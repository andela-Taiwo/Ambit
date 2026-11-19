# 16. Accessible primitives, not a component framework

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

The plan expects accessible UI primitives (focus, labels, keyboard). Adding a
large component library for a small personal app would be unnecessary weight.

## Decision

- Build a small set of native primitives in `src/components/ui.tsx`: labelled
  inputs, dialog with focus trap/Escape/restore, alerts with `role=alert|status`,
  progress bars with ARIA values, pagination navigation, badges and empty states.
- Never rely on placeholder text as a label; every control has an associated
  `<label>` and errors are linked with `aria-describedby`.
- Charts render an SVG image plus a screen-reader-accessible data table.
- Tables use `<th scope>`, landmarks are labelled, and the shell provides a skip
  link.

## Consequences

- Accessibility behaviour is explicit and unit-tested (modal escape/focus,
  labels/errors, progress values, chart tables).
- Future UI work reuses these primitives instead of introducing parallel styles.
