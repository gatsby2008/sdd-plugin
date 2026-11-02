---
name: doc-spec-query
description: Deprecated alias — use /sdd:ask (it searches specs and every other registry). Runs /sdd:ask type:spec.
argument-hint: "free-text question"
allowed-tools: Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/lib/registry.py:*), Bash(ls:*), Bash(find:*), Bash(grep:*), Bash(cat:*)
---

# doc-spec-query (deprecated)

This skill is kept so existing habits and notes keep working. It is now
`/sdd:ask type:spec`.

1. Tell the user once: "`/sdd:doc-spec-query` is deprecated — use `/sdd:ask` (add `type:spec`
   only to restrict it to specs)."
2. Then follow `${CLAUDE_PLUGIN_ROOT}/skills/ask/SKILL.md` exactly, running Step 1 as:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/registry.py ask "type:spec $ARGUMENTS"
```
