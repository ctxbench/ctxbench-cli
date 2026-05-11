---
description: "Task list for the Command Model and Phase Renaming feature (spec 001)"
---

# Tasks: Command Model and Phase Renaming

**Input**: Design documents from `specs/001-command-model-phase-renaming/`
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by FR-014 and US4. Contract tests are added before
implementation so the no-alias behavior is pinned down early. Production-path
fixtures are migrated after the implementation slices they assert on.

**Organization**: Tasks are grouped by implementation phase and user story.
The final delivered state is intentionally breaking: no public `copa`,
`query`, `exec`, legacy selector flags, legacy artifact files, legacy record
fields, or bare `mcp` remote-strategy label.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches disjoint files and does not
  depend on another in-flight task.
- **[Story]**: User story label for user-story phases only.
- All paths are repo-relative from `ctxbench-cli/`.
- All tasks are provider-free. Any model-provider behavior must be tested with
  mock/fake clients or payload-building helpers only.

## Path Conventions

- Source: `src/copa/`
- Tests: flat files under `tests/` unless an explicit task adds a new file.
- Architecture docs: `docs/architecture/`
- Spec artifacts: `specs/001-command-model-phase-renaming/`

---

## Phase 1: Setup and Early Contract Tests

**Purpose**: Capture baseline references and add failing target-contract tests
before implementation.

- [X] T001 Capture pre-migration baseline at `specs/001-command-model-phase-renaming/baseline.before.txt` by running `rg -n --no-heading 'copa|\bquery\b|queries\.jsonl|answers\.jsonl|runId|questionId|\banswer\b|--question|--repeat|--ids|\bmcp\b' src/ tests/ docs/architecture/ README.md pyproject.toml flake.nix > specs/001-command-model-phase-renaming/baseline.before.txt`. This baseline is consumed by T069.
- [ ] T002 [P] Add CLI command/help contract tests in `tests/test_cli.py` covering `ctxbench` parser usage, allowed subcommands `{plan, execute, eval, export, status}`, and rejection of `query` and `exec`.
- [X] T003 [P] Add selector contract tests in `tests/test_cli.py` covering target flags `--task`, `--repetition`, `--trial-id` and rejection of `--question`, `--repeat`, and `--ids`.
- [X] T004 [P] Add artifact file and record-field contract tests in `tests/test_cli.py` for mock-only `plan` and `execute`: `trials.jsonl` / `responses.jsonl` exist and `queries.jsonl` / `answers.jsonl` do not.
- [X] T005 [P] Add eval/export/status target-artifact tests in `tests/test_eval_status_regression.py`: eval reads `responses.jsonl`, export reads `responses.jsonl`, and status counts `trials.jsonl` / `responses.jsonl`.
- [X] T006 [P] Add strategy label tests in `tests/test_ai.py`: `remote_mcp` resolves to the native remote MCP strategy path, `mcp` is rejected by engine resolution, and `local_mcp` remains distinct.
- [ ] T007 Add legacy-rejection tests in `tests/test_legacy_rejection.py` marked `@pytest.mark.legacy_rejection` for `ctxbench query`, `ctxbench exec`, legacy selector flags, and an experiment config containing `"mcp"`.
- [X] T008 Register the `legacy_rejection` marker in `pytest.ini`.

---

## Phase 2: Foundational Rename Primitives

**Purpose**: Update shared constants, model fields, selectors, schemas, and
strategy labels before command writers/readers are migrated.

- [X] T009 Update artifact path helpers in `src/copa/benchmark/paths.py`: default planning artifact becomes `trials.jsonl`, default execution artifact becomes `responses.jsonl`, and helper names are renamed only where needed by callers.
- [X] T010 Update trial identity fields in `src/copa/benchmark/models.py`: `RunMetadata` uses `trialId` / `taskId` in persisted/public structures while preserving non-public behavior.
- [X] T011 Update trial specification fields in `src/copa/benchmark/models.py`: `RunSpec.model_validate()` and `RunSpec.to_persisted_artifact()` consume and emit `trialId` / `taskId`, rejecting public `runId` / `questionId` inputs under the no-alias contract.
- [X] T012 Update response fields in `src/copa/benchmark/models.py`: `RunResult.model_validate()` and `RunResult.to_persisted_artifact()` consume and emit `trialId`, `taskId`, and `response`, rejecting public `runId`, `questionId`, and `answer` inputs.
- [X] T013 Update evaluation and judge-vote models in `src/copa/benchmark/models.py` so persisted eval and judge-vote records use `trialId`, `taskId`, and `response` where those concepts are serialized.
- [X] T014 Update selector data structures in `src/copa/benchmark/selectors.py`: `question` / `not_question` become `task` / `not_task`, `repeat` becomes `repetition`, and `ids` becomes `trial_id`.
- [X] T015 Audit `src/schemas/runspec.schema.json`; update only schema fields, `$id`, title, or required entries that define public legacy command/artifact/field contracts. Do not invent schema fields that are not present.
- [X] T016 Audit `src/schemas/plan.schema.json`; update only schema fields, `$id`, title, or required entries that define public legacy command/artifact/field contracts. Do not invent schema fields that are not present.
- [X] T017 Update strategy registry in `src/copa/ai/engine.py`: register native remote MCP as `remote_mcp`, do not register `mcp`, and keep `local_mcp` behavior separate.
- [X] T018 Update experiment strategy validation in `src/copa/benchmark/models.py` and/or `src/copa/benchmark/runspec_generator.py` so experiment factors containing `"mcp"` fail before `plan` writes artifacts.
- [X] T019 Update trial/response strategy validation in `src/copa/benchmark/models.py` so persisted public records containing `"mcp"` are rejected during reader validation.

---

## Phase 3: User Story 1 - Run Execution with Target Command (P1)

**Goal**: `ctxbench plan` and `ctxbench execute` work against a mock-only
fixture and produce target artifact names and fields.

**Independent Test**: Target parser/help tests pass; mock-only `plan` +
`execute` produces `trials.jsonl` and `responses.jsonl` with `trialId`,
`taskId`, and `response`.

- [X] T020 [US1] Update `pyproject.toml`: replace the public script `copa = "copa.cli:main"` with `ctxbench = "copa.cli:main"` while leaving `[project].name = "copa"` unchanged.
- [X] T021 [US1] Update `flake.nix`: expose `/bin/ctxbench`, update package/app output names that are public, and keep `--add-flags "copa.cli"` because the internal module path is unchanged.
- [X] T022 [US1] Update parser identity in `src/copa/cli.py`: `ArgumentParser(prog="ctxbench", description=...)` and top-level command list uses target terminology.
- [X] T023 [US1] Rename `src/copa/commands/query.py` to `src/copa/commands/execute.py` and rename `query_command` to `execute_command`.
- [X] T024 [US1] Update imports and command wiring in `src/copa/cli.py` from `copa.commands.query.query_command` to `copa.commands.execute.execute_command`, and replace the `query` subparser with `execute`.
- [X] T025 [US1] Update selector flags in `src/copa/cli.py`: `--task` / `--not-task`, `--repetition` / `--not-repetition`, `--trial-id` / `--trial-id-file`; remove legacy long flags entirely.
- [X] T026 [US1] Update selector parsing in `src/copa/cli.py` to construct the renamed `RunSelector` fields from T014.
- [X] T027 [US1] Sweep user-facing CLI help strings in `src/copa/cli.py` so canonical help output uses `execute`, `trials.jsonl`, `responses.jsonl`, `taskId`, `trialId`, and `response`.
- [X] T028 [US1] Update `src/copa/commands/plan.py` to write `trials.jsonl` through `src/copa/benchmark/paths.py` and print/log target terminology.
- [X] T029 [US1] Update `src/copa/commands/execute.py` to read `trials.jsonl`, write `responses.jsonl`, and use target public field names.
- [X] T030 [US1] Update trial generation in `src/copa/benchmark/runspec_generator.py` so produced trial records use `trialId`, `taskId`, and `remote_mcp`.
- [X] T031 [US1] Update execution result construction in `src/copa/benchmark/executor.py` so response records and execution metadata use target public field names.
- [X] T032 [US1] Update affected source/test imports from `copa.commands.query` to `copa.commands.execute` in `tests/test_cli.py` and any source file that imports the renamed command module.

---

## Phase 4: User Story 2 - Inspect Target Artifacts (P2)

**Goal**: Eval, export, and status operate on target artifacts and emit only
target public fields while preserving judge-vote separation and metric meaning.

**Independent Test**: Mock-only plan -> execute -> eval -> export fixture
produces `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`,
`evals-summary.json`, and `results.csv` without legacy public fields.

- [X] T033 [US2] Update `src/copa/commands/eval.py`: positional/input naming becomes `responses`, default input is `responses.jsonl`, output remains `evals.jsonl` / `judge_votes.jsonl`, and public fields use target names.
- [X] T034 [US2] Update `src/copa/commands/export.py`: reads `responses.jsonl`, merges evals/votes by `trialId`, and writes target CSV/detail fields including `trialId`, `taskId`, and `response`.
- [X] T035 [US2] Update `src/copa/commands/status.py`: reads `trials.jsonl`, `responses.jsonl`, and `evals.jsonl`; rendered labels use target phase/field terms.
- [X] T036 [US2] Update `src/copa/benchmark/evaluation.py`: judge request/evaluation aggregation reads response objects with target fields and persists target eval fields without conflating execution and judge costs.
- [ ] T037 [US2] Update `src/copa/benchmark/evaluation_batch.py`: batch manifest/job serialization uses target field names and mocked provider tests remain provider-free.
- [X] T038 [US2] Update `src/copa/benchmark/results.py`: response/eval/judge-vote serializers and trace refs use target fields while preserving trace directory scope.
- [X] T039 [US2] Update `src/copa/benchmark/checkpoints.py`: checkpoint records refer to `trialId` / completed trial IDs and keep checkpoint file behavior otherwise unchanged.
- [X] T040 [US2] Update `src/copa/benchmark/experiment_loader.py`: manifest-facing output uses target public terminology only where it serializes public artifact metadata.
- [X] T041 [US2] Update identity and filename helpers in `src/copa/util/artifacts.py`: public helper names and serialized identity inputs use `trial` / `task` terminology where applicable.
- [X] T042 [US2] Audit `src/copa/util/jsonl.py`; update only public docstrings or helper names if they contain legacy artifact terminology.
- [X] T043 [US2] Update `src/copa/util/ids.py` imports/calls to match renamed artifact identity helpers from T041.
- [X] T044 [US2] Update `src/copa/ai/runtime.py` where runtime metadata crosses into persisted artifacts; preserve MCP runtime protocol terminology that is not the strategy label.
- [X] T045 [US2] Update `src/copa/ai/trace.py` so strategy span recognition uses `strategy.remote_mcp.execute` and metric aggregation meaning/provenance is unchanged.
- [X] T046 [US2] Update `src/copa/ai/strategies/mcp.py` span names and public metadata to `remote_mcp`; keep the file name if no public import path is exposed.
- [X] T047 [P] [US2] Audit `src/copa/ai/strategies/inline.py` for artifact-facing legacy fields and update only those occurrences.
- [X] T048 [P] [US2] Audit `src/copa/ai/strategies/local_function.py` for artifact-facing legacy fields and update only those occurrences.
- [X] T049 [P] [US2] Audit `src/copa/ai/strategies/local_mcp.py` for artifact-facing legacy fields and update only those occurrences.
- [X] T050 [P] [US2] Audit `src/copa/ai/strategies/base.py` for artifact-facing legacy fields and update only those occurrences.
- [X] T051 [US2] Update `src/copa/ai/models/base.py` request/response metadata names that are serialized into artifacts.
- [X] T052 [US2] Update `src/copa/ai/models/openai.py`: native MCP payload path accepts `remote_mcp`, rejects `mcp`, and tests use fake clients/payload helpers only.
- [X] T053 [US2] Update `src/copa/ai/models/claude.py`: native MCP payload path accepts `remote_mcp`, rejects `mcp`, and tests use fake clients/payload helpers only.
- [X] T054 [US2] Update `src/copa/ai/models/gemini.py`: native MCP payload path accepts `remote_mcp`, rejects `mcp`, and tests use fake clients/payload helpers only.
- [X] T055 [P] [US2] Audit `src/copa/ai/models/mock.py` for artifact-facing legacy fields and update only those occurrences.
- [X] T056 [P] [US2] Audit `src/copa/dataset/questions.py` and `src/copa/dataset/provider.py` for artifact-facing legacy fields; preserve dataset-internal question terminology where it is not public benchmark artifact schema.
- [X] T057 [P] [US2] Audit `src/copa/datasets/lattes/provider.py`, `src/copa/datasets/lattes/mcp_server.py`, `src/copa/datasets/lattes/models.py`, `src/copa/datasets/lattes/tools.py`, `src/copa/datasets/lattes/readers/base.py`, `src/copa/datasets/lattes/readers/html_reader.py`, and `src/copa/datasets/lattes/readers/json_reader.py`; update only artifact-facing legacy fields and preserve Lattes/domain terminology.
- [X] T058 [US2] Audit stale modules `src/copa/commands/run.py` and `src/copa/commands/experiment.py`; either migrate artifact-facing terminology or document a removal/follow-up decision in `specs/001-command-model-phase-renaming/follow-ups.md`.

---

## Phase 5: User Story 3 - Document Compatibility Expectations (P3)

**Goal**: Docs declare deprecated public terms and replacements, and no
architecture doc contradicts the no-alias policy.

**Independent Test**: Architecture alias grep is clean and `README.md` has the
12-row Compatibility / Migration table.

- [X] T059 [US3] Add a **Compatibility / Migration** section to `README.md` with the 12 required FR-013 rows and the note that the installed command is `ctxbench` while the distribution may still be named `copa`.
- [X] T060 [US3] Update `docs/architecture/README.md`: remove or relabel read-side compatibility language and clarify actual `src/copa/` layout versus future target layout.
- [X] T061 [P] [US3] Update `docs/architecture/vocabulary.md`: remove compatibility-alias entries that conflict with no-alias behavior.
- [X] T062 [P] [US3] Update `docs/architecture/cli-architecture.md`: remove selector alias table and any command alias wording.

---

## Phase 6: User Story 4 - Migrate Test Fixtures (P4)

**Goal**: Production-path tests use target terminology; legacy terms appear
only in explicit legacy-rejection tests or documented historical assertions.

**Independent Test**: `pytest -q`, `pytest -q -m legacy_rejection`, and the
production-test legacy-term grep from `quickstart.md` pass.

- [X] T063 [US4] Migrate production-path fixtures and assertions in `tests/test_cli.py` to target commands, artifact names, selector flags, and record fields.
- [X] T064 [US4] Migrate production-path fixtures and assertions in `tests/test_ai.py` to target record fields and `remote_mcp`; keep protocol-level MCP terminology where appropriate.
- [X] T065 [US4] Migrate production-path fixtures and assertions in `tests/test_eval_status_regression.py` to `responses.jsonl`, `trialId`, `taskId`, and `response`.
- [X] T066 [US4] Audit `tests/test_lattes_sections.py`; update only public benchmark artifact terminology if present and preserve Lattes/domain terminology.

---

## Phase 7: Polish and Provider-Free Verification

**Purpose**: Audits, optional Nix validation, and mock-only end-to-end checks.

- [ ] T067 [P] Audit `outputs_analysis.ipynb` for `runId`, `questionId`, and `answer`; update to target fields or record a follow-up in `specs/001-command-model-phase-renaming/follow-ups.md`.
- [ ] T068 [P] Audit `docs/prompts/spec-kit/**` for legacy public terminology; if edits are required, create follow-up tasks naming exact files or add a clearly labeled historical note to retained templates.
- [ ] T069 Generate `specs/001-command-model-phase-renaming/baseline.after.txt` with the same grep scope as T001, diff it against `baseline.before.txt`, and verify remaining legacy mentions are limited to migration docs, explicitly historical docs, or `tests/test_legacy_rejection.py`.
- [ ] T070 Run focused provider-free tests: `pytest -q -k cli`, `pytest -q -k eval`, `pytest -q -k export`, `pytest -q -k status`, `pytest -q -k mcp`, and `pytest -q -m legacy_rejection`.
- [ ] T071 Run full provider-free test suite with `pytest -q`; do not run `ctxbench execute` or `ctxbench eval` against real providers.
- [ ] T072 If `nix` is available and lockfile updates are approved, validate Nix packaging with `nix flake check` and `nix run .# -- --help`; confirm the exposed binary path is `/bin/ctxbench`, not `/bin/copa`.
- [ ] T073 Run the `specs/001-command-model-phase-renaming/quickstart.md` recipe using a named mock-only fixture path documented in the command log; ensure no provider API environment variables are required or consumed.
- [ ] T074 Update `CLAUDE.md` only if its `<!-- SPECKIT START -->` context does not already point at `specs/001-command-model-phase-renaming/plan.md`.

---

## Dependencies and Execution Order

- **Phase 1** runs first. T002-T007 may fail until implementation is complete;
  that is expected.
- **Phase 2** depends on T001 and can proceed while contract tests are present.
- **US1** depends on T009-T019.
- **US2** depends on US1 and T009-T019 because readers must match target writers.
- **US3** can run after Phase 1 and in parallel with US1/US2.
- **US4** depends on US1 and US2 substantially complete.
- **Polish** depends on US1-US4 complete.

## Parallel Opportunities

- T002-T006 can be authored in parallel because they touch different test areas.
- T015 and T016 are independent schema audits.
- T047-T050 are independent strategy audits after T045/T046.
- T052-T055 are independent provider/mock model updates after T017.
- T059-T062 are independent documentation tasks after README ownership is clear.
- T063-T066 are independent test-file migrations after implementation behavior exists.
- T067 and T068 are independent audits.

## Provider and Cost Controls

- Do not run real provider-backed `ctxbench execute` or `ctxbench eval`.
- Provider adapter tests must use fake clients, mocked SDK objects, or pure payload
  construction helpers.
- Quickstart verification must use a mock-only fixture and must not require API
  keys, provider tokens, or network access.
- Nix validation is conditional on local availability and approval for lockfile
  changes.
