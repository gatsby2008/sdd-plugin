---
name: doc-catalog-query
description: Deprecated alias — use /sdd:ask (it searches service catalogs and every other registry). Runs /sdd:ask type:catalog.
argument-hint: "free-text question"
allowed-tools: Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/lib/registry.py:*), Bash(ls:*), Bash(find:*), Bash(grep:*), Bash(cat:*)
---

# doc-catalog-query (deprecated)

This skill is kept so existing habits and notes keep working. It is now
`/sdd:ask type:catalog`.

1. Tell the user once: "`/sdd:doc-catalog-query` is deprecated — use `/sdd:ask` (add `type:catalog`
   only to restrict it to service catalogs)."
2. Then follow `${CLAUDE_PLUGIN_ROOT}/skills/ask/SKILL.md` exactly, running Step 1 as:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/registry.py ask "type:catalog $ARGUMENTS"
```
