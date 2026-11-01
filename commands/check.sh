#!/usr/bin/env bash
#
# Project validation script consumed by /sdd:mr (before push).
#   exit 0  → clean, continue (push)
#   exit !0 → stop, do not push
#
# This repo is the SDD plugin itself: Python helpers under lib/ plus markdown
# skills. Validation = the lib unit suite + the end-to-end smoke script.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== unit tests (lib/tests) =="
( cd lib && python3 -m unittest discover -s tests -p 'test_*.py' )

echo "== smoke =="
bash lib/tests/smoke.sh
