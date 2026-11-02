# Spec Registry

Store a feature `spec.md` in the central spec registry so `/sdd:ask` can read
it. This is the **registry side** of the spec lifecycle (authoring is still
`/sdd:spec`) and the **standalone / vibe-coding** counterpart to the SDD pipeline's
`/sdd:mr`, which already publishes specs automatically when a `.specwork/` artifact
exists.

## When to use it

- You wrote a spec by hand (or outside the SDD pipeline) and want it queryable.
- You want to re-store an existing `.specwork` spec without re-running `/sdd:mr`.

If you ran the pipeline through `/sdd:mr`, the spec is already stored — you do not
need this skill.

## Usage

```bash
/sdd:doc-spec docs/my-feature-spec.md   # store a specific spec file
/sdd:doc-spec                           # auto-detect the active .specwork spec
/sdd:doc-spec list                      # list specs registered for this repo's service
```

The spec is copied to `spec-registry/<service>/<slug>-spec.md` under
`$CLAUDE_DOC_HOME` (default `~/.claude/`). The `<service>` key is resolved the same
way `/sdd:doc-catalog` and `/sdd:doc-adr` resolve it, so all registries stay aligned.

## Notes

- **Store-only.** It copies the file verbatim — it never generates a spec from
  your diff and never rewrites your content.
- The destination filename always ends in `-spec.md` (that is what `/sdd:ask`
  discovers).
- For richer query answers, the spec should follow the canonical SDD sections
  (`## Summary`, `## Behavior`, `## Scope`, `## Implementation Context`,
  `## Safe Constraints`, `## Open Questions`), but they are not required.

See `SKILL.md` for the full step-by-step behavior.
