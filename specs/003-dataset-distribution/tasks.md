# Tasks: Dataset Distribution

**Spec**: `specs/003-dataset-distribution/spec.md`  
**Plan**: `specs/003-dataset-distribution/plan.md`  
**Branch**: `feat/dataset-distribution`

## Task Format

`- [ ] TXXX [P?] [Sn] Description with exact file path`

- **[P]**: parallelizable — touches disjoint files, no dependency on another in-flight task.
- **[Sn]**: implementation slice from `plan.md`.
- All tasks are provider-free unless explicitly marked otherwise.

## Execution Rules

- Implement one slice at a time; do not batch across slices.
- Do not call real LLM providers; use fixtures, mocks, and monkeypatching.
- Do not perform opportunistic refactors.
- Commit after each green slice checkpoint.
- End each slice with passing focused tests before moving to the next.

## Decision Locks

- `dataset: "path"` and `dataset: { "root": ... }` remain accepted compatibility inputs.
- `export` and `status` remain artifact-only commands and must not require dataset re-resolution.
- `evals.jsonl` and `judge_votes.jsonl` both gain first-class `dataset` provenance fields.
- `plan` is the provenance-producing phase for dataset identity/version/origin/revision fields.
- Generic execution/evaluation decoupling from embedded Lattes services is in scope, but only in
  the slices that explicitly name those files.
- Archive and release-asset acquisition require verified SHA-256 before extraction.
- Lifecycle commands must not depend on archive/release acquisition code paths.

---

## Slice S1 — Dataset Package Distribution Envelope

**Goal**: Define the `DatasetPackage` protocol, `StrategyDescriptor`, and `DatasetCapabilityReport`
dataclasses that form the distribution-facing interface; verify with contract tests.  
**Validation**: `pytest tests/test_dataset_package_contract.py`  
**Depends on**: nothing  
**Suggested commit**: `feat(dataset): add dataset package distribution envelope`

### Tasks

- [x] T001 [S1] Create `src/ctxbench/dataset/__init__.py` as package init (empty or with `__all__`).
- [x] T002 [P] [S1] Define `DatasetMetadata` dataclass in `src/ctxbench/dataset/package.py` with fields: `name: str`, `description: str`, `domain: str`, `intended_uses: str`, `limitations: str`, `license_url: str | None`, `citation_url: str | None`.
- [x] T003 [P] [S1] Define `StrategyDescriptor` dataclass in `src/ctxbench/dataset/package.py` with all nine required fields from FR-029: `name`, `classification`, `context_access_mode`, `inline_vs_operation`, `local_vs_remote`, `loop_ownership`, `metric_provenance: dict[str, str]`, `observability_limitations`, `comparability_implications`. All fields required; no defaults.
- [x] T004 [P] [S1] Define `DatasetCapabilityReport` dataclass in `src/ctxbench/dataset/capabilities.py` with all FR-026 fields: `identity`, `version`, `origin`, `resolved_revision`, `materialized_path`, `content_hash`, `metadata`, `mandatory_capabilities: dict[str, bool]`, `optional_capabilities: dict[str, bool]`, `contributed_tools`, `evaluation_helpers`, `strategy_descriptors: list[StrategyDescriptor]`, `missing_mandatory: list[str]`, `nonconformant_descriptors: list[str]`, `conformant: bool`.
- [x] T005 [S1] Define `@runtime_checkable class DatasetPackage(Protocol)` in `src/ctxbench/dataset/package.py` with the import `from typing import Protocol, runtime_checkable`. Mandatory methods: `metadata()`, `identity()`, `version()`, `origin()`, `list_instance_ids()`, `list_task_ids()`, `get_context_artifact()`, `get_evidence_artifact()`, `fixtures()`, `capability_report()`. Optional methods: `tool_provider()`, `evaluation_helpers()`, `strategy_descriptors()`. Return types per S1 surface sketch in `plan.md`.
- [x] T006 [S1] Write `tests/test_dataset_package_contract.py` asserting: (a) a class implementing all mandatory methods passes `isinstance(obj, DatasetPackage)`; (b) a class missing one mandatory method fails the check; (c) `StrategyDescriptor` with all nine fields constructs without error; (d) a `StrategyDescriptor` missing any required field raises `TypeError` at construction; (e) `DatasetCapabilityReport` with `conformant=False` and non-empty `missing_mandatory` is representable.

### Checkpoint

- [x] `pytest tests/test_dataset_package_contract.py` passes.
- [x] No provider calls.
- [x] No Lattes-specific imports in `src/ctxbench/dataset/package.py` or `capabilities.py`.
- [x] Diff is reviewable (new files only).

---

## Slice S2 — Dataset Materialization Cache

**Goal**: Add local cache for explicitly fetched datasets; write and read materialization manifests;
refuse silent overwrites.  
**Validation**: `pytest tests/test_dataset_cache.py`  
**Depends on**: nothing  
**Suggested commit**: `feat(dataset): add local materialization cache`

### Tasks

- [x] T007 [S2] Extend `MaterializationManifest` in `src/ctxbench/dataset/materialization.py` to include archive/release provenance fields needed by Spec 003: `sourceType`, `archiveUrl`, `releaseTagUrl`, `assetName`, `verifiedSha256`. Keep existing FR-021 fields and update validation so `fetchMethod` accepts `"archive-download"` in addition to existing values.
- [x] T008 [S2] Extend `DatasetCache` in `src/ctxbench/dataset/cache.py` so manifest read/write and conflict checks preserve archive/release provenance and verified checksum values. Idempotent re-materialization with identical identity/version/content/checksum should remain non-conflicting; conflicting checksum/content must still raise `DatasetConflictError`.
- [x] T009 [S2] Extend `tests/test_dataset_cache.py` asserting: (a) archive/release provenance fields round-trip through manifest IO; (b) `fetchMethod="archive-download"` is accepted; (c) idempotent store of identical manifest content remains non-conflicting; (d) conflicting checksum/content still raises `DatasetConflictError`.

### Checkpoint

- [x] `pytest tests/test_dataset_cache.py` passes.
- [x] No provider calls; no network access.
- [x] No Lattes-specific imports.
- [x] Diff is reviewable.

---

## Slice S3 — `ctxbench dataset fetch`

**Goal**: Implement explicit dataset acquisition command supporting `file-copy` and `git-clone`
methods; wire nested subparser per D10; write manifest.  
**Validation**: `pytest tests/test_dataset_fetch.py`  
**Depends on**: S2  
**Suggested commit**: `feat(cli): add ctxbench dataset fetch`

### Tasks

- [x] T010 [S3] Extend nested `dataset fetch` parser wiring in `src/ctxbench/cli.py` to accept archive/release acquisition options: `--asset-name`, `--sha256`, and `--sha256-url`. Parser validation must reject archive/release acquisition without one of `--sha256` or `--sha256-url`.
- [x] T011 [P] [S3] Refactor `fetch_command(...)` in `src/ctxbench/commands/dataset.py` behind an explicit acquisition source model in `src/ctxbench/dataset/acquisition.py`. Local-path `file-copy` behavior remains supported; direct `.tar.gz` URLs and GitHub Release tag URLs plus explicit asset name become recognized acquisition source types.
- [x] T012 [S3] Keep `fetch` sub-subparser behavior in `src/ctxbench/cli.py`, but update it so `ctxbench dataset fetch` dispatches the expanded acquisition source handling.
- [x] T013 [S3] Extend `tests/test_dataset_fetch.py` asserting: (a) local-path behavior still works; (b) archive/release inputs without checksum material fail before download/extraction; (c) `--asset-name` is accepted for release-tag origins; (d) `ctxbench dataset fetch --help` shows the new options.

### Checkpoint

- [x] `pytest tests/test_dataset_fetch.py` passes (local-path + parser/validation tests only; no real remote fetches).
- [x] `ctxbench dataset fetch --help` runs without error.
- [x] `ctxbench dataset` without subcommand prints usage without traceback.
- [x] No provider calls; no Lattes-specific imports.
- [x] Diff is reviewable.

---

## Slice S3a — Verified Archive and Release-Asset Acquisition

**Goal**: Support dataset acquisition from direct `.tar.gz` archive URLs and GitHub Release tag URLs
plus explicit asset names, with checksum verification required before extraction.  
**Validation**: `pytest tests/test_dataset_archive_fetch.py`  
**Depends on**: S2, S3  
**Suggested commit**: `feat(dataset): add verified archive acquisition sources`

### Tasks

- [x] T013a [S3a] Add acquisition source types in `src/ctxbench/dataset/acquisition.py` for: local path, direct archive URL, and GitHub Release tag URL plus explicit asset name.
- [x] T013b [P] [S3a] Implement archive/release checksum handling in `src/ctxbench/dataset/acquisition.py`: require `--sha256` or `--sha256-url`, load checksum material, and fail before extraction if checksum is missing or invalid.
- [x] T013c [P] [S3a] Implement release-tag source resolution in `src/ctxbench/dataset/acquisition.py` for a GitHub Release tag URL plus explicit `--asset-name`, returning exactly one resolved asset source or a structured error.
- [x] T013d [S3a] Write `tests/test_dataset_archive_fetch.py` covering: direct archive URL with `--sha256`, direct archive URL with `--sha256-url`, release tag URL plus `--asset-name`, missing checksum rejection, invalid checksum rejection, and provenance fields recorded in the materialization manifest. Use only local fixtures/mocks; do not fetch real assets.

### Checkpoint

- [x] `pytest tests/test_dataset_archive_fetch.py` passes.
- [x] No real remote assets fetched.
- [x] No provider calls.
- [x] Diff is reviewable.

---

## Slice S3b — Safe Extraction and Manifest Discovery

**Goal**: Safely extract verified `.tar.gz` archives, discover exactly one dataset manifest, and
validate identity/version before cache materialization.  
**Validation**: `pytest tests/test_dataset_archive_safety.py tests/test_dataset_manifest_discovery.py`  
**Depends on**: S2, S3a  
**Suggested commit**: `feat(dataset): add safe archive extraction and manifest discovery`

### Tasks

- [x] T013e [S3b] Implement safe extraction in `src/ctxbench/dataset/archive.py` for verified tar.gz archives. Reject path traversal, absolute paths, unsafe symlinks/hardlinks, device nodes, FIFOs, sockets, and other special files before writing them.
- [x] T013f [P] [S3b] Implement manifest discovery in `src/ctxbench/dataset/archive.py` or `src/ctxbench/dataset/acquisition.py`: support either a single top-level directory or files at archive root; require exactly one dataset package manifest; fail on zero or multiple manifests.
- [x] T013g [P] [S3b] Validate dataset identity/version after manifest discovery and before cache materialization in `src/ctxbench/dataset/acquisition.py`.
- [x] T013h [S3b] Write `tests/test_dataset_archive_safety.py` covering traversal entries, absolute paths, unsafe links, device nodes/FIFOs/special files, and safe extraction of a normal archive fixture.
- [x] T013i [S3b] Write `tests/test_dataset_manifest_discovery.py` covering: single top-level directory, archive-root files, no manifest, multiple manifests, and identity/version mismatch rejection.

### Checkpoint

- [x] `pytest tests/test_dataset_archive_safety.py tests/test_dataset_manifest_discovery.py` passes.
- [x] No real remote assets fetched.
- [x] No provider calls.
- [x] Diff is reviewable.

---

## Slice S4 — Dataset Resolver and Conflict Detection

**Goal**: Resolve experiment dataset references to exactly one local/cached `DatasetPackage`;
detect and reject ambiguous references; extend `ExperimentDataset` with provenance fields.  
**Validation**: `pytest tests/test_dataset_resolver.py tests/test_dataset_conflicts.py`  
**Depends on**: S1, S2  
**Suggested commit**: `feat(dataset): resolve cached datasets and reject ambiguous references`

### Tasks

- [x] T014 [S4] Add optional fields `id: str | None`, `version: str | None`, `origin: str | None` to `ExperimentDataset` in `src/ctxbench/benchmark/models.py`. Keep existing `root: str | None` for local-path compat (D11). Both forms remain valid: `{"root": "..."}` and `{"id": "...", "version": "..."}`.
- [x] T015 [P] [S4] Implement `DatasetConflictDetector.check(dataset_id, version, cache: DatasetCache) -> None` in `src/ctxbench/dataset/conflicts.py`: when `cache.lookup(dataset_id, version)` returns more than one manifest, raise `AmbiguousDatasetError` with a message listing each conflicting `origin` and `resolvedRevision`.
- [x] T016 [P] [S4] Implement `DatasetResolver` in `src/ctxbench/dataset/resolver.py` with method `resolve(ref: ExperimentDataset, cache: DatasetCache) -> DatasetPackage`. Logic: (a) if `ref` is a multi-dataset reference (a list or `datasets` key), raise `MultiDatasetError`; (b) if `ref.root` is set, load from local path without cache lookup; (c) if `ref.id` is set, call conflict detector then return the single matching materialization; (d) if not found, raise `DatasetNotFoundError` with a message suggesting `ctxbench dataset fetch`. MUST NOT make network calls (D4).
- [x] T017 [S4] Write `tests/test_dataset_resolver.py` asserting: (a) local-path `ExperimentDataset` resolves to a `DatasetPackage`-compatible object; (b) cached id+version resolves when exactly one materialization exists; (c) missing dataset raises `DatasetNotFoundError` whose message contains "ctxbench dataset fetch"; (d) multi-dataset reference raises `MultiDatasetError`.
- [x] T018 [S4] Write `tests/test_dataset_conflicts.py` asserting: (a) single materialization passes check without error; (b) two materializations for the same id+version with different origins raise `AmbiguousDatasetError` listing both candidates; (c) `DatasetResolver.resolve()` calls the conflict detector before returning.

### Checkpoint

- [x] `pytest tests/test_dataset_resolver.py tests/test_dataset_conflicts.py` passes.
- [x] No provider calls; no network access in resolver.
- [x] No Lattes-specific imports in `resolver.py` or `conflicts.py`.
- [x] Diff is reviewable.

---

## Slice S5 — Local-Path Package Adapter

**Goal**: Introduce the thin adapter that makes an existing on-disk local dataset root satisfy the
`DatasetPackage` contract without changing benchmark semantics.  
**Validation**: `pytest tests/test_dataset_local_package.py`  
**Depends on**: S1, S4  
**Suggested commit**: `refactor(dataset): wrap local dataset roots as dataset packages`

### Tasks

- [x] T019 [S5] Implement `LocalDatasetPackage` in `src/ctxbench/dataset/provider.py` or `src/ctxbench/dataset/local_package.py` as the compatibility adapter for current local dataset roots. It must expose enough information for current planning semantics: question text, question tags, validation type, context blocks, instance-level question parameters, context artifact lookup, and evidence lookup.
- [x] T020 [S5] Update `DatasetResolver.resolve()` in `src/ctxbench/dataset/resolver.py` so `ref.root` returns `LocalDatasetPackage` rather than a bare path or legacy provider object.
- [x] T021 [S5] Write `tests/test_dataset_local_package.py` asserting: (a) a real temporary local dataset root resolves to a `DatasetPackage`-compatible object; (b) the adapter preserves current question/template/instance parameter semantics needed by planning; (c) both `dataset: "path"` and `dataset: { "root": "path" }` resolve equivalently.

### Checkpoint

- [x] `pytest tests/test_dataset_local_package.py` passes.
- [x] No provider calls; no network access.
- [x] No Lattes-specific imports.
- [x] Diff is reviewable.

---

## Slice S6 — `ctxbench dataset inspect`

**Goal**: Add read-only inspection command that validates capabilities using the shared validation
module also used by `ctxbench plan` (FR-028); reject ambiguous references.  
**Validation**: `pytest tests/test_dataset_inspect.py`  
**Depends on**: S4, S5  
**Suggested commit**: `feat(cli): add ctxbench dataset inspect`

### Tasks

- [x] T022 [S6] Implement `validate_package(package: DatasetPackage) -> DatasetCapabilityReport` in `src/ctxbench/dataset/validation.py`. Check each mandatory extension point method; check each `StrategyDescriptor` for all nine required fields (FR-030); populate `missing_mandatory`, `nonconformant_descriptors`, and `conformant` accordingly. This function is the shared validation logic called by both `inspect` and `plan`.
- [x] T023 [P] [S6] Implement `build_inspect_result(package: DatasetPackage, manifest: MaterializationManifest | None) -> DatasetCapabilityReport` in `src/ctxbench/dataset/inspect.py`: call `validate_package`, populate provenance fields from manifest when available.
- [x] T024 [S6] Implement `inspect_command(dataset_ref: str, json_output: bool = False) -> None` in `src/ctxbench/commands/dataset.py`: call `DatasetConflictDetector.check` then `DatasetResolver.resolve`, then `build_inspect_result`; print human-readable or JSON output. Wire `inspect` sub-subparser in `src/ctxbench/cli.py` with positional `dataset_ref` and `--json` flag.
- [x] T025 [S6] Write `tests/test_dataset_inspect.py` asserting: (a) a fully conformant fake package reports `conformant=True` and empty `missing_mandatory`; (b) a package missing one mandatory extension point lists it in `missing_mandatory` and sets `conformant=False`; (c) a package with a `StrategyDescriptor` missing one field lists it in `nonconformant_descriptors`; (d) an ambiguous ref raises `AmbiguousDatasetError` before any capability check (FR-039); (e) `--json` output is valid JSON with keys `identity`, `version`, `conformant`, `missing_mandatory`.

### Checkpoint

- [x] `pytest tests/test_dataset_inspect.py` passes.
- [x] `ctxbench dataset inspect --help` runs without error.
- [x] No provider calls; no Lattes-specific imports.
- [x] Diff is reviewable.

---

## Slice S7 — Planning Integration

**Goal**: Make `ctxbench plan` resolve and validate the dataset package before trial generation;
persist dataset provenance in `manifest.json`; reject missing and ambiguous datasets.  
**Validation**: `pytest tests/test_dataset_distribution_workflow.py -k plan`  
**Depends on**: S4, S5, S6  
**Suggested commit**: `refactor(plan): resolve dataset package before trial planning`

### Tasks

- [x] T026 [S7] In `src/ctxbench/commands/plan.py`, add dataset resolution at the top of `plan_command`: call `DatasetResolver.resolve(experiment.dataset, cache)`. On `DatasetNotFoundError`, re-raise with remediation message. On `AmbiguousDatasetError`, re-raise listing candidates. On `MultiDatasetError`, re-raise with explicit error per FR-034.
- [x] T027 [S7] In `src/ctxbench/commands/plan.py`, after resolution call `validation.validate_package(package)` (shared with inspect per FR-028) and log the capability summary before proceeding to trial generation.
- [x] T028 [S7] In `src/ctxbench/commands/plan.py`, persist dataset provenance in `manifest.json` under a nested `dataset` key with fields: `id`, `version`, `origin`, `resolvedRevision`, `contentHash`. Provenance is read from the resolved manifest or from the package metadata for local-path datasets.
- [x] T029 [P] [S7] Update `src/ctxbench/benchmark/runspec_generator.py` to accept a resolved package/adapter argument instead of reconstructing from a raw path. It must preserve current planning semantics for question text, tags, validation type, context blocks, and instance-level parameters; do not widen the generic `DatasetPackage` protocol just to mirror legacy provider internals.
- [x] T030 [S7] Write integration test in `tests/test_dataset_distribution_workflow.py` covering four sub-cases (use `@pytest.mark.parametrize` or separate functions, all with fake dataset fixture): (a) plan with fake local-path dataset resolves, writes `manifest.json` with `dataset.id` field, writes `trials.jsonl`; (b) plan with missing dataset raises with a message containing "ctxbench dataset fetch"; (c) plan with two conflicting materializations raises `AmbiguousDatasetError`; (d) `dataset: "path"` and `dataset: { "root": ... }` produce equivalent planning output.

### Checkpoint

- [x] `pytest tests/test_dataset_distribution_workflow.py -k plan` passes.
- [x] `manifest.json` written by test contains `dataset.id` and `dataset.version`.
- [x] No provider calls.
- [x] Diff is reviewable.

---

## Slice S8 — Provenance Propagation Across Artifacts

**Goal**: Preserve dataset provenance unchanged from `manifest.json` through all six artifact
types; assert identity across artifacts.  
**Validation**: `pytest tests/test_dataset_provenance_artifacts.py`  
**Depends on**: S7  
**Suggested commit**: `feat(artifacts): propagate dataset provenance across phases`

### Tasks

- [x] T031 [S8] Add `DatasetProvenance` model to `src/ctxbench/benchmark/models.py` with fields: `id: str`, `version: str`, `origin: str | None`, `resolved_revision: str | None`, `content_hash: str | None`, `materialized_path: str | None`. Note: `materialized_path` is additive operational metadata — MUST NOT be treated as authoritative identity.
- [x] T032 [P] [S8] Update `src/ctxbench/benchmark/models.py`, `src/ctxbench/commands/plan.py`, and related serializers so `trials.jsonl` persists the dataset provenance chosen during planning. `execute.py` must not become the owner of `trials.jsonl`.
- [x] T033 [P] [S8] In `src/ctxbench/commands/execute.py`, preserve dataset provenance from `trials.jsonl`/`manifest.json` into `responses.jsonl` without recomputing or substituting values from another source.
- [x] T034 [P] [S8] In `src/ctxbench/commands/eval.py` and `src/ctxbench/benchmark/results.py`, preserve dataset provenance into `evals.jsonl` and `judge_votes.jsonl`. Both artifact types must carry first-class `dataset` objects.
- [x] T035 [P] [S8] In `src/ctxbench/commands/export.py` and `src/ctxbench/benchmark/results.py`, include `dataset_id` and `dataset_version` columns in `results.csv`. Do not add an export-manifest alternative in this slice; choose direct CSV columns for scope control.
- [x] T036 [P] [S8] Update `docs/architecture/artifact-contracts.md` to document the `dataset.*` provenance fields: their carrier artifacts, required/optional status, and the D9 note on flat vs. nested schema owners.
- [x] T037 [S8] Write `tests/test_dataset_provenance_artifacts.py` using the fake dataset and mocked execution: assert that `manifest.json`, `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl` all contain `dataset.id` and `dataset.version`; assert the values are identical across all artifact types for the same run (FR-043); assert that `execute` and `eval` do not recompute these values from a different source than the planning manifest (FR-045); assert `results.csv` contains `dataset_id` and `dataset_version` columns.

### Checkpoint

- [x] `pytest tests/test_dataset_provenance_artifacts.py` passes.
- [x] Manual spot-check via `jq '.dataset.id, .dataset.version' outputs/test-run/manifest.json` returns expected values.
- [x] No provider calls.
- [x] Diff is reviewable.

---

## Slice S9 — Lifecycle No-Network Enforcement

**Goal**: Assert that lifecycle commands never trigger network access for dataset resolution;
missing datasets raise immediately rather than fetching.  
**Validation**: `pytest tests/test_lifecycle_no_network.py`  
**Depends on**: S7  
**Suggested commit**: `test(dataset): enforce no implicit dataset fetch during lifecycle commands`

### Tasks

- [x] T038 [S9] In `src/ctxbench/dataset/resolver.py`, document the local-only resolution contract and keep resolver/materialization boundaries explicit. Do not add generic “network guards” unrelated to actual call sites; keep the enforcement focused on command behavior.
- [x] T039 [S9] Write `tests/test_lifecycle_no_network.py` using `monkeypatch` to replace fetch/materialization entry points with fail-fast stubs. Assert: (a) `plan_command` rejects unresolved datasets without fetching; (b) `execute_command` rejects missing planned materializations without fetching; (c) `eval_command` rejects missing required planned dataset evidence without fetching; (d) `export_command` succeeds from artifacts alone and does not touch dataset resolution; (e) `status_command` does not touch dataset resolution at all; (f) archive/release acquisition helpers are unreachable from lifecycle command paths.

### Checkpoint

- [x] `pytest tests/test_lifecycle_no_network.py` passes.
- [x] No provider calls; no network access.
- [x] Diff is reviewable.

---

## Slice S10 — Lattes Dataset Package Wrapper

**Goal**: Wrap existing Lattes infrastructure behind `LattesDatasetPackage`; remove direct Lattes
imports from generic core; first deliver the package wrapper and contract-level tests only.  
**Validation**: `pytest tests/test_lattes_dataset_package.py`  
**Depends on**: S1, S4, S6  
**Suggested commit**: `feat(lattes): add lattes dataset package wrapper`

### Tasks

- [ ] T040 [S10] Create `tests/fixtures/lattes_provider_free/dataset/` with minimal Lattes-structured fixture data: one instance file, one task file, one context artifact file, one evidence artifact file — enough to exercise all mandatory `DatasetPackage` extension points without real provider calls.
- [ ] T041 [S10] Implement `LattesDatasetPackage` in `src/ctxbench/datasets/lattes/package.py` satisfying `DatasetPackage` protocol: expose `identity()` → `"ctxbench/lattes"`, `version()` → current Lattes data version string, `metadata()`, `get_context_artifact()`, `get_evidence_artifact()`, and the package/adapter methods needed by current planning semantics.
- [ ] T042 [P] [S10] In `src/ctxbench/datasets/lattes/package.py`, implement `LattesDatasetPackage.tool_provider()` wrapping Lattes tool runtime ownership behind the dataset package boundary.
- [ ] T043 [S10] Write `tests/test_lattes_dataset_package.py` asserting: (a) `LattesDatasetPackage()` passes `isinstance(obj, DatasetPackage)` check; (b) `fixtures()` returns a path containing at least one instance and one task file; (c) `identity()` and `version()` return non-empty strings; (d) `capability_report()` returns a `DatasetCapabilityReport` with `conformant=True` and empty `missing_mandatory`.

### Checkpoint

- [ ] `pytest tests/test_lattes_dataset_package.py` passes.
- [ ] No real provider tokens consumed.
- [ ] Diff is reviewable.

---

## Slice S11 — Fake Dataset Provider-Free Workflow

**Goal**: Synthetic fake dataset validates generic distribution mechanics and Spec 004 boundary
neutrality without any Lattes-specific terms.  
**Validation**: `pytest tests/test_fake_dataset_workflow.py`  
**Depends on**: S1, S4, S5, S7  
**Suggested commit**: `test(dataset): add fake dataset provider-free workflow`

### Tasks

- [ ] T044 [S11] Create an on-disk fake dataset fixture under `tests/fixtures/fake_dataset/` using the same local-root compatibility path as real datasets: `questions.json`, `questions.instance.json`, minimal context/evidence artifacts, and an `experiment.json`. Do not require importing a Python package object from the fixture path.
- [ ] T045 [S11] If needed, add a tiny fake-package adapter helper under `tests/fixtures/fake_dataset/` only for tests, but keep the production resolution path the same as local-root datasets.
- [ ] T046 [S11] Write `tests/test_fake_dataset_workflow.py` as a provider-free integration test: (a) resolve the fake dataset via `DatasetResolver` local-root flow; (b) call `plan_command` with `tests/fixtures/fake_dataset/experiment.json` and assert `trials.jsonl` is written with generic vocabulary only; (c) assert no Lattes-specific terms (`lattes`, `curriculum`, `LattesProvider`) appear in any trial record; (d) assert `manifest.json` contains `dataset.id = "ctxbench/fake-dataset"`; (e) assert no real provider calls were made.

### Checkpoint

- [ ] `pytest tests/test_fake_dataset_workflow.py` passes.
- [ ] No Lattes terms in trial records.
- [ ] No provider calls.
- [ ] Diff is reviewable.

---

## Slice S12 — Executor/Evaluation Decoupling and Lattes Conformance

**Goal**: Remove direct Lattes imports from generic execution/evaluation code and verify the
provider-free Lattes conformance workflow end to end.  
**Validation**: `pytest tests/test_lattes_dataset_conformance.py` + static leakage grep  
**Depends on**: S7, S8, S10  
**Suggested commit**: `refactor(core): decouple generic execution from lattes services`

### Tasks

- [ ] T047 [S12] Create `tests/fixtures/lattes_provider_free/` directory with: `__init__.py`, `experiment.json`, `fake_responder.py`, and `fake_judge.py` for provider-free end-to-end testing.
- [ ] T048 [P] [S12] Create `tests/fixtures/lattes_provider_free/conftest.py` defining pytest fixtures that monkeypatch `ctxbench.benchmark.executor` and `ctxbench.benchmark.evaluation` to use `FakeResponder` and `FakeJudge`.
- [ ] T049 [P] [S12] Update `src/ctxbench/benchmark/executor.py` to consume the tool provider through the resolved dataset package/adapter boundary instead of directly importing `LattesMCPServer` or `LattesToolService`.
- [ ] T050 [P] [S12] Update `src/ctxbench/benchmark/evaluation.py` to consume dataset-backed evidence through the resolved dataset package/adapter boundary rather than rebuilding from `dataset.root` alone.
- [ ] T051 [S12] Run static leakage grep and assert zero hits: `grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/`. Fix any remaining leakage in scope before proceeding.
- [ ] T052 [S12] Write `tests/test_lattes_dataset_conformance.py` as a provider-free integration test using the monkeypatched responder and judge fixtures: fetch fixture, inspect, plan, execute, eval, export, then assert dataset provenance and non-empty trial output.

### Checkpoint

- [ ] `pytest tests/test_lattes_dataset_conformance.py` passes.
- [ ] `grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/` → zero hits.
- [ ] No real provider tokens consumed.
- [ ] Diff is reviewable.

---

## Slice S13 — Documentation and Architecture Update

**Goal**: Update all docs affected by dataset acquisition, inspection, resolution, and package
authoring; verify S11 checklist from `plan.md` passes.  
**Validation**: S11 documentation checklist  
**Depends on**: S1–S12 (for accurate command behavior to document)  
**Suggested commit**: `docs(dataset): document external dataset workflow and authoring guide`

### Tasks

- [ ] T053 [P] [S13] Create `docs/datasets/using-external-datasets.md`: remote dataset workflow (`ctxbench dataset fetch` → `ctxbench dataset inspect` → `ctxbench plan` → `execute` → `eval` → `export`); local-path dataset shortcut; conflict and ambiguity error resolution steps; no-implicit-network rule (FR-050, FR-051, FR-052, FR-058).
- [ ] T054 [P] [S13] Create `docs/datasets/creating-a-dataset.md`: dataset author guide covering all mandatory extension points (FR-005–FR-015), optional extension points (FR-016–FR-018), fixture requirement (FR-015), `StrategyDescriptor` nine-field requirement (FR-029), provider-free validation with `ctxbench dataset inspect`, identity/version conflict avoidance (FR-053), and archive packaging/release asset guidance.
- [ ] T055 [P] [S13] Update `docs/architecture/vocabulary.md` with all ten new terms from FR-057: `dataset repository`, `dataset package`, `dataset materialization`, `dataset cache`, `dataset resolver`, `dataset capability report`, `dataset origin`, `resolved revision`, `content hash`, `single-dataset experiment`.
- [ ] T056 [P] [S13] Update `docs/architecture/workflow.md` canonical workflow diagram to include dataset acquisition and cache step before `ctxbench plan` for remote datasets; add local-path shortcut note.
- [ ] T057 [P] [S13] Update `docs/architecture/cli-architecture.md` to explicitly separate lifecycle commands (`plan`, `execute`, `eval`, `export`, `status`) from dataset-management commands (`dataset fetch`, `dataset inspect`) per D10 nested subparser structure (FR-055).
- [ ] T058 [P] [S13] Update `docs/architecture/container.md` to show: remote dataset repository, local dataset materialization cache, `DatasetResolver`, `DatasetPackage` boundary, benchmark lifecycle, artifact store (FR-054).
- [ ] T059 [P] [S13] Update `docs/architecture/component.md` Mermaid diagram to show `DatasetResolver`, `DatasetPackage` boundary, and dataset cache as distinct components (FR-054).
- [ ] T060 [P] [S13] Update `docs/architecture/dynamic.md` to include flows: (a) successful remote dataset fetch; (b) inspect reporting non-conformant package; (c) plan rejected on missing dataset; (d) plan rejected on ambiguous dataset (FR-054).
- [ ] T061 [S13] Update `README.md` quickstart section to include `ctxbench dataset fetch` and `ctxbench dataset inspect` steps for remote datasets before `ctxbench plan`; add note that local-path datasets skip the fetch step.
- [ ] T062 [P] [S13] Create `specs/003-dataset-distribution/quickstart.md` with provider-free validation steps: fetch fixture, inspect, plan, execute (monkeypatched), eval (monkeypatched), export; expected outputs at each step.
- [ ] T063 [P] [S13] Create `specs/003-dataset-distribution/contracts/dataset-commands.md` documenting the dataset command contract: subcommand surface, argument schemas, exit codes, error message formats, and the nested subparser registration pattern (D10).
- [ ] T063a [P] [S13] Document verified archive acquisition examples in `docs/datasets/using-external-datasets.md` and `specs/003-dataset-distribution/contracts/dataset-commands.md`, including:
  - direct `.tar.gz` URL + `--sha256`;
  - release tag URL + `--asset-name` + `--sha256-url`;
  - failure behavior for missing/invalid checksums;
  - safe extraction guarantees and manifest discovery rules.

### Checkpoint

```text
[ ] README quickstart includes dataset fetch/inspect for remote datasets.
[ ] workflow.md diagram includes dataset acquisition and cache.
[ ] cli-architecture.md separates lifecycle from dataset-management commands.
[ ] container.md shows remote dataset repository and local dataset cache.
[ ] component.md shows DatasetResolver, DatasetPackage boundary, and artifact store.
[ ] dynamic.md includes fetch, inspect, missing dataset, ambiguous dataset flows.
[ ] vocabulary.md defines all ten new dataset distribution terms.
[ ] artifact-contracts.md documents dataset provenance fields (updated in S8).
[ ] using-external-datasets.md exists.
[ ] creating-a-dataset.md exists.
[ ] Spec 004 ownership of internal boundaries is referenced in creating-a-dataset.md.
```

```bash
test -f docs/datasets/using-external-datasets.md
test -f docs/datasets/creating-a-dataset.md
grep -R "ctxbench dataset fetch" README.md docs/ specs/003-dataset-distribution/
grep -R "ctxbench dataset inspect" README.md docs/ specs/003-dataset-distribution/
grep -R "single-dataset" docs/architecture/vocabulary.md
```

---

## Final Audit

- [ ] T064 [Audit] Run full provider-free test suite: `pytest tests/test_dataset_package_contract.py tests/test_dataset_cache.py tests/test_dataset_fetch.py tests/test_dataset_resolver.py tests/test_dataset_conflicts.py tests/test_dataset_local_package.py tests/test_dataset_inspect.py tests/test_dataset_distribution_workflow.py tests/test_dataset_provenance_artifacts.py tests/test_lifecycle_no_network.py tests/test_lattes_dataset_package.py tests/test_lattes_dataset_conformance.py tests/test_fake_dataset_workflow.py` — all must pass.
- [ ] T064a [Audit] Run archive/provider-free fetch tests: `pytest tests/test_dataset_archive_fetch.py tests/test_dataset_archive_safety.py tests/test_dataset_manifest_discovery.py` — all must pass.
- [ ] T065 [Audit] Run static leakage grep: `grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/` — zero hits required.
- [ ] T066 [Audit] Run S13 documentation validation checklist manually; confirm all eleven items pass.
- [ ] T067 [Audit] Update `worklog.md` with final validation summary, decisions made during implementation, and deferred items.

---

## Dependencies and Execution Order

```text
S1  ──────────────────────────────────────────────┐
S2                                                 │
S3 (needs S2)                                     │
S3a (needs S2, S3)                                │
S3b (needs S2, S3a)                               │
S4 (needs S1, S2)                                 │
S5 (needs S1, S4)                                 │
S6 (needs S4, S5)                                 │
S7 (needs S4, S5, S6)                             │
S8 (needs S7)         ────────────────────────────┤
S9 (needs S7)                                     │
S10 (needs S1, S4, S6)                            │
S11 (needs S1, S4, S5, S7)                        │
S12 (needs S7, S8, S10) ──────────────────────────┤
S13 (needs S1–S12)    ────────────────────────────┘
Audit (needs all slices complete)
```

S3 and S4 may begin in parallel once S2 is complete (disjoint files).  
S8 and S9 may begin in parallel once S7 is complete (disjoint files).  
S10 and S11 may begin in parallel once S7 is complete (disjoint files).  
Within S13, all [P]-marked tasks may run in parallel.

## Provider and Cost Controls

- Do not run real `ctxbench execute` or `ctxbench eval` with provider tokens.
- All execution tests must use `FakeResponder` and `FakeJudge` via `monkeypatch.setattr`.
- Resolver tests must stub `DatasetCache.lookup` rather than hitting the real filesystem.
- Cache tests must use a temporary directory fixture (`tmp_path`) rather than `~/.cache/ctxbench/`.
- Git-clone tests must be skipped (`@pytest.mark.skip(reason="requires network")`) unless run explicitly.
