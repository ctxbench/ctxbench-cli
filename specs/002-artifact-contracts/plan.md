# Plan: [FEATURE]

**Branch**: `[branch-name]` | **Date**: [DATE] | **Spec**: [link]  
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

## Summary

[One short paragraph describing the intended change and implementation approach.]

## Decisions

- [decision]
- [decision]

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: pyproject.toml, flake.nix  
**Storage**: local JSON/JSONL/CSV artifacts when relevant  
**Testing**: pytest, provider-free fixtures/mocks  
**Target Platform**: CLI  
**Project Type**: single Python CLI project  
**Constraints**: provider-free validation; no full benchmark unless explicitly approved  
**Scale/Scope**: [small/medium/large, with reason]

## Constitution Check

Check only gates relevant to this spec. Do not repeat irrelevant gates verbosely.

| Gate | Status | Notes |
|---|---|---|
| Phase separation | pass / n/a / risk | [notes] |
| Cost/evaluation separation | pass / n/a / risk | [notes] |
| Metric provenance | pass / n/a / risk | [notes] |
| Artifact contracts | pass / n/a / risk | [notes] |
| Strategy comparability | pass / n/a / risk | [notes] |
| Dataset/domain isolation | pass / n/a / risk | [notes] |
| Provider isolation | pass / n/a / risk | [notes] |
| Provider-free validation | pass / n/a / risk | [notes] |
| Documentation impact | pass / n/a / risk | [notes] |
| Simplicity / research sufficiency | pass / n/a / risk | [notes] |

## Files Likely Affected

- [file/path]
- [file/path]

## Implementation Slices

The plan MUST propose small implementation slices before task generation.

Each slice should be independently reviewable and should end in a green checkpoint.

| Slice | Goal | Likely files | Validation | Depends on |
|---|---|---|---|---|
| S1 | [goal] | [files] | [tests/checks] | [dependency] |
| S2 | [goal] | [files] | [tests/checks] | [dependency] |

Slice rules:

- Prefer 3–7 tasks per slice.
- A slice must not mix unrelated concerns.
- A slice must not require provider-backed execution.
- A slice should end with focused tests or an explicit audit.
- If the spec is large, tasks MUST be grouped under these slices.
- Prefer one commit per green slice, not one commit per task.

## Process Logging

For Level 2 or Level 3 changes, create or update process logs in the spec directory:

- `worklog.md` for human-readable process history.
- `usage.jsonl` for structured process metrics, if useful.

Keep logging light:

- record one entry per meaningful step, review, slice, audit, or decision;
- do not log every small prompt;
- token fields may be `unavailable` when tools do not report usage;
- distinguish reported, estimated, and unavailable usage.

## Risks

- [risk]
- [risk]

## Validation

Provider-free validation:

- [command/check]
- [command/check]

No real provider-backed command should be required unless explicitly approved.

## Complexity Tracking

Fill only if the plan knowingly violates a constitution gate.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| _(none)_ | _(n/a)_ | _(n/a)_ |
