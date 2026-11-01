#!/usr/bin/env python3
"""
start.py — consolidated artifact generator for /sdd:start.

Creates the .specwork bootstrap artifacts from a single call: state, rules,
cache, and source.md. Returns a JSON summary.

source.md captures the raw input the spec is drafted from. Pass the free-text
description via --source-body-file to persist it (mirrors how the Jira path
writes the fetched issue into source.md); without it, a placeholder is written.

--slug must be canonical — exactly what lib/slug.py derives (lowercase,
non-alphanumerics → hyphens), the same form /sdd:resync writes. A non-canonical
slug is rejected (exit 2, nothing written) rather than normalized silently: the
Jira path writes <slug>-source.md before this script runs, so a silent rename
would split the pipeline's files across two prefixes.

It does NOT create spec.md — that is /sdd:spec's job (draft mode reads source.md
+ templates/spec.md and writes the spec). The write_spec_scaffold helper below
stays available as the canonical section structure for /sdd:spec and tests.

Usage:
  python3 start.py \
    --slug <slug> \
    --ticket <TICKET|none> \
    --input-type jira|freetext \
    --branch <branch> \
    --base-branch <branch> \
    --spec-dir .specwork \
    [--source-body-file <path>]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import paths
import slug as slugs


def ensure_gitignore(entry=".specwork/"):
    """Ensure `.specwork/` is gitignored (idempotent). Returns a status dict.

    Mirrors the shell start behavior: append to (or create) .gitignore so
    transient pipeline state is never committed. If the directory is already
    tracked from a prior bad setup, flag it — .gitignore alone won't untrack it,
    and we never run `git rm --cached` automatically (too destructive without
    explicit intent). Degrades gracefully when git is absent (alpine CI).
    """
    entry = entry.rstrip("/")  # normalize; matched with an optional trailing slash
    gitignore = Path(".gitignore")
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    appended = False
    if not re.search(rf"^{re.escape(entry)}(/|$)", existing, re.MULTILINE):
        prefix = "" if existing == "" or existing.endswith("\n") else "\n"
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{prefix}# SDD pipeline state (transient)\n{entry}/\n")
        appended = True

    tracked = False
    try:
        result = subprocess.run(
            ["git", "ls-files", entry],
            capture_output=True, text=True, check=False, timeout=10,
        )
        tracked = bool(result.stdout.strip())
    except Exception:
        tracked = False

    return {"appended": appended, "tracked": tracked}


def build_state(slug, ticket, input_type, branch, base_branch, spec_dir, non_interactive=False):
    non_interactive = non_interactive or os.environ.get("SDD_NON_INTERACTIVE", "0") == "1"
    # Path STRINGS in state.json are repo-relative (portable) — always under the
    # default `.specwork/`, regardless of where files are physically written
    # (tests may pass an absolute spec_dir). So derive them with paths.py defaults.
    state = {
        "schema_version": 1,
        "id": slug,
        "ticket": ticket if ticket and ticket != "none" else None,
        "input_type": input_type,
        "non_interactive": non_interactive,
        "branch": branch,
        "base_branch": base_branch,
        "source_title": "",
        "source_body_file": paths.source_file(slug),
        "spec_file": paths.spec_file(slug),
        "context_file": paths.context_file(slug),
        "rules_file": paths.rules_file(slug),
        "path_file": paths.path_file(slug),
        "implementation_cache_file": paths.cache_file(slug),
    }
    return state


# Cap on distilled invariants written to rules.json. Generous enough to hold a
# curated multi-domain rule set, bounded so an accidental dump can't bloat the file.
MAX_GLOBAL_RULES = 100


def _iter_rule_files(rule_sources):
    """Yield concrete markdown files from the given paths.

    A path may be a file or a directory; directories expand to their ``*.md``
    files (recursively), sorted for deterministic output. This lets callers pass
    a per-topic rules directory (e.g. ``.claude/rules``) alongside individual
    files. Missing paths are skipped.
    """
    for path_str in rule_sources:
        p = Path(path_str)
        if p.is_dir():
            yield from sorted(p.rglob("*.md"))
        elif p.exists():
            yield p


_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
# Headings whose bullets are real rules. A document that uses any of these switches
# to "selective" extraction; one that uses none (e.g. AGENTS.md, all bullets are rules)
# falls back to extracting every bullet.
_RULE_SECTION_RE = re.compile(r"invariant|constraint", re.IGNORECASE)


def _extract_rules(text):
    """Extract rule statements from markdown, joining wrapped continuation lines.

    Captures two kinds of statement: ``-`` bullets and ``>`` callouts (the latter
    prefixed with ``Note: `` so a critical clarification — e.g. an implementation
    note under an Invariants heading — survives into ``rules.json`` for consumers
    that have no access to the source markdown, such as a handoff pack).

    Two modes, chosen per document:

    * **Selective** — if the document has any heading matching ``_RULE_SECTION_RE``
      (e.g. ``### Invariants``), only statements under such headings are returned.
      Intro prose and meta-guidance (e.g. a "How to organize" or "Adding a domain"
      section) are skipped.
    * **Fallback** — if no such heading exists, every bullet is returned (legacy
      behavior; keeps files like ``AGENTS.md`` where all bullets are rules working).
      Callouts are only captured in selective mode, to avoid pulling unrelated
      asides from prose-heavy docs.

    Bullets/callouts that wrap across several lines survive intact; tables and
    headings are ignored.
    """
    lines = text.splitlines()
    selective = any(
        _RULE_SECTION_RE.search(m.group(1))
        for m in (_HEADING_RE.match(line) for line in lines)
        if m
    )

    rules = []
    bullet = None   # in-progress "- " bullet
    callout = None  # in-progress "> " callout
    collecting = not selective

    def flush():
        nonlocal bullet, callout
        if bullet:
            rules.append(bullet)
            bullet = None
        if callout:
            rules.append("Note: " + callout)
            callout = None

    for raw in lines:
        heading = _HEADING_RE.match(raw)
        if heading:
            flush()
            if selective:
                collecting = bool(_RULE_SECTION_RE.search(heading.group(1)))
            continue
        if not collecting:
            continue
        if re.match(r"^- \S", raw):
            flush()
            bullet = raw[2:].strip()
        elif selective and raw.startswith(">"):
            if bullet:
                rules.append(bullet)
                bullet = None
            piece = raw.lstrip(">").strip()
            if not piece:  # blank ">" line separates adjacent callouts
                if callout:
                    rules.append("Note: " + callout)
                    callout = None
            else:
                callout = (callout + " " + piece) if callout else piece
        elif bullet is not None and raw[:1] in (" ", "\t") and raw.strip():
            bullet += " " + raw.strip()
        else:
            flush()
    flush()
    return rules


def build_rules(slug, rule_sources):
    global_rules = []
    sources = []

    for p in _iter_rule_files(rule_sources):
        sources.append(str(p))
        global_rules.extend(_extract_rules(p.read_text(encoding="utf-8")))

    # Dedupe while preserving order
    seen = set()
    global_rules_deduped = []
    for r in global_rules:
        if r not in seen:
            seen.add(r)
            global_rules_deduped.append(r)

    if len(global_rules_deduped) > MAX_GLOBAL_RULES:
        print(
            f"WARNING: extracted {len(global_rules_deduped)} rules from {len(sources)} source(s); "
            f"rules.json keeps only the first {MAX_GLOBAL_RULES}. "
            f"{len(global_rules_deduped) - MAX_GLOBAL_RULES} dropped — split or trim the rule files "
            f"so no invariant is silently lost.",
            file=sys.stderr,
        )

    return {
        "schema_version": 1,
        "id": slug,
        "source_files": sources,
        "global_rules": global_rules_deduped[:MAX_GLOBAL_RULES],
        "service_rules": [],
    }


def scaffold_rules_if_missing(
    template_path, rules_dir=".claude/rules", legacy_file=".claude/service-rules.md"
):
    """Create a starter rules file from a template, only when none exists yet.

    "None exists" means: no legacy single ``.claude/service-rules.md`` AND no
    ``*.md`` under ``.claude/rules/``. When that holds, copy ``template_path`` to
    ``<rules_dir>/service-rules.md``; otherwise leave existing rules untouched
    (never overwrite). Keeping this decision in code — rather than SKILL.md prose
    the model executes — makes it deterministic and testable.

    Returns a status dict: ``{scaffolded: bool, path: str|None, reason: str}``.
    """
    rules_dir_p = Path(rules_dir)
    has_legacy = Path(legacy_file).is_file()
    has_dir_rules = rules_dir_p.is_dir() and any(rules_dir_p.glob("*.md"))
    if has_legacy or has_dir_rules:
        return {"scaffolded": False, "path": None, "reason": "rules already present"}

    template = Path(template_path)
    if not template.is_file():
        return {"scaffolded": False, "path": None, "reason": f"template not found: {template_path}"}

    rules_dir_p.mkdir(parents=True, exist_ok=True)
    target = rules_dir_p / "service-rules.md"
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    return {"scaffolded": True, "path": str(target), "reason": "no existing rules; scaffolded from template"}


def build_cache(slug):
    return {
        "schema_version": 1,
        "id": slug,
        "repositories": [],
        "patterns": [],
        "related_tests": [],
        "similar_classes": [],
        "notes": [],
    }


_PLACEHOLDER_MARKER = "goes here."


def _source_has_real_body(path: Path) -> bool:
    """Return True when source.md already contains real content (not a placeholder)."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return bool(text.strip()) and _PLACEHOLDER_MARKER not in text


def write_source_md(slug, spec_dir, ticket, input_type, source_body=None):
    path = Path(spec_dir) / "_spec" / f"{slug}-source.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    # Don't overwrite content already written by jira_write_issue_markdown or
    # any other upstream step — only write when the file is absent or a placeholder.
    if _source_has_real_body(path):
        return str(path)

    label = f"JIRA: {ticket}" if ticket and ticket != "none" else "Free text"
    body = (source_body or "").strip()
    if body:
        content = f"# {slug} — Source\n\n> {label}\n\n{body}\n"
    else:
        content = f"# {slug} — Source\n\n> {label}\n\nRaw input from {input_type} goes here.\n"
    path.write_text(content, encoding="utf-8")
    return str(path)


def write_spec_scaffold(slug, spec_dir, ticket, input_type):
    label = f"JIRA: {ticket}" if ticket and ticket != "none" else "Free text"
    path = Path(spec_dir) / "_spec" / f"{slug}-spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {slug} — <Title>\n\n"
        f"> Source: {label}\n\n"
        f"## Summary\n\n"
        f"One or two sentences.\n\n"
        f"## Scope\n\n"
        f"### In scope\n"
        f"- \n\n"
        f"### Out of scope\n"
        f"- \n\n"
        f"## Behavior\n\n"
        f"1. \n\n"
        f"## Implementation Context\n"
        f"- \n\n"
        f"## Expected Change Scope\n"
        f"- **Expected files touched**: \n"
        f"- **Expected layers**: \n"
        f"- **Avoid touching**:\n"
        f"  - \n\n"
        f"## Safe Constraints\n"
        f"**Safe**:\n"
        f"- \n\n"
        f"**Unsafe**:\n"
        f"- \n\n"
        f"## Open Questions\n\n"
        f"- [ ] **#1** *Add your first open question here*\n",
        encoding="utf-8",
    )
    return str(path)


def main():
    parser = argparse.ArgumentParser(description="Initialize SDD pipeline artifacts")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--ticket", default="none")
    parser.add_argument("--input-type", choices=["jira", "freetext"], default="freetext")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base-branch", default="")
    parser.add_argument("--spec-dir", default=".specwork")
    parser.add_argument("--rules", nargs="*", default=[])
    parser.add_argument(
        "--scaffold-rules-template",
        default="",
        help="If set and the project has no rules yet (.claude/service-rules.md or "
        ".claude/rules/*.md), scaffold .claude/rules/service-rules.md from this template path. "
        "Never overwrites existing rules.",
    )
    parser.add_argument(
        "--source-body",
        default="",
        help="Inline free-text body for source.md. Use this instead of "
        "--source-body-file when the content is available in memory — no temp "
        "file needed. Takes precedence over --source-body-file when both are set.",
    )
    parser.add_argument(
        "--source-body-file",
        default="",
        help="Path to a file whose contents become the source.md body "
        "(e.g. the free-text description). Falls back to a placeholder when "
        "omitted or the file is missing. Prefer --source-body for inline text.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        default=False,
        help="Set non_interactive=true in state.json. Equivalent to SDD_NON_INTERACTIVE=1 "
        "but reliable across subprocess boundaries (env vars are not always inherited).",
    )
    args = parser.parse_args()

    canonical = slugs.normalize_slug(args.slug)
    if args.slug != canonical:
        hint = f"'{canonical}'" if canonical else "a non-empty slug"
        print(
            f"✗ Non-canonical slug '{args.slug}' — expected {hint}.\n"
            f"  Derive it with: python3 lib/slug.py \"{args.branch}\"  (field 'slug')",
            file=sys.stderr,
        )
        sys.exit(2)

    spec_dir = Path(args.spec_dir)
    for sub in ["_spec", "_state", "_progress"]:
        (spec_dir / sub).mkdir(parents=True, exist_ok=True)

    # 1. State
    state = build_state(args.slug, args.ticket, args.input_type, args.branch, args.base_branch, args.spec_dir, args.non_interactive)
    state_path = spec_dir / "_state" / f"{args.slug}-state.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    # 1.5 Scaffold a starter rules file when the project has none yet (optional).
    scaffold = {"scaffolded": False, "path": None, "reason": "not requested"}
    if args.scaffold_rules_template:
        scaffold = scaffold_rules_if_missing(args.scaffold_rules_template)
        if scaffold["scaffolded"]:
            print(f"Scaffolded {scaffold['path']} from template", file=sys.stderr)

    # 2. Rules
    rules = build_rules(args.slug, args.rules)
    rules_path = spec_dir / "_state" / f"{args.slug}-rules.json"
    rules_path.write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")

    # 3. Cache
    cache = build_cache(args.slug)
    cache_path = spec_dir / "_state" / f"{args.slug}-implementation-cache.json"
    cache_path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")

    # 4. Source.md — persist the passed body (free-text description) when given,
    #    otherwise a placeholder. The Jira path writes source.md separately.
    #    --source-body (inline) takes precedence over --source-body-file.
    source_body = ""
    if args.source_body:
        source_body = args.source_body
    elif args.source_body_file:
        body_path = Path(args.source_body_file)
        if body_path.exists():
            source_body = body_path.read_text(encoding="utf-8")
    source_path = write_source_md(
        args.slug, args.spec_dir, args.ticket, args.input_type, source_body
    )
    # Reflect actual file state — the Jira path writes source.md before calling
    # start.py, so source_body may be empty even when the file has real content.
    source_has_body = _source_has_real_body(Path(source_path))

    # 5. Ensure transient state is gitignored
    gitignore = ensure_gitignore()
    if gitignore["tracked"]:
        print(
            "\n⚠  Warning: .specwork/ files are already tracked in git from a prior\n"
            "   setup. .gitignore alone will not untrack them. To fix:\n\n"
            "     git rm -r --cached .specwork/\n"
            "     git commit -m 'chore: untrack .specwork/ (pipeline state is transient)'\n",
            file=sys.stderr,
        )

    # 6. Output summary. spec_file is declared (not yet created) — /sdd:spec writes it.
    result = {
        "state_file": str(state_path),
        "rules_file": str(rules_path),
        "cache_file": str(cache_path),
        "source_file": source_path,
        "source_has_body": source_has_body,
        "spec_file": state["spec_file"],
        "spec_created": False,
        "gitignore": gitignore,
        "rules_scaffold": scaffold,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
