# Spec Process Usage Log

This document defines a lightweight process log for future evaluation of the SDD workflow.

## Files

Each significant spec may include:

```text
specs/<spec>/
├── worklog.md
└── usage.jsonl
```

## `worklog.md`

Human-readable narrative:

- timeline;
- iterations;
- decisions;
- implementation slices;
- validation;
- lessons learned.

## `usage.jsonl`

Structured event log. Each line is one JSON object.

Recommended fields:

```json
{
  "timestamp": "2026-05-11T14:10:00-03:00",
  "spec": "specs/001-command-model-phase-renaming",
  "tool": "claude",
  "model": "unknown",
  "activity": "review-plan",
  "iteration": "I1",
  "slice": null,
  "tasks": [],
  "input_tokens": null,
  "output_tokens": null,
  "total_tokens": null,
  "token_provenance": "unavailable",
  "duration_minutes": 12,
  "files_changed": ["specs/001-command-model-phase-renaming/plan.md"],
  "commands_run": [],
  "tests_run": [],
  "result": "partial",
  "notes": "Added flake.nix and help-string scope"
}
```

## Token provenance

Use:

- `reported`: tool/model reported token usage.
- `estimated`: usage was estimated using a documented heuristic.
- `unavailable`: usage is not available and not responsibly estimated.

Do not invent token counts. Prefer `unavailable` over false precision.

## Suggested activities

- `spec-created`
- `spec-reviewed`
- `plan-created`
- `plan-reviewed`
- `tasks-generated`
- `tasks-regrouped`
- `slice-implemented`
- `diff-reviewed`
- `audit-run`
- `spec-completed`
- `manual-edit`
- `follow-up-created`

## Minimal logging rule

For large specs, log one entry per meaningful step or slice.

Do not log every prompt, every small typo, or every command unless it is relevant to evaluation.
