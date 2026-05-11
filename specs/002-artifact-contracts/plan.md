# Plan: Artifact Contracts

**Branch**: `feat/artifact-contracts` | **Date**: 2026-05-11 | **Spec**: `specs/002-artifact-contracts/spec.md`
**Input**: Feature specification from `specs/002-artifact-contracts/spec.md`

## Summary

Create `docs/architecture/artifact-contracts.md` as the authoritative reference for the canonical artifact set, artifact classification, metric provenance taxonomy, and legacy no-alias policy. Update existing architecture docs so they consistently point to that reference and describe the same artifact set and workflow. Optionally remove unused internal legacy path aliases only if the implementation slice also proves the public reader/writer contract with focused tests.

## Decisions

- The reference document lives at `docs/architecture/artifact-contracts.md` (alongside `vocabulary.md`, `workflow.md`).
- `evals-summary.json` is classified as an evaluation-phase derived artifact (produced by `ctxbench eval` alongside `evals.jsonl`; reproducible from evals + judge votes without re-running providers).
- `resolve_expand_jsonl_path` and `resolve_expand_output_dir` are kept (still used by `experiment.py`); the six unused legacy aliases are removed only if S3 remains in scope and is backed by focused contract tests.
- No new paths.py functions are needed; `evals-summary.json` path remains hardcoded in `commands/eval.py` (out of scope for this spec).

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: `pyproject.toml`
**Storage**: `docs/architecture/artifact-contracts.md` (new); architecture docs under `docs/architecture/`; `src/ctxbench/benchmark/paths.py` only if the optional cleanup slice is kept
**Testing**: pytest; add focused legacy-artifact reader/writer contract tests if code cleanup is kept
**Target Platform**: CLI + architecture docs
**Project Type**: single Python CLI project
**Constraints**: provider-free validation; no full benchmark; no schema fields in the reference doc
**Scale/Scope**: small — one new markdown file, architecture doc consistency updates, and optional dead-code cleanup only if it remains spec-scoped

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| Phase separation | pass | No phase boundaries touched |
| Cost/evaluation separation | pass | Not touched |
| Metric provenance | pass | Spec formalizes the taxonomy already in constitution §III |
| Artifact contracts | pass | This spec IS the artifact-contracts definition (constitution §V) |
| Strategy comparability | n/a | — |
| Dataset/domain isolation | n/a | — |
| Provider isolation | n/a | — |
| Provider-free validation | pass | All checks are grep/read/pytest |
| Documentation impact | pass | Primary deliverable is a documentation file |
| Simplicity / research sufficiency | pass | Documentation + dead code removal only |

## Files Likely Affected

- `docs/architecture/artifact-contracts.md` — new file (primary deliverable)
- `docs/architecture/workflow.md` — align workflow overview and artifact lists with the new reference
- `docs/architecture/vocabulary.md` — add pointer to artifact-contracts.md
- `docs/architecture/README.md` — add pointer to artifact-contracts.md
- `docs/architecture/cli-architecture.md` — add pointer to artifact-contracts.md
- `src/ctxbench/benchmark/paths.py` — optional removal of unused legacy alias functions
- `tests/` — optional focused tests for mixed legacy/target artifact directories if the cleanup slice is kept

## Implementation Slices

| Slice | Goal | Likely files | Validation | Depends on |
|---|---|---|---|---|
| S1 | Create `artifact-contracts.md` reference (FR-001–FR-014) | `docs/architecture/artifact-contracts.md` | Read file against a requirement checklist covering phase/class labels, canonical/derived rules, provenance definitions, and explicit no-alias wording | — |
| S2 | Update architecture docs so artifact references and workflow descriptions stay consistent with S1 | `docs/architecture/vocabulary.md`, `docs/architecture/README.md`, `docs/architecture/cli-architecture.md`, `docs/architecture/workflow.md` | `rg "artifact-contracts" docs/architecture/`; inspect README doc index and workflow diagrams/text for consistent artifact lists, including `evals-summary.json` | S1 |
| S3 | Optional: remove unused internal legacy aliases only with contract-focused tests for FR-008/FR-009 | `src/ctxbench/benchmark/paths.py`, focused tests under `tests/` | Focused pytest coverage proves writers emit only target names and readers ignore legacy names when target files are present; repo search confirms removed aliases are unused | S1 |

### Slice detail

**S1 — Reference document**

Goal: produce `docs/architecture/artifact-contracts.md` that satisfies FR-001 through FR-014.

Content outline:
- Header: phase-lifecycle table (artifact, producing phase, class)
- Section per artifact role (execution, evaluation, analysis-ready export, traces)
- Metric provenance taxonomy block (5 classes with definitions), explicitly stating:
  - `estimated` MUST NOT be presented as `reported` or `measured` (FR-013)
  - `unavailable` MUST NOT be recorded as zero unless zero is the observed value (FR-013)
  - The taxonomy is closed in this spec; no sub-classes or extensions (FR-014)
- Legacy migration table (3 entries, explicit no-alias statements)
- Reader/writer policy (two bullet points)

Constraints from spec:
- No field-level schemas
- No format versioning
- No validation tooling
- Must be citable by follow-on specs

Validation:
```bash
sed -n '1,260p' docs/architecture/artifact-contracts.md
```

Acceptance checklist:
- FR-001/FR-002: all nine artifacts are present and each row shows producing phase and class
- FR-003: execution artifacts, evaluation artifacts, analysis-ready exports, and traces each have their own role treatment
- FR-004: `manifest.json` is explicitly described as a plan-phase canonical artifact with reproduction-oriented responsibility
- FR-005/FR-006: canonical vs. derived rules are stated, and `results.csv` plus `evals-summary.json` are explicitly derived and reproducible without provider re-runs
- FR-007/FR-010: all three legacy mappings appear with explicit no-alias wording and migration responsibility language
- FR-011/FR-014: exactly five provenance classes are defined, `estimated` and `unavailable` restrictions are explicit, and the taxonomy is explicitly closed in this spec

Commit: `docs(arch): add artifact-contracts reference`

---

**S2 — Architecture doc consistency updates**

Goal: keep architecture documentation internally consistent with the artifact-contracts reference and current implementation.

Changes:
- `README.md`: add `artifact-contracts.md` to the architecture document index
- `README.md`: update the top-level canonical workflow so the eval phase consistently includes `evals-summary.json`
- `workflow.md`: update the overview diagram so the eval phase consistently includes `evals-summary.json`
- `vocabulary.md`, `README.md`, `cli-architecture.md`: add a short pointer from each historical migration section to `artifact-contracts.md` as the authoritative artifact reference

Validation:
```bash
rg "artifact-contracts" docs/architecture/
sed -n '1,260p' docs/architecture/README.md
sed -n '1,220p' docs/architecture/workflow.md
```

Acceptance checklist:
- the architecture doc index lists `artifact-contracts.md`
- the top-level workflow descriptions in `README.md` and `workflow.md` agree on eval outputs
- migration tables remain labeled as historical/migration-only
- architecture docs point readers to `artifact-contracts.md` for the authoritative contract

Commit: `docs(arch): align architecture docs with artifact contracts`

---

**S3 — Optional internal cleanup with contract-focused tests**

Goal: remove dead internal legacy alias helpers only if the slice also demonstrates the public artifact contract behavior required by FR-008 and FR-009.

Possible cleanup:
- remove `resolve_queries_path`
- remove `resolve_answers_path`
- remove `resolve_run_jsonl_path`
- remove `resolve_eval_jsonl_path`
- remove `resolve_run_output_dir`
- remove `resolve_eval_output_dir`

Keep:
- `resolve_expand_output_dir` if still required by `commands/experiment.py`
- `resolve_expand_jsonl_path` if still required by `commands/experiment.py`

Validation:
```bash
pytest -k "legacy or status or export or eval"
rg "resolve_queries_path|resolve_answers_path|resolve_run_jsonl_path|resolve_eval_jsonl_path|resolve_run_output_dir|resolve_eval_output_dir" src/ tests/
```

Focused tests to add if this slice is kept:
- mixed directory with both legacy and target filenames: readers use target artifacts only
- writer-oriented command paths produce target filenames only
- presence of legacy files in an output directory is ignored rather than treated as an error

Note: if adding these tests is too large for this spec, drop this slice and leave `paths.py` unchanged.

Commit: `refactor(paths): remove unused internal legacy aliases`

## Process Logging

Level 2 change (spec + plan with implementation slices). See `worklog.md` and `usage.jsonl` for process history.

## Risks

- The public spec is mostly documentation-level, but the optional `paths.py` cleanup can drift into opportunistic refactoring unless paired with contract-level tests. If the tests are not added, this slice should be dropped.
- Existing architecture docs currently omit `evals-summary.json` from some top-level workflow views. If S2 is skipped or narrowed back to pointer-only updates, the documentation set will remain internally inconsistent.
- `evals-summary.json` path is hardcoded in `commands/eval.py`, not in `paths.py`. If a follow-on schema spec needs to move or configure this path, it will need to touch the eval command directly. Noted as an open question in the spec.
- `resolve_expand_jsonl_path` and `resolve_expand_output_dir` are kept; their names use the old vocabulary (`expand`). A follow-on spec may want to rename them. Out of scope here.

## Validation

Provider-free validation:

```bash
# After S1
sed -n '1,260p' docs/architecture/artifact-contracts.md

# After S2
rg "artifact-contracts" docs/architecture/
sed -n '1,260p' docs/architecture/README.md
sed -n '1,220p' docs/architecture/workflow.md

# After S3
pytest -k "legacy or status or export or eval"
rg "resolve_queries_path|resolve_answers_path|resolve_run_jsonl_path|resolve_eval_jsonl_path|resolve_run_output_dir|resolve_eval_output_dir" src/ tests/

# Full check
pytest -k "cli or legacy or status or export or eval"
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| _(none)_ | _(n/a)_ | _(n/a)_ |
