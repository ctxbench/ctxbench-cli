# Tasks: Artifact Contracts

**Input**: Design documents from `specs/002-artifact-contracts/`
**Prerequisites**: `spec.md`, `plan.md`, `research.md`

## Task Format

`- [ ] T### [P?] [S?] Description with file path`

- **[P]**: can run in parallel (touches disjoint files, no dependency on another in-flight task).
- **[S#]**: implementation slice from `plan.md`.
- All tasks are provider-free.

## Execution Rules

- Implement one slice at a time; do not start S2 or S3 before S1 is checkpointed.
- S3 is optional — only execute it if a decision is made to include contract tests.
- End each slice with a green checkpoint before committing.
- Commit after each green slice, not after individual tasks.
- Do not perform opportunistic refactors.

---

## Slice S1 — Reference document

**Goal**: Create `docs/architecture/artifact-contracts.md` satisfying FR-001 through FR-014.
**Validation**: Read file against acceptance checklist — 9 artifacts with phase+class, 4 role sections, 5 provenance classes with rules, 3 legacy mappings with no-alias wording.
**Depends on**: —
**Suggested commit**: `docs(arch): add artifact-contracts reference`

### Tasks

- [x] T001 [S1] Create `docs/architecture/artifact-contracts.md` with a phase-lifecycle table listing all nine canonical artifacts (`manifest.json`, `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, `results.csv`, `traces/executions/<trialId>.json`, `traces/evals/<trialId>.json`), each row showing producing phase and class (canonical/derived) — FR-001, FR-002
- [x] T002 [S1] Add four named role sections to `docs/architecture/artifact-contracts.md`: Execution Artifacts, Evaluation Artifacts, Analysis-Ready Exports, Traces — with each artifact assigned to exactly one role — FR-003
- [x] T003 [S1] Within the Execution Artifacts section, describe `manifest.json` explicitly as a plan-phase canonical artifact whose content is sufficient to reproduce subsequent phases — FR-004; describe canonical/derived distinction and state that `results.csv` and `evals-summary.json` are derived artifacts reproducible without re-running providers — FR-005, FR-006
- [x] T004 [S1] Add a metric provenance taxonomy section to `docs/architecture/artifact-contracts.md` with all five class definitions (`reported`, `measured`, `derived`, `estimated`, `unavailable`); include the following explicit rule statements: (a) `estimated` MUST NOT be presented as `reported` or `measured`; (b) `unavailable` MUST NOT be recorded as zero unless zero is the observed value; (c) this taxonomy is closed in this spec — no sub-classes or extensions — FR-011, FR-012, FR-013, FR-014
- [x] T005 [S1] Add a legacy migration section to `docs/architecture/artifact-contracts.md` with a table mapping `queries.jsonl` → `trials.jsonl`, `answers.jsonl` → `responses.jsonl`, `traces/queries/<runId>.json` → `traces/executions/<trialId>.json`; each entry must include an explicit no-alias statement; include a sentence stating migration is the researcher's responsibility — FR-007, FR-010
- [x] T006 [S1] Add a reader/writer policy section to `docs/architecture/artifact-contracts.md` with two rules: writers produce only target artifact names; readers encounter legacy files silently (not an error, not consumed) — FR-008, FR-009
- [x] T007 [S1] Validate S1 against the acceptance checklist in `plan.md` using `sed -n '1,260p' docs/architecture/artifact-contracts.md`: confirm (a) all nine artifacts are present and each has phase + class labeling; (b) the four role treatments are present; (c) `manifest.json` is described as plan-phase canonical with reproduction-oriented responsibility; (d) `results.csv` and `evals-summary.json` are explicitly derived and reproducible without provider re-runs; (e) all three legacy mappings use explicit no-alias wording and migration responsibility language; (f) exactly five provenance classes are defined with FR-013/FR-014 rule statements; (g) no field-level schemas are included
- [x] T008 [S1] Update `specs/002-artifact-contracts/worklog.md` with an S1 completion entry (date, what was written, any decisions made)

### Checkpoint

- [x] All nine canonical artifacts named with phase and class in `artifact-contracts.md`
- [x] Five provenance classes defined with FR-013/FR-014 rule statements present
- [x] Three legacy mappings with explicit no-alias wording present
- [x] No field-level schemas, format versions, or validation tooling described in the file
- [x] No provider-backed execution required to validate
- [x] `worklog.md` updated

---

## Slice S2 — Architecture doc consistency

**Goal**: Keep architecture documentation internally consistent with `artifact-contracts.md` and the current implementation — including `evals-summary.json` in eval-phase outputs.
**Validation**: `rg "artifact-contracts" docs/architecture/` returns ≥3 hits; README.md and workflow.md agree on eval outputs.
**Depends on**: S1
**Suggested commit**: `docs(arch): align architecture docs with artifact contracts`

### Tasks

- [ ] T009 [P] [S2] In `docs/architecture/README.md`: add `artifact-contracts.md` to the documentation structure table with a one-line description
- [ ] T010 [P] [S2] In `docs/architecture/README.md`: update the canonical workflow diagram/text so the eval-phase output line includes `evals-summary.json`; add a one-sentence pointer to `artifact-contracts.md` in the "Historical migration reference" section
- [ ] T011 [P] [S2] In `docs/architecture/workflow.md`: update the Mermaid flowchart node for `ctxbench eval` and the Evaluation prose section so both include `evals-summary.json` in the listed outputs — make eval outputs agree with `artifact-contracts.md`
- [ ] T012 [P] [S2] In `docs/architecture/vocabulary.md`: add one sentence after the "Historical migration reference" heading pointing readers to `docs/architecture/artifact-contracts.md` as the authoritative artifact reference
- [ ] T013 [P] [S2] In `docs/architecture/cli-architecture.md`: add one sentence in the migration section pointing readers to `docs/architecture/artifact-contracts.md` as the authoritative artifact reference
- [ ] T014 [S2] Validate S2: run `rg "artifact-contracts" docs/architecture/` (expect ≥3 hits); read the eval-phase output in README.md and workflow.md to confirm they agree and both include `evals-summary.json`; confirm the architecture document index lists `artifact-contracts.md`; confirm migration tables remain labeled as historical/migration-only context
- [ ] T015 [S2] Update `specs/002-artifact-contracts/worklog.md` with an S2 completion entry

### Checkpoint

- [ ] `rg "artifact-contracts" docs/architecture/` returns ≥3 hits
- [ ] README.md and workflow.md eval outputs both include `evals-summary.json`
- [ ] Migration tables in vocabulary.md, README.md, and cli-architecture.md each carry a pointer to `artifact-contracts.md`
- [ ] No provider-backed execution required
- [ ] `worklog.md` updated

---

## Slice S3 — Internal cleanup with contract tests *(optional)*

**Goal**: Remove six unused internal legacy path aliases from `paths.py`, backed by focused contract tests that prove FR-008/FR-009 at the code level. Execute this slice only if it remains in scope per plan decision.
**Validation**: Focused pytest tests green; `rg` confirms all six function names are gone from `src/`.
**Depends on**: S1
**Suggested commit**: `refactor(paths): remove unused legacy artifact name aliases`

### Tasks

- [ ] T016 [S3] Audit callers of the six target functions in `src/`: run `rg "resolve_queries_path|resolve_answers_path|resolve_run_jsonl_path|resolve_eval_jsonl_path|resolve_run_output_dir|resolve_eval_output_dir" src/` and confirm no hits outside `src/ctxbench/benchmark/paths.py` before touching any code
- [ ] T017 [S3] Add focused contract tests in `tests/test_artifact_contracts.py` for writer behavior: verify plan/execution path construction or command-level write targets use only `trials.jsonl`, `responses.jsonl`, and other target artifact names, never `queries.jsonl` or `answers.jsonl`
- [ ] T018 [S3] Add focused contract tests in `tests/test_artifact_contracts.py` for reader behavior: verify command-level readers such as status/export/eval consume target artifact names and ignore legacy-named files when target files are present in the same directory — FR-009 edge case coverage
- [ ] T019 [S3] Remove the six unused legacy alias functions from `src/ctxbench/benchmark/paths.py`: `resolve_queries_path`, `resolve_answers_path`, `resolve_run_jsonl_path`, `resolve_eval_jsonl_path`, `resolve_run_output_dir`, `resolve_eval_output_dir`; keep `resolve_expand_output_dir` and `resolve_expand_jsonl_path` (still used by `commands/experiment.py`)
- [ ] T020 [S3] Validate S3: `pytest -k "legacy_rejection or artifact_contracts or status or export or eval"` passes; `rg "resolve_queries_path|resolve_answers_path|resolve_run_jsonl_path|resolve_eval_jsonl_path|resolve_run_output_dir|resolve_eval_output_dir" src/` returns no results
- [ ] T021 [S3] Update `specs/002-artifact-contracts/worklog.md` and `specs/002-artifact-contracts/usage.jsonl` with S3 completion entry

### Checkpoint

- [ ] Contract tests in `test_artifact_contracts.py` pass green before code removal
- [ ] All six legacy alias functions absent from `src/ctxbench/benchmark/paths.py`
- [ ] `resolve_expand_output_dir` and `resolve_expand_jsonl_path` still present (used by `experiment.py`)
- [ ] `pytest -k "legacy_rejection or artifact_contracts or status or export or eval"` passes
- [ ] No provider-backed execution required
- [ ] `worklog.md` and `usage.jsonl` updated

---

## Final Audit

- [ ] T022 [Audit] Run full provider-free validation from `plan.md`: inspect `docs/architecture/artifact-contracts.md` and confirm (a) all nine artifacts are named with phase + class labels; (b) four role treatments are present; (c) `manifest.json` responsibility text is present; (d) `results.csv` and `evals-summary.json` are explicitly derived; (e) three legacy mappings use explicit no-alias wording; (f) five provenance classes plus FR-013/FR-014 rule statements are present; confirm `rg "artifact-contracts" docs/architecture/` ≥3 hits and that README.md/workflow.md agree on eval outputs; if S3 was applied, confirm `rg` for removed functions returns nothing and focused pytest coverage is green
- [ ] T023 [Audit] Update `specs/002-artifact-contracts/worklog.md` with final validation result and any deferred findings (e.g., `evals-summary.json` path still hardcoded in `commands/eval.py`, `expand`-named aliases still present for follow-on rename, manual review used because branch naming does not match spec-kit prerequisite helper expectations)
- [ ] T024 [Audit] Update `specs/002-artifact-contracts/usage.jsonl` with implementation phase entry (token_provenance: unavailable if tool does not report usage)

---

## Dependencies and Execution Order

```
S1 (no deps) → S2 (depends on S1)
S1 (no deps) → S3 optional (depends on S1)
S2, S3 → Final Audit
```

Within S2, tasks T009, T010, T011, T012, T013 touch disjoint files and may run in parallel after the S1 checkpoint. Run T014 after those edits for slice validation, then T015 for worklog update.

## Provider and Cost Controls

- Do not run `ctxbench execute`, `ctxbench eval`, or any real provider command.
- All validation uses `grep`, `rg`, `sed`, `read`, and `pytest` with fixtures/mocks only.
- No API keys, provider tokens, or network access required.
