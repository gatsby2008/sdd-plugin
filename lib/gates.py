#!/usr/bin/env python3
"""
Shared validation gates for SDD pipeline. Usable standalone or as a library.

Standalone:
  python3 gates.py check-oqs <slug>               # exit 1 if unresolved OQs
  python3 gates.py check-staleness <slug>          # exit 1 if plan stale
  python3 gates.py record-fingerprint <slug>       # stamp spec fingerprint into plan
  python3 gates.py check-artifacts <slug>          # exit 1 if missing
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import paths

# Marker stamped into a plan by /sdd:plan to record which spec it was built
# against. Lets plan-staleness be detected by spec *content* identity instead of
# filesystem mtime, which git stash/checkout/rebase do not preserve.
FINGERPRINT_MARKER = "spec-fingerprint:"

# Single source of truth for the pipeline working-dir root. Used as the default
# for spec_dir= params and by the CLI handlers below, so the path is defined once.
SPECWORK = ".specwork"


def section_text(text, heading):
    m = re.search(rf"(?ms)^## {re.escape(heading)}\b(.*?)(?=^## |\Z)", text)
    return m.group(1).strip() if m else ""


def unresolved_oqs(text):
    """Return list of unresolved OQ lines from ## Open Questions section."""
    section = section_text(text, "Open Questions")
    return [l.strip() for l in section.splitlines() if re.match(r"^\s*-\s*\[\s*\]", l)]


def check_open_questions(slug, spec_dir=SPECWORK):
    """Check spec and optionally plan for unresolved OQs. Returns list of blockers."""
    spec = Path(spec_dir) / "_spec" / f"{slug}-spec.md"
    plan = Path(spec_dir) / "_plan" / f"{slug}-plan.md"
    blockers = []

    for path in [spec, plan]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        oqs = unresolved_oqs(text)
        if oqs:
            blockers.append((str(path), oqs))

    return blockers


def count_open_questions(text):
    """Return ``(open, resolved)`` counts from the ## Open Questions section.

    Open = ``- [ ]``; resolved = ``- [x]`` (case-insensitive).
    """
    section = section_text(text, "Open Questions")
    open_n = len([l for l in section.splitlines() if re.match(r"^\s*-\s*\[\s*\]", l)])
    resolved_n = len([l for l in section.splitlines() if re.match(r"^\s*-\s*\[[xX]\]", l)])
    return open_n, resolved_n


def get_resolved_oqs(text):
    """Return ``{question: answer}`` for resolved OQs.

    A resolved line looks like ``- [x] <question> — <answer>``. When no ``—``
    separator is present the whole line is the key and the answer is "".
    """
    section = section_text(text, "Open Questions")
    out = {}
    for l in section.splitlines():
        m = re.match(r"^\s*-\s*\[[xX]\]\s*(.+)$", l)
        if not m:
            continue
        body = m.group(1).strip()
        if "—" in body:
            q, a = body.split("—", 1)
            out[q.strip()] = a.strip()
        else:
            out[body] = ""
    return out


def spec_fingerprint(slug, spec_dir=SPECWORK):
    """SHA-256 of the normalized spec body, or "" when the spec is absent.

    Normalizes trailing whitespace and outer blanks so a no-content editor save
    (or a ``touch``) does not change the fingerprint — only real edits do.
    """
    spec_file = Path(spec_dir) / "_spec" / f"{slug}-spec.md"
    if not spec_file.exists():
        return ""
    text = spec_file.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def read_plan_fingerprint(plan_file):
    """Return the spec fingerprint recorded in the plan, or "" if none."""
    if not plan_file.exists():
        return ""
    pattern = re.compile(rf"{re.escape(FINGERPRINT_MARKER)}\s*([0-9a-f]{{64}})")
    for line in plan_file.read_text(encoding="utf-8").splitlines():
        m = pattern.search(line)
        if m:
            return m.group(1)
    return ""


def record_plan_fingerprint(slug, spec_dir=SPECWORK):
    """Stamp the current spec fingerprint into the plan file (idempotent).

    Called by /sdd:plan after the plan is written. Returns True on success,
    False when the plan or spec is missing.
    """
    plan_file = Path(spec_dir) / "_plan" / f"{slug}-plan.md"
    if not plan_file.exists():
        return False
    fp = spec_fingerprint(slug, spec_dir)
    if not fp:
        return False
    lines = [l for l in plan_file.read_text(encoding="utf-8").splitlines()
             if FINGERPRINT_MARKER not in l]
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append(f"<!-- {FINGERPRINT_MARKER} {fp} -->")
    plan_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def check_plan_staleness(slug, spec_dir=SPECWORK):
    """Detect a plan built against an older spec.

    Prefers the content fingerprint stamped into the plan by /sdd:plan — robust
    to git stash/checkout/rebase/worktree, which reset mtimes (e.g. /sdd:pause
    round-trips .specwork/ through ``git stash --all``). Falls back to mtime for
    legacy plans written before fingerprinting.
    """
    spec_file = Path(spec_dir) / "_spec" / f"{slug}-spec.md"
    plan_file = Path(spec_dir) / "_plan" / f"{slug}-plan.md"

    if not plan_file.exists() or not spec_file.exists():
        return None

    recorded = read_plan_fingerprint(plan_file)
    if recorded:
        current = spec_fingerprint(slug, spec_dir)
        if current and current != recorded:
            return {"stale": True, "reason": "fingerprint", "fix_command": "/sdd:plan"}
        return {"stale": False}

    # Legacy plan (no fingerprint stamped): fall back to mtime comparison.
    plan_mtime = plan_file.stat().st_mtime
    spec_mtime = spec_file.stat().st_mtime
    if plan_mtime < spec_mtime:
        return {
            "stale": True,
            "reason": "mtime",
            "plan_mtime": plan_mtime,
            "spec_mtime": spec_mtime,
            "fix_command": "/sdd:plan",
        }
    return {"stale": False}


def format_staleness_error(slug, spec_dir=SPECWORK):
    """Human-readable staleness message, or "" when the plan is fresh/absent."""
    result = check_plan_staleness(slug, spec_dir)
    if not result or not result.get("stale"):
        return ""
    return (
        f"Plan is stale: .specwork/_plan/{slug}-plan.md was built against an older "
        f".specwork/_spec/{slug}-spec.md (the spec changed after the plan was written). "
        f"Re-run /sdd:plan to refresh it, or delete the plan to force a rebuild."
    )


def check_required_artifacts(slug, spec_dir=SPECWORK):
    """Check that all required artifacts exist. Returns list of missing paths."""
    spec_dir = Path(spec_dir)
    required = [
        spec_dir / "_state" / f"{slug}-state.json",
        spec_dir / "_state" / f"{slug}-rules.json",
        spec_dir / "_spec" / f"{slug}-spec.md",
    ]
    missing = [str(p) for p in required if not p.exists()]
    return missing


def plan_required(slug, spec_dir=SPECWORK):
    """Return True when triage marked this pipeline plan-required AND no plan exists.

    triage.py stamps ``plan_required`` into ``.specwork/_state/<slug>-path.json``
    for high-risk / architectural work. /sdd:implement blocks on this so a
    high-risk change gets a reviewable plan first, while trivial/focused/standard
    keep the optional plan step (the vibe-coding path). Returns False when
    ``path.json`` is absent (pipelines triaged before this field existed) or when
    a plan already exists.

    A tier override (``/sdd:spec --tier``) wins over the automatic result: when
    ``path.json`` carries an ``override`` block, its ``tier`` alone decides.
    """
    path_json = Path(spec_dir) / "_state" / f"{slug}-path.json"
    if not path_json.exists():
        return False
    try:
        data = json.loads(path_json.read_text(encoding="utf-8"))
    except Exception:
        return False
    override = data.get("override")
    if isinstance(override, dict) and override.get("tier"):
        required = override["tier"] == "high-risk"
    else:
        required = bool(data.get("plan_required"))
    if not required:
        return False
    plan_file = Path(spec_dir) / "_plan" / f"{slug}-plan.md"
    return not plan_file.exists()


def audit_artifacts(slug, spec_dir=SPECWORK):
    """Existence + mtime for every artifact of a slug, keyed by artifact name."""
    result = {}
    for name, rel in paths.all_paths(slug, spec_dir).items():
        p = Path(rel)
        exists = p.exists()
        result[name] = {
            "path": rel,
            "exists": exists,
            "mtime": p.stat().st_mtime if exists else None,
        }
    return result


def risk_signals(spec_text):
    """Detect risk signals from spec text. Returns dict of signal→matches."""
    text = spec_text.lower()
    signals = {
        "db-migration": r"\b(?:migration|flyway|liquibase|alter\s+table|drop\s+(?:table|column)|schema\s+change|add\s+column|rename\s+column)\b",
        "auth-security": r"\b(?:authentication|authorization|oauth|jwt|security\s+config|credential|permission|role-based|access\s+control|token\s+validation|password\s+hash)\b",
        "breaking-api": r"\b(?:breaking\s+change|remove\s+endpoint|deprecate\s+endpoint|change\s+response\s+(?:format|shape)|change\s+contract|api\s+version\s+bump)\b",
        "data-destructive": r"\b(?:delete\s+data|purge|wipe|cleanup\s+data|production\s+data|truncate)\b",
        "concurrency": r"\b(?:@transactional|distributed\s+transaction|race\s+condition|two-phase\s+commit|optimistic\s+lock|pessimistic\s+lock)\b",
        # Frontend risk signals
        "component-api": r"\b(?:component\s+api|props?\s+(?:interface|type|shape)|breaking\s+change\s+in\s+component|rename\s+prop|remove\s+prop|change\s+(?:prop|render)\s+(?:type|signature))\b",
        "state-management": r"\b(?:state\s+management|redux|zustand|context\s+api|mobx|recoil|jotai|migration\s+(?:from|to)\s+(?:redux|zustand|context)|replace\s+(?:redux|zustand|context))\b",
        "accessibility": r"\b(?:a11y|accessibility|aria[-_]\w*|screen\s+reader|keyboard\s+navigat|focus\s+trap|role\s*=|tab\s*index|wcag|contrast\s+ratio)\b",
        "routing": r"\b(?:routing|navigation|react-router|next\.router|userouter|navigate|redirect|route\s+(?:structure|change|restructure))\b",
        "data-fetching": r"\b(?:data\s+fetching|useswr|react-query|tanstack\s+query|apollo\s+client|graphql|usequery|usemutation|ssr|server-side\s+rendering|hydration|getserversideprops|getstaticprops|getstaticpaths)\b",
        "ui-migration": r"\b(?:ui[- ]library\s+(?:upgrade|migration|bump)|migrat(?:e|ion)\s+(?:from|to)\s+(?:material|antd|chakra|tailwind|bootstrap|shadcn|styled|emotion)|design\s+system\s+update|theming\s+overhaul|dark\s+mode)\b",
    }
    hits = {}
    for label, pattern in signals.items():
        matches = re.findall(pattern, text)
        if matches:
            hits[label] = sorted(set(matches))[:3]
    return hits


def spec_consistency(text):
    """Check spec for internal contradictions. Returns list of flagged issues."""
    pairs = [
        ("idempotent + per-call side effect",
         r"\bidempotent(ly|cy)?\b",
         r"\b(log|audit|notify|publish|emit)\b[^.\n]{0,40}\b(on|in|per|for)\s+(each|every)\s+(call|invocation|request)\b",
         None),
        ("remove + still-referenced",
         r"\b(remove|delete|drop)\s+(the\s+)?(endpoint|method|class|column|field|constant)\b",
         r"\bstill\s+(referenced|used|in[- ]use)\b",
         None),
        ("atomic + multi-step",
         r"\batomic\b",
         r"\bmulti[- ]step\b",
         r"\b(transaction|saga|two[- ]phase|coordinator|orchestrat)\w*"),
        ("cache + always fresh",
         r"\bcach(e|ing)\b",
         r"\b(always|fully)\s+(fresh|real[- ]time|up[- ]to[- ]date|current)\b",
         r"\b(invalidat|expir|ttl|evict|refresh\s+strategy)\w*"),
    ]
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    flagged = []
    for label, pat_a, pat_b, resolver in pairs:
        in_a = {i for i, p in enumerate(paragraphs) if re.search(pat_a, p, re.IGNORECASE)}
        in_b = {i for i, p in enumerate(paragraphs) if re.search(pat_b, p, re.IGNORECASE)}
        if not in_a or not in_b:
            continue
        if in_a & in_b:
            continue
        if resolver and re.search(resolver, text, re.IGNORECASE):
            continue
        flagged.append(label)
    return flagged


def detect_stack(project_dir="."):
    """Detect project stack. Returns 'java', 'frontend', 'node', or 'unknown'.

    'frontend' is a JS/TS project that ships a UI framework (config file or
    dependency); plain 'node' is a backend/CLI JS project. The split lets
    /sdd:spec and /sdd:plan apply UI-specific structure (components, routes, a11y).
    """
    root = Path(project_dir)
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists() or (root / "pom.xml").exists():
        return "java"
    if not (root / "package.json").exists():
        return "unknown"
    frontend_configs = [
        "vite.config.ts", "vite.config.js", "vite.config.mjs",
        "next.config.js", "next.config.ts", "next.config.mjs",
        "angular.json", "svelte.config.js", "nuxt.config.ts",
        "nuxt.config.js", "vue.config.js", "remix.config.js",
        "astro.config.mjs",
    ]
    if any((root / f).exists() for f in frontend_configs):
        return "frontend"
    try:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        frontend_kw = {"react", "vue", "@angular/core", "svelte", "preact", "solid-js", "lit"}
        if frontend_kw & set(deps.keys()):
            return "frontend"
    except Exception:
        pass
    return "node"


def merge_cache(slug, new_facts, spec_dir=SPECWORK):
    """Load cache, merge new facts (append-only, dedupe), write back."""
    p = Path(spec_dir) / "_state" / f"{slug}-implementation-cache.json"
    keys = ("repositories", "patterns", "related_tests", "similar_classes", "notes")
    cache = {"schema_version": 1, "id": slug, **{k: [] for k in keys}}
    if p.exists():
        cache.update(json.loads(p.read_text(encoding="utf-8")))
    for k in keys:
        merged = cache.get(k, []) + new_facts.get(k, [])
        cache[k] = list(dict.fromkeys(x.strip() for x in merged if isinstance(x, str) and x.strip()))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    return cache


def behavioral_change_signals(spec_text, plan_text=""):
    """Detect signals that spec modifies existing behavior (vs additive only)."""
    text = spec_text.lower()
    signals = {
        "idempotent": r'\bidempotent(ly)?\b',
        "no-op": r'\bno[- ]op\b',
        "no longer": r'\bno longer\b',
        "instead of": r'\binstead of\b',
        "remove existing": r'\bremove[s]?\s+(the\s+)?existing\b',
        "override existing": r'\boverride[s]?\s+(the\s+)?existing\b',
        "change the behavior": r'\bchange\s+(the\s+)?behavior\b',
        "short-circuit": r'\bshort[- ]circuit\b',
        "replace the": r'\breplace[sd]?\s+the\s+\w+',
        "stop VERB-ing": r'\bstop\s+\w+ing\b',
    }
    hits = [label for label, pat in signals.items() if re.search(pat, text)]
    if '[infra]' in plan_text:
        hits.append("plan contains [infra] tag")
    if '[reference-update]' in plan_text:
        hits.append("plan contains [reference-update] tag")
    return hits


def worktree_freshness(plan_path):
    """Check plan Target Files against worktree. Returns list of discrepancies."""
    p = Path(plan_path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    m = re.search(r'## Target Files\s*\n(.*?)(?=\n## |\Z)', text, re.DOTALL)
    if not m:
        return []
    new_hints = re.compile(r'\(new\)|\bnew file\b|\bcreate[sd]?\b|\bbrand[- ]new\b', re.IGNORECASE)
    discrepancies = []
    for line in m.group(1).splitlines():
        if not line.startswith('|') or set(line.replace('|', '').replace(' ', '')) <= {'-', ':'}:
            continue
        parts = [c.strip() for c in line.split('|')[1:-1]]
        if len(parts) < 2 or parts[0].lower() == 'file':
            continue
        file_cell, change_cell = parts[0], parts[1]
        pm = re.search(r'`([^`]+)`', file_cell)
        if not pm:
            continue
        path = pm.group(1)
        if '[UNVERIFIED]' in change_cell:
            continue
        is_new = bool(new_hints.search(change_cell))
        exists = Path(path).exists()
        if is_new and exists:
            discrepancies.append(f"`{path}` marked new but already exists")
        elif not is_new and not exists:
            discrepancies.append(f"`{path}` expected but not found")
    return discrepancies


def require_specwork(spec_dir=SPECWORK):
    """Returns a reject reason if the pipeline is not initialized here, else None."""
    root = Path(spec_dir)
    if not root.is_dir():
        return f"No pipeline working directory ({spec_dir}/ not found). Run /sdd:start first."
    state_dir = root / "_state"
    if not state_dir.is_dir() or not any(state_dir.glob("*-state.json")):
        return f"Pipeline not initialized ({spec_dir}/_state has no *-state.json). Run /sdd:start first."
    return None


def non_interactive_mode(slug, spec_dir=SPECWORK):
    """Return True when state.json marks this pipeline as non-interactive."""
    state_path = Path(spec_dir) / "_state" / f"{slug}-state.json"
    if not state_path.exists():
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(state.get("non_interactive"))


def resolve_slug(branch=None, spec_dir=SPECWORK):
    """Resolve the active pipeline slug from ``.specwork/_state/*-state.json``.

    Replaces the ``ls ... | head -1 | sed`` one-liner duplicated across skills.
    With a ``branch``, prefer the state file whose ``branch`` field matches it
    (the correct pick when several pipelines left state behind); otherwise return
    the first state file's slug. Returns ``""`` when none is found.
    """
    state_dir = Path(spec_dir) / "_state"
    candidates = sorted(state_dir.glob("*-state.json")) if state_dir.is_dir() else []
    if not candidates:
        return ""

    def slug_of(p):
        return p.name[: -len("-state.json")]

    if branch:
        for p in candidates:
            try:
                if json.loads(p.read_text(encoding="utf-8")).get("branch") == branch:
                    return slug_of(p)
            except Exception:
                continue
    return slug_of(candidates[0])


def resolve_slug_for_branch(branch, spec_dir=SPECWORK):
    """Return the slug whose state.json ``branch`` field exactly matches ``branch``.

    Unlike ``resolve_slug()``, this never falls back to the first state file
    when no exact match is found. That fallback is correct for skills resuming
    the "current" pipeline (branch rename, restore, etc.) but wrong for gates
    that decide *whether a pipeline governs this branch at all* — e.g. the
    push-gate and coverage-gate hooks, which must not treat some other
    branch's leftover ``.specwork/`` state (never cleared because it's
    gitignored and survives `git checkout`) as if it applied here. Returns
    ``""`` when ``branch`` is falsy, the state dir is absent, or nothing
    matches.
    """
    if not branch:
        return ""
    state_dir = Path(spec_dir) / "_state"
    if not state_dir.is_dir():
        return ""
    for p in sorted(state_dir.glob("*-state.json")):
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("branch") == branch:
                return p.name[: -len("-state.json")]
        except Exception:
            continue
    return ""


def pipeline_branch_status(branch, spec_dir=SPECWORK):
    """Full picture of how ``.specwork/`` relates to ``branch``.

    ``/sdd:pause`` and ``/sdd:close`` both need to decide, deterministically,
    whether it is safe to act on whatever pipeline state happens to be on disk
    — previously this was left to prose ("verify the branch") with no gates.py
    call backing it, so a rushed or careless run could stash/delete a
    *different* branch's pipeline under the current branch's label. This
    answers that in one call instead of leaving it to interpretation.

    Returns a dict:
      current_branch        -- ``branch`` as given
      has_any_pipeline       -- True if any ``*-state.json`` exists at all
      owns_pipeline          -- True if some state.json's ``branch`` field
                                 equals ``branch`` exactly (this branch has its
                                 own pipeline — the normal case, nothing to warn)
      slug                   -- the owning slug when owns_pipeline is True;
                                 otherwise the slug resolve_slug()'s fallback
                                 would silently pick (reported here so the
                                 caller can *name* the mismatch instead of
                                 acting on it blind), or "" if nothing at all
      recorded_branch         -- that slug's own recorded branch
      recorded_base_branch    -- that slug's recorded base_branch, or ""
      is_base_branch          -- True if ``branch`` equals recorded_base_branch
                                 — the "MR already merged, back on the base
                                 branch to clean up" case /sdd:close's "safe to
                                 run from any branch" is meant to cover, as
                                 opposed to a genuinely unrelated third branch
    """
    state_dir = Path(spec_dir) / "_state"
    candidates = sorted(state_dir.glob("*-state.json")) if state_dir.is_dir() else []
    result = {
        "current_branch": branch or "",
        "has_any_pipeline": bool(candidates),
        "owns_pipeline": False,
        "slug": "",
        "recorded_branch": "",
        "recorded_base_branch": "",
        "is_base_branch": False,
    }
    if not candidates:
        return result

    def slug_of(p):
        return p.name[: -len("-state.json")]

    if branch:
        for p in candidates:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("branch") == branch:
                result["owns_pipeline"] = True
                result["slug"] = slug_of(p)
                result["recorded_branch"] = data.get("branch", "")
                result["recorded_base_branch"] = data.get("base_branch", "")
                return result

    # No match for `branch` — report the same file resolve_slug() would
    # silently fall back to, purely so the caller can name the mismatch.
    p = candidates[0]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    result["slug"] = slug_of(p)
    result["recorded_branch"] = data.get("branch", "")
    result["recorded_base_branch"] = data.get("base_branch", "")
    result["is_base_branch"] = bool(branch) and branch == result["recorded_base_branch"]
    return result


def _git(args, timeout=10):
    """Run a git command. Returns ``(returncode, stdout)``; rc is ``None`` when
    git could not be run at all (not installed, timeout), which callers must
    treat as "unknown", never as "the check failed".
    """
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False, timeout=timeout
        )
        return r.returncode, r.stdout.strip()
    except Exception:
        return None, ""


def branch_merge_status(branch, base, git=_git):
    """Classify a pipeline's recorded branch against its recorded base branch.

    Git-only and offline — no ``glab``, no network. This answers "has this
    pipeline's work already landed?" well enough to *warn*; the authoritative
    MR state still comes from /sdd:close's ``glab mr view`` check before it
    deletes anything.

    Returns one of:
      ``"branch-gone"``  -- no local ref for ``branch``; it was almost certainly
                            merged and deleted (the usual post-MR cleanup), but
                            a rename that skipped /sdd:resync looks identical,
                            so callers must warn rather than act
      ``"merged"``       -- ``branch`` is an ancestor of ``base`` (or
                            ``origin/<base>``): its commits are already in
      ``"open"``         -- ``branch`` exists and has not landed in a resolvable base
      ``"unknown"``      -- not a git repo, git unavailable, no base recorded, or
                            neither ``base`` nor ``origin/<base>`` resolves
    """
    if not branch:
        return "unknown"
    # One repo probe up front: outside a git repo (or with no git at all) every
    # subsequent rc is nonzero, which would masquerade as "branch-gone".
    rc, _ = git(["rev-parse", "--git-dir"])
    if rc != 0:
        return "unknown"
    rc, _ = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"])
    if rc is None:
        return "unknown"
    if rc != 0:
        return "branch-gone"
    if not base:
        return "unknown"
    resolved = False
    for ref in (base, f"origin/{base}"):
        rc_ref, _ = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        if rc_ref != 0:
            continue
        resolved = True
        rc_anc, _ = git(["merge-base", "--is-ancestor", branch, ref])
        if rc_anc == 0:
            return "merged"
    return "open" if resolved else "unknown"


def pipeline_inventory(current_branch, spec_dir=SPECWORK, git=_git):
    """Inventory every pipeline on disk and flag the closable leftovers.

    ``.specwork/`` is gitignored, so it survives `git checkout` and outlives the
    branch it belongs to: finish a feature, merge the MR, never run /sdd:close,
    and its state sits there indefinitely. /sdd:start then refuses to start
    anything new because "a pipeline is already active" — pointing the user at
    /sdd:spec to *continue* work that already shipped.

    This lets /sdd:start tell the two cases apart before it writes that message:
    a pipeline this branch actually owns (continue it) versus an orphan whose
    work already landed (close it). Purely a reporting call — it never deletes.

    Returns a dict:
      current_branch -- ``current_branch`` as given
      pipelines      -- one entry per ``*-state.json``, each with ``slug``,
                        ``branch``, ``base_branch``, ``is_current``,
                        ``merge_status`` (see branch_merge_status; ``"active"``
                        for the current branch's own pipeline, which is never
                        probed) and ``closable``
      orphans        -- pipelines not owned by ``current_branch``
      closable       -- orphans whose ``merge_status`` says the work already
                        landed (``merged`` / ``branch-gone``) — the ones to
                        name in a "run /sdd:close" warning
    """
    state_dir = Path(spec_dir) / "_state"
    candidates = sorted(state_dir.glob("*-state.json")) if state_dir.is_dir() else []
    pipelines = []
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        branch = str(data.get("branch") or "")
        base = str(data.get("base_branch") or "")
        is_current = bool(current_branch) and branch == current_branch
        status = "active" if is_current else branch_merge_status(branch, base, git)
        pipelines.append({
            "slug": p.name[: -len("-state.json")],
            "branch": branch,
            "base_branch": base,
            "is_current": is_current,
            "merge_status": status,
            "closable": (not is_current) and status in ("merged", "branch-gone"),
        })
    return {
        "current_branch": current_branch or "",
        "pipelines": pipelines,
        "orphans": [x for x in pipelines if not x["is_current"]],
        "closable": [x for x in pipelines if x["closable"]],
    }


def base_branch(slug, spec_dir=SPECWORK):
    """Return the parent/base branch recorded in state.json, or "" when absent.

    /sdd:close reads this (before it deletes .specwork/) so its branch-cleanup
    dialog knows which branch to switch back to after deleting the feature
    branch. Falls back to "" so the caller can resolve the default branch.
    """
    state_path = Path(spec_dir) / "_state" / f"{slug}-state.json"
    if not state_path.exists():
        return ""
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(state.get("base_branch") or "")


if __name__ == "__main__":
    # precheck takes an optional slug, so it is handled before the slug-required guard.
    if len(sys.argv) >= 2 and sys.argv[1] == "precheck":
        reason = require_specwork()
        if reason:
            print(reason)
            sys.exit(1)
        if len(sys.argv) >= 3:
            pc_slug = sys.argv[2]
            if not Path(f"{SPECWORK}/_state/{pc_slug}-state.json").exists():
                print(f"No state file for '{pc_slug}'. Run /sdd:start first.")
                sys.exit(1)
        sys.exit(0)

    # detect-stack takes no slug, so it is handled before the slug-required guard.
    if len(sys.argv) >= 2 and sys.argv[1] == "detect-stack":
        print(detect_stack())
        sys.exit(0)

    # resolve-slug takes an OPTIONAL branch (not a slug), so handle it early.
    if len(sys.argv) >= 2 and sys.argv[1] == "resolve-slug":
        branch_arg = sys.argv[2] if len(sys.argv) >= 3 else None
        print(resolve_slug(branch_arg))
        sys.exit(0)

    # pipeline-branch-status takes a REQUIRED branch (not a slug) — used by
    # /sdd:pause and /sdd:close to deterministically detect when .specwork/
    # belongs to a different branch, instead of relying on the agent to catch
    # it. Prints one JSON object; always exits 0 (it reports, never gates).
    if len(sys.argv) >= 2 and sys.argv[1] == "pipeline-branch-status":
        if len(sys.argv) < 3:
            print("Usage: gates.py pipeline-branch-status <branch>")
            sys.exit(1)
        print(json.dumps(pipeline_branch_status(sys.argv[2])))
        sys.exit(0)

    # pipeline-inventory takes a REQUIRED branch (not a slug) — used by
    # /sdd:start to distinguish "this branch has an active pipeline, continue
    # it" from "these are leftovers whose MR already merged, close them".
    # Prints one JSON object; always exits 0 (it reports, never gates).
    if len(sys.argv) >= 2 and sys.argv[1] == "pipeline-inventory":
        if len(sys.argv) < 3:
            print("Usage: gates.py pipeline-inventory <branch>")
            sys.exit(1)
        print(json.dumps(pipeline_inventory(sys.argv[2])))
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: gates.py <precheck|detect-stack|resolve-slug|pipeline-branch-status|pipeline-inventory|check-oqs|count-oqs|audit|check-staleness|record-fingerprint|check-artifacts|check-plan-required|risk|risk-signals|consistency|merge-cache|behavioral-signals|worktree-freshness|non-interactive|base-branch> <slug> [args]")
        sys.exit(1)

    command = sys.argv[1]
    slug = sys.argv[2]

    if command == "check-oqs":
        blockers = check_open_questions(slug)
        if blockers:
            for path, oqs in blockers:
                print(f"--- {path}")
                for oq in oqs:
                    print(f"  {oq}")
            sys.exit(1)
        sys.exit(0)
    elif command == "check-staleness":
        result = check_plan_staleness(slug)
        if result and result.get("stale"):
            if result.get("reason") == "mtime":
                print(f"PLAN_STALE reason=mtime spec_mtime={result['spec_mtime']} plan_mtime={result['plan_mtime']}")
            else:
                print("PLAN_STALE reason=fingerprint")
            print(format_staleness_error(slug), file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    elif command == "record-fingerprint":
        # /sdd:plan calls this after writing the plan so staleness is detected by
        # spec content identity, not mtime. Silent no-op if plan/spec missing.
        record_plan_fingerprint(slug)
        sys.exit(0)
    elif command == "count-oqs":
        spec = Path(f"{SPECWORK}/_spec/{slug}-spec.md")
        text = spec.read_text(encoding="utf-8") if spec.exists() else ""
        open_n, resolved_n = count_open_questions(text)
        print(f"{open_n} {resolved_n}")
        sys.exit(0)
    elif command == "audit":
        print(json.dumps(audit_artifacts(slug), indent=2))
        sys.exit(0)
    elif command == "check-artifacts":
        missing = check_required_artifacts(slug)
        if missing:
            for m in missing:
                print(f"Missing: {m}")
            sys.exit(1)
        sys.exit(0)
    elif command == "check-plan-required":
        # Exit 1 (block) when triage marked this high-risk pipeline plan-required
        # and no plan exists yet. /sdd:implement gates on this; passes (exit 0)
        # for every other tier and once a plan is written.
        if plan_required(slug):
            print("PLAN_REQUIRED reason=high-risk")
            sys.exit(1)
        sys.exit(0)
    elif command == "risk":
        spec = Path(f"{SPECWORK}/_spec/{slug}-spec.md")
        if spec.exists():
            hits = risk_signals(spec.read_text(encoding="utf-8"))
            print(json.dumps(hits, indent=2))
    elif command == "risk-signals":
        # Concrete risk-signal labels, one per line; empty output = no signal.
        # /sdd:auto reads this to decide whether to pause for the costly test steps.
        # Distinct from "risk" (JSON with matched terms) — this is the line-oriented
        # form aligned with the local engine risk-signals output.
        spec = Path(f"{SPECWORK}/_spec/{slug}-spec.md")
        if spec.exists():
            hits = risk_signals(spec.read_text(encoding="utf-8"))
            for label in sorted(hits.keys()):
                print(label)
    elif command == "consistency":
        spec = Path(f"{SPECWORK}/_spec/{slug}-spec.md")
        if spec.exists():
            flagged = spec_consistency(spec.read_text(encoding="utf-8"))
            for f in flagged:
                print(f)
    elif command == "merge-cache":
        new_facts = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        merge_cache(slug, new_facts)
        print("Cache updated.")
    elif command == "behavioral-signals":
        spec = Path(f"{SPECWORK}/_spec/{slug}-spec.md")
        plan = Path(f"{SPECWORK}/_plan/{slug}-plan.md")
        signals = behavioral_change_signals(
            spec.read_text(encoding="utf-8") if spec.exists() else "",
            plan.read_text(encoding="utf-8") if plan.exists() else "",
        )
        for s in signals:
            print(s)
    elif command == "worktree-freshness":
        plan = Path(f"{SPECWORK}/_plan/{slug}-plan.md")
        disc = worktree_freshness(str(plan))
        if disc:
            for d in disc:
                print(d)
            sys.exit(1)
        sys.exit(0)
    elif command == "non-interactive":
        print("1" if non_interactive_mode(slug) else "0")
        sys.exit(0)
    elif command == "base-branch":
        print(base_branch(slug))
        sys.exit(0)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
