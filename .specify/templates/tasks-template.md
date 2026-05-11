---
description: "Slice-first task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`  
**Prerequisites**: `spec.md`, `plan.md`; optionally `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

## Task Format

`[ID] [P?] [Slice] Description`

- **[P]**: can run in parallel because it touches disjoint files and has no dependency on another in-flight task.
- **[Slice]**: implementation slice ID from `plan.md`, e.g., `[S1]`.
- Include exact file paths where possible.
- All tasks should be provider-free unless explicitly approved.

## Execution Rules

- Implement one slice at a time.
- Do not implement all tasks at once.
- Do not create a large failing test suite up front when red/green by slice is safer.
- Add tests with the implementation slice they validate.
- End each slice with a green checkpoint.
- Commit after each green slice, not after every individual task.
- Do not perform opportunistic refactors.

---

## Slice S1 — [Name]

**Goal**: [small goal]  
**Validation**: [focused tests/checks]  
**Depends on**: [dependency]  
**Suggested commit**: `[type]: [message]`

### Tasks

- [ ] T001 [S1] [description with exact path]
- [ ] T002 [S1] [description with exact path]
- [ ] T003 [S1] [description with exact path]

### Checkpoint

- [ ] focused tests/checks pass
- [ ] no provider-backed execution
- [ ] no opportunistic refactor
- [ ] diff is reviewable
- [ ] `worklog.md` updated if this is Level 2/3

---

## Slice S2 — [Name]

**Goal**: [small goal]  
**Validation**: [focused tests/checks]  
**Depends on**: [dependency]  
**Suggested commit**: `[type]: [message]`

### Tasks

- [ ] T004 [S2] [description with exact path]
- [ ] T005 [S2] [description with exact path]

### Checkpoint

- [ ] focused tests/checks pass
- [ ] no provider-backed execution
- [ ] no opportunistic refactor
- [ ] diff is reviewable
- [ ] `worklog.md` updated if this is Level 2/3

---

## Final Audit

- [ ] TXXX [Audit] Run focused provider-free verification from `plan.md`.
- [ ] TXXX [Audit] Update `worklog.md` with final validation and lessons learned.
- [ ] TXXX [Audit] Update `usage.jsonl` for major iterations if usage data is available or explicitly unavailable.
- [ ] TXXX [Audit] Record follow-ups for deferred findings.

## Dependencies and Execution Order

- S1 before S2 if S2 depends on S1 outputs.
- Independent slices may run in parallel only when they touch disjoint files and tests.
- Final audit depends on all selected slices being complete.

## Provider and Cost Controls

- Do not run real provider-backed `ctxbench execute` or `ctxbench eval`.
- Provider adapter tests must use fake clients, mocked SDK objects, or pure payload-building helpers.
- Quickstart verification must use a mock-only fixture and must not require API keys, provider tokens, or network access.
