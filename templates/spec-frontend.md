# <id> — <Title>

> Source: <JIRA: TICKET | Free text>

## Summary

One or two sentences describing what this UI feature does for the user.

## Scope

### In scope
- What the feature will do (screens, flows, interactions)

### Out of scope
- What the feature will NOT do

## Behavior

1. **B1** — Detailed, testable behavioral requirement — user-visible interactions,
   states (loading / empty / error / success), and validation.

## Components
- Component tree and each component's responsibility.
- New vs. reused components; where they mount.

## Props & State
- **Inputs (props)**: data each component receives.
- **Local state**: component-owned state.
- **Shared/global state**: store slices, context, or query cache touched.
- **Data fetching**: endpoints called, loading/error handling.

## Routes
- Paths added or changed, route params, and navigation guards.
- Lazy-loading / code-split boundaries, if any.

## Design Reference
- Figma / mockup links, design-system components and tokens to use.
- Responsive breakpoints and any visual states to match.

## Accessibility Requirements
- Semantic structure, ARIA roles/labels, focus management.
- Keyboard navigation and screen-reader expectations.
- Color-contrast and motion-reduction considerations.

## Implementation Context
- Files, components, hooks, stores, routes, and services relevant to this feature.

## Expected Change Scope
- **Expected files touched**: <count or range>
- **Expected layers**: <components / hooks / store / routing / styles / …>
- **Avoid touching**:
  - <areas that must not change>

## Safe Constraints
**Safe**:
- Things the implementation MUST be free to do

**Unsafe**:
- Things the implementation MUST NOT do

## Open Questions

- [ ] **#1** *Every unresolved ambiguity you would otherwise have to guess.*
