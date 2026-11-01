#!/usr/bin/env python3
"""Promote durable rules from a closed spec into a service-rules file, append-only.

``/sdd:close`` proposes candidate rules from the spec; the user approves each
one; this module performs the write. The guarantee lives here, in code, not in
prose: rules files mix hand-written business rules and design rationale, so
every pre-existing line must survive byte-for-byte and in order. ``apply``
only ever *inserts* lines and refuses to write if the result is anything else.

Each inserted bullet carries a provenance marker so promoted rules stay
distinguishable from hand-written ones::

    - <rule> _(from spec <slug>, <YYYY-MM-DD>)_

CLI:
  python3 promote.py apply <rules-file> <slug> '<json>'
      <json> = [{"section": "Business Invariants", "rule": "..."}, ...]
      exit 0 on success (prints inserted count), 1 on a rejected write, 2 on usage error
"""
import datetime
import difflib
import json
import re
import sys
from pathlib import Path

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET = re.compile(r"^[-*]\s")


def bullet(rule, slug, date):
    return "- {} _(from spec {}, {})_".format(rule.strip(), slug, date)


def _find_section(lines, section):
    """(start, end, level) of the heading named ``section``; end is exclusive. None if absent."""
    wanted = section.strip().lstrip("#").strip().lower()
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and m.group(2).lower() == wanted:
            level = len(m.group(1))
            end = len(lines)
            for j in range(i + 1, len(lines)):
                n = _HEADING.match(lines[j])
                if n and len(n.group(1)) <= level:
                    end = j
                    break
            return i, end, level
    return None


def _insertion_point(lines, start, end):
    """After the section's last bullet (and its indented continuation), else after its last non-blank line."""
    last_bullet = None
    for i in range(start + 1, end):
        if _BULLET.match(lines[i]):
            last_bullet = i
    if last_bullet is not None:
        i = last_bullet + 1
        while i < end and lines[i].startswith((" ", "\t")) and lines[i].strip():
            i += 1
        return i
    i = end
    while i > start + 1 and not lines[i - 1].strip():
        i -= 1
    return i


def insert_rules(text, entries, slug, date):
    """Return ``text`` with each entry's rule inserted at the end of its section."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    for entry in entries:
        new_line = bullet(entry["rule"], slug, date)
        found = _find_section(lines, entry["section"])
        if found is None:
            while lines and not lines[-1].strip():
                lines.pop()
            heading = "## " + entry["section"].strip().lstrip("#").strip()
            lines.extend(([""] if lines else []) + [heading, "", new_line])
            continue
        start, end, _ = found
        at = _insertion_point(lines, start, end)
        lines.insert(at, new_line)
    return newline.join(lines) + newline


def only_insertions(old, new):
    """True when ``new`` keeps every line of ``old`` unchanged and in order."""
    matcher = difflib.SequenceMatcher(a=old.splitlines(), b=new.splitlines(), autojunk=False)
    return all(tag in ("equal", "insert") for tag, *_ in matcher.get_opcodes())


def apply(path, slug, entries, date=None):
    """Write the approved entries into ``path``. Returns the number inserted; raises ValueError on rejection."""
    date = date or datetime.date.today().isoformat()
    entries = [e for e in entries if str(e.get("rule", "")).strip() and str(e.get("section", "")).strip()]
    if not entries:
        return 0
    p = Path(path)
    old = p.read_bytes().decode("utf-8") if p.exists() else ""
    new = insert_rules(old, entries, slug, date)
    if not only_insertions(old, new):
        raise ValueError("refusing to write {}: an existing line would change".format(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(new.encode("utf-8"))
    return len(entries)


def _main(argv):
    if len(argv) != 4 or argv[0] != "apply":
        sys.stderr.write("Usage: promote.py apply <rules-file> <slug> '<json>'\n")
        return 2
    _, path, slug, raw = argv
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError("expected a JSON list")
    except ValueError as exc:
        sys.stderr.write("✗ Invalid JSON: {}\n".format(exc))
        return 2
    try:
        count = apply(path, slug, entries)
    except ValueError as exc:
        sys.stderr.write("✗ {}\n".format(exc))
        return 1
    print("✓ Promoted {} rule(s) into {}".format(count, path))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
