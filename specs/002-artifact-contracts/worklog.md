# Worklog: 002-artifact-contracts

## 2026-05-10 — Spec authored

Initial full spec created at roadmap level. Status: draft.

## 2026-05-11 — Spec converted to lite format

Reviewed full spec for verbosity and redundancy. Classified as `convert-to-lite`. Converted to lightweight spec format: removed Success Criteria (restatement of requirements), removed FR-015–FR-018 (restatement of Out of Scope), compressed Key Entities, reduced Assumptions to two load-bearing bullets. All accepted requirements, scope, migration decisions, and deferred decisions preserved. Line count: 193 → 135.

## 2026-05-11 — Tasks generated

tasks.md produced with 3 slices (S3 optional) and 22 tasks total. Organized by implementation slice, not user story, per user request. S1 (8 tasks), S2 (6 tasks), S3 optional (5 tasks), Final Audit (3 tasks). Plan.md was also revised by user/linter after initial authoring — S2 scope expanded to include workflow.md consistency, S3 made conditional on contract tests.

## 2026-05-11 — Plan authored

- Ran `setup-plan.sh` after updating `.specify/feature.json` to point at `specs/002-artifact-contracts`.
- Researched codebase: all target artifact names already emitted by writers; six unused legacy path aliases remain in `benchmark/paths.py`; no `docs/architecture/artifact-contracts.md` exists yet.
- Designed 3 slices: S1 (reference doc), S2 (legacy alias removal), S3 (doc pointers).
- Produced `research.md` and `plan.md`.
- Level 2 process logging started.

## 2026-05-11 — Slice S1 implemented

- Created `docs/architecture/artifact-contracts.md` as the authoritative artifact reference for FR-001 through FR-014.
- Documented all nine canonical artifacts with producing phase, class, and role.
- Recorded the canonical versus derived rule, including that `evals-summary.json` and `results.csv` are reproducible without provider re-runs.
- Defined the closed five-class metric provenance taxonomy and explicit `estimated`/`unavailable` handling rules.
- Added the legacy migration table with explicit no-alias wording and migration responsibility language.
- Validation stayed provider-free and was limited to targeted file inspection.

## 2026-05-11 — Slice S2 implemented

- Updated `docs/architecture/README.md` to index `artifact-contracts.md`, align the top-level workflow with `evals-summary.json`, and point the migration section to the authoritative reference.
- Updated `docs/architecture/workflow.md` so the overview diagram lists `evals-summary.json` in eval outputs.
- Updated `docs/architecture/vocabulary.md` and `docs/architecture/cli-architecture.md` to point migration readers to `docs/architecture/artifact-contracts.md`.
- Validation stayed provider-free and used `rg` plus targeted document inspection.

## 2026-05-11 — Slice S3 implemented

- Added `tests/test_artifact_contracts.py` with focused contract coverage for target artifact writer paths and mixed legacy/target directories.
- Removed six unused legacy artifact alias helpers from `src/ctxbench/benchmark/paths.py`.
- Kept `resolve_expand_output_dir` and `resolve_expand_jsonl_path` because `commands/experiment.py` still uses them.
- Validation stayed provider-free and used focused pytest plus repo search for removed alias names.
