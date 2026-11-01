"""Guard: this repo must be self-contained.

It must not carry references to the shared origin repo, to the parallel
shell-based variant, or to the origin's obsolete installer mechanism — those
couplings are exactly what moving to a standalone project removed. This test
scans every **git-tracked** text file and fails if a forbidden token appears
anywhere (e.g. a doc still pointing at the origin's old per-tool installer
instead of this plugin's namespaced /sdd:* commands).

Only tracked files are checked because they are what ships in the published
plugin. Gitignored scratch (e.g. a machine-local settings.local.json) may
legitimately name the origin and is not part of the distribution. Outside a git checkout, the test falls back to walking
the tree.

The forbidden tokens are assembled from fragments on purpose, so this guard file
does not itself contain the literal strings it searches for — which means it can
scan its own tree without a self-exclusion and the result is a true "zero
occurrences anywhere" check.
"""

import os
import subprocess
import unittest
from pathlib import Path

# Repo layout: lib/tests/<this file> -> repo root is 2 dirs up.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Built from fragments so the literal substrings never appear in this source.
FORBIDDEN = (
    # origin repo + parallel variant
    "claude" + "-tools",
    "open" + "-sdd",
    "open" + "sdd",  # catches the no-hyphen / dotfile form too
    # origin's obsolete installer mechanism (this is a plugin — /plugin install)
    "update" + ".sh",
    "update" + ".ps1",
    "--core" + "-only",
    "." + "deps",
)

SKIP_DIRS = {".git", "__pycache__", ".idea", ".pytest_cache", "node_modules"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".zip", ".gz", ".pyc"}


def _git_tracked_files(root):
    """Tracked file paths relative to root, or None outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [p for p in out.split("\0") if p]


def _iter_text_files(root):
    tracked = _git_tracked_files(root)
    if tracked is not None:
        for rel in tracked:
            path = root / rel
            if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
                continue
            yield path
        return
    # Fallback: not a git checkout — walk the tree.
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            yield path


class SelfContainedTest(unittest.TestCase):
    def test_no_forbidden_references(self):
        offenders = []
        for path in _iter_text_files(REPO_ROOT):
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable — nothing to check
            for lineno, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                for token in FORBIDDEN:
                    if token in low:
                        rel = path.relative_to(REPO_ROOT)
                        offenders.append(f"{rel}:{lineno}: {token}")

        self.assertEqual(
            offenders,
            [],
            "Repo must be self-contained — remove these cross-references:\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
