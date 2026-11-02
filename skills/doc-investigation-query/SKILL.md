---
name: doc-investigation-query
description: Deprecated alias — use /sdd:ask (it searches investigations and every other registry). Runs /sdd:ask type:investigation.
argument-hint: "free-text question"
allowed-tools: Read, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/lib/registry.py:*), Bash(ls:*), Bash(find:*), Bash(grep:*), Bash(cat:*)
---

# doc-investigation-query (deprecated)

This skill is kept so existing habits and notes keep working. It is now
`/sdd:ask type:investigation`.

1. Tell the user once: "`/sdd:doc-investigation-query` is deprecated — use `/sdd:ask` (add `type:investigation`
   only to restrict it to investigations)."
2. Then follow `${CLAUDE_PLUGIN_ROOT}/skills/ask/SKILL.md` exactly, running Step 1 as:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/registry.py ask "type:investigation $ARGUMENTS"
```
