#!/usr/bin/env python3
"""
plan.py — consolidated discovery engine for /sdd:plan.

Reads the spec, runs all heuristics and gates, and outputs a JSON
summary that the LLM uses to write the plan.md.

Usage:
  python3 plan.py <slug>

Output:
  JSON with: open_questions_blocked, stack, target_files, risk_signals,
             consistency_issues, cache_updates, plan_oqs
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from gates import (
    check_open_questions,
    check_required_artifacts,
    detect_stack,
    merge_cache,
    risk_signals as detect_risk_signals,
    spec_consistency as detect_consistency,
    section_text,
)


def _own_service():
    """This repo's registry key, via the shared resolver in lib/service-name.sh."""
    lib = Path(__file__).resolve().parent / "service-name.sh"
    try:
        out = subprocess.run(["bash", "-c", '. "$1" && resolve_service_name', "_", str(lib)],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def cross_service_impact(spec_text):
    """`## Cross-Service Impact` markdown from the other services' catalogs."""
    try:
        from registry import render_impact
        return render_impact(spec_text, _own_service())
    except Exception:
        return "## Cross-Service Impact\n\n_Impact not checked (registry unreadable)._\n"


def find_mock_consumer_tests(stack, target_files):
    """For Java, find test files that reference target service classes."""
    if stack != "java":
        return []

    tests = []
    for tf in target_files:
        path = tf.get("path", "")
        if not path.endswith(".java"):
            continue
        class_name = Path(path).stem
        # Find test files referencing this class (-F: class_name is a literal)
        try:
            result = subprocess.run(
                ["grep", "-rlF", class_name, "src/test", "src/intTest"],
                capture_output=True, text=True, check=False, timeout=30,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line != path:
                    tests.append(line)
        except Exception:
            pass

    return list(set(tests))


def find_http_status_in_spec(spec_text):
    """Extract HTTP status codes mentioned in the spec."""
    return re.findall(r"\b(40[0-9]|50[0-9]|201|204|30[0-9])\b", spec_text)


def reference_grep(spec_text):
    """Grep the codebase for concrete symbols the spec says to rename/remove/replace.

    Only fires when the spec uses rename/remove/replace/deprecate/delete language,
    and only extracts symbols from those specific lines. Additive mentions of a
    symbol do not trigger reference-update tagging — that would falsely flag every
    existing file referenced in the spec.

    Guards against over-matching (the 2026-05-29 consumer-portal blow-up, where a
    3-file change produced dozens of false-positive [reference-update] targets):
      1. Skip the "## Safe Constraints" section — it documents what to PRESERVE.
      2. Skip negated lines ("Do NOT remove the `@Size` constraint").
      3. Cap hits per symbol — a generic token matching many files is not a
         targeted rename. Tunable via CLAUDE_TOOLS_REF_HIT_CAP (default 8).
    """
    trigger = re.compile(
        r"\b(renam\w*|remov\w*|delet\w*|deprecat\w*|replac\w*|migrat\w*|drop)\b",
        re.IGNORECASE,
    )
    negation = re.compile(
        r"\b(?:not|never|without|keep|keeps|keeping|kept|preserv\w*|retain\w*|"
        r"maintain\w*|unchanged|untouched|intact)\b|n't",
        re.IGNORECASE,
    )
    symbols = set()
    in_safe_constraints = False
    for line in spec_text.splitlines():
        m = re.match(r"^\s*##\s+(.*)", line)
        if m:                                    # guard 1: track section
            in_safe_constraints = m.group(1).strip().lower().startswith("safe constraints")
            continue
        if in_safe_constraints:
            continue
        if not trigger.search(line):
            continue
        if negation.search(line):                # guard 2: skip negated lines
            continue
        symbols.update(re.findall(r"`([^`]+)`", line))     # `Symbol`
        symbols.update(re.findall(r"(/\w[\w/_-]*)", line))  # /api/v1/path

    candidates = [s for s in symbols if len(s) >= 3][:10]
    if not candidates:
        return []

    hit_cap = int(os.environ.get("CLAUDE_TOOLS_REF_HIT_CAP", "8"))  # guard 3
    refs = set()
    source_exts = (".java", ".kt", ".ts", ".tsx")
    for term in candidates:
        # -F: terms may contain regex metachars (List<String>, foo(), a.b.c).
        # No --include: busybox grep (Alpine CI) doesn't support it, so filter
        # to source extensions in Python instead.
        try:
            result = subprocess.run(
                ["grep", "-rlF", term, "src/"],
                capture_output=True, text=True, check=False, timeout=15,
            )
            hits = [line.strip() for line in result.stdout.splitlines()
                    if line.strip().endswith(source_exts)]
            if len(hits) > hit_cap:              # guard 3: too generic, skip
                continue
            refs.update(hits)
        except Exception:
            pass

    return sorted(refs)[:10]


def get_existing_tests(prod_path, stack):
    """Find existing test files for a production file."""
    if stack == "java":
        base = Path(prod_path).stem
        # Try test dirs
        test_dirs = ["src/test/java", "src/intTest/java", "src/integrationTest/java"]
        tests_found = []
        for td in test_dirs:
            candidate = Path(td) / f"{base}Test.java"
            if candidate.exists():
                tests_found.append(str(candidate))
            candidate = Path(td) / f"{base}IT.java"
            if candidate.exists():
                tests_found.append(str(candidate))
        return tests_found
    if stack in ("node", "frontend"):
        prod = Path(prod_path)
        if prod.suffix not in (".ts", ".tsx", ".js", ".jsx"):
            return []
        base = prod.stem
        ext = prod.suffix
        parent = prod.parent
        tests_found = []
        # Sibling: <stem>.test.<ext>, <stem>.spec.<ext>
        for suffix in (".test", ".spec"):
            candidate = parent / f"{base}{suffix}{ext}"
            if candidate.exists():
                tests_found.append(str(candidate))
        # __tests__/<stem>.test.<ext>, __tests__/<stem>.spec.<ext>
        tests_dir = parent / "__tests__"
        if tests_dir.is_dir():
            for suffix in (".test", ".spec"):
                candidate = tests_dir / f"{base}{suffix}{ext}"
                if candidate.exists():
                    tests_found.append(str(candidate))
        return tests_found
    return []


def main():
    if len(sys.argv) < 2:
        print("Usage: plan.py <slug>", file=sys.stderr)
        sys.exit(1)

    slug = sys.argv[1]
    spec_dir = Path(".specwork")
    spec_file = spec_dir / "_spec" / f"{slug}-spec.md"
    state_file = spec_dir / "_state" / f"{slug}-state.json"
    plan_dir = spec_dir / "_plan"

    result = {
        "slug": slug,
        "open_questions_blocked": False,
        "stack": detect_stack(),
        "target_files": [],
        "risk_signals": {},
        "consistency_issues": [],
        "plan_oqs": [],
        "cache_updates": {"repositories": [], "related_tests": []},
        "infra_hints": [],
        "cross_service_impact_md": "",
        "errors": [],
    }

    # ---- Pre-flight gates ----
    missing = check_required_artifacts(slug)
    if missing:
        result["errors"].append(f"Missing artifacts: {', '.join(missing)}")
        print(json.dumps(result, indent=2))
        sys.exit(0)

    blockers = check_open_questions(slug)
    if blockers:
        result["open_questions_blocked"] = True
        result["errors"].append("Unresolved Open Questions block planning")
        print(json.dumps(result, indent=2))
        sys.exit(0)

    # ---- Load spec ----
    spec_text = spec_file.read_text(encoding="utf-8")

    # ---- Extract candidates from Implementation Context ----
    impl_ctx = section_text(spec_text, "Implementation Context")
    behavior = section_text(spec_text, "Behavior")
    scope = section_text(spec_text, "Expected Change Scope")

    candidates = set()
    for line in impl_ctx.splitlines():
        line = line.strip()
        if line.startswith("-"):
            line = line.lstrip("- ").strip()
        # Extract paths and class names
        if "/" in line or ".java" in line or ".ts" in line:
            candidates.add(line.split()[0].strip("`").strip())
        elif re.match(r"^[A-Z][A-Za-z0-9]+", line):
            # Probable class name
            candidates.add(line.split(",")[0].strip().strip("`"))

    result["candidates"] = list(candidates)

    # ---- Detect risk signals ----
    result["risk_signals"] = detect_risk_signals(spec_text)

    # ---- Spec consistency check ----
    result["consistency_issues"] = detect_consistency(spec_text)

    # ---- Build target files ----
    target_files = []
    stack = result["stack"]

    for candidate in sorted(candidates):
        entry = {
            "path": candidate,
            "change": "",
            "tags": [],
        }
        # Check for existing tests
        existing_tests = get_existing_tests(candidate, stack)
        if existing_tests:
            entry["existing_tests"] = existing_tests

        # Check for risk
        for signal, matches in result["risk_signals"].items():
            candidate_lower = candidate.lower()
            if signal in candidate_lower or any(m in candidate_lower for m in matches):
                entry["tags"].append(f"risk:{signal}")

        target_files.append(entry)

    # Mock-consumer detection
    mock_tests = find_mock_consumer_tests(stack, target_files)
    for mt in mock_tests:
        target_files.append({
            "path": mt,
            "change": "[mock-consumer] Update mocks to match new signature",
            "tags": ["mock-consumer"],
        })

    # HTTP status hints
    http_codes = find_http_status_in_spec(spec_text)
    if http_codes:
        result["infra_hints"] = [
            f"HTTP {code} detected — may need handler update" for code in sorted(set(http_codes))
        ]

    # Reference grep
    refs = reference_grep(spec_text)
    for ref in refs:
        target_files.append({
            "path": ref,
            "change": "[reference-update] Update reference",
            "tags": ["reference-update"],
        })

    result["target_files"] = target_files

    # ---- Cross-service impact (read-only; never blocks the plan) ----
    result["cross_service_impact_md"] = cross_service_impact(spec_text)

    # ---- Plan OQs from consistency ----
    for i, issue in enumerate(result["consistency_issues"], 1):
        result["plan_oqs"].append(f"**#{i}** Spec suggests \"{issue}\" — confirm intent or clarify")

    # ---- Cache updates ----
    cache = {"repositories": [], "related_tests": []}
    for tf in target_files:
        p = tf.get("path", "")
        if p and Path(p).exists():
            # Guess repository
            if "/repository/" in p or p.endswith("Repository.java"):
                cache["repositories"].append(p)
            # Test files
            if "test" in p or "Test" in p:
                cache["related_tests"].append(p)

    result["cache_updates"] = {
        "repositories": list(set(cache["repositories"])),
        "related_tests": list(set(cache["related_tests"])),
    }

    # ---- Persist cache to disk (degrade gracefully if cache is unreadable) ----
    try:
        merge_cache(slug, result["cache_updates"], str(spec_dir))
    except Exception:
        pass

    # ---- Ensure plan dir exists ----
    plan_dir.mkdir(parents=True, exist_ok=True)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
