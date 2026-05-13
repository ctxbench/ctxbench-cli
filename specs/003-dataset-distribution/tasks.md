# Tasks: Dataset Distribution

**Spec**: `specs/003-dataset-distribution/spec.md`  
**Plan**: `specs/003-dataset-distribution/plan.md`  
**Branch**: `feat/dataset-distribution`  
**Amendments**: `specs/003-dataset-distribution/amendments/001-simplified-fetch-ux.md` (Slice S-A1), `specs/003-dataset-distribution/amendments/descriptor-and-cache-reuse.md` (Slice S-A1-R1)

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
- `--descriptor-url` and `--descriptor-file` are self-describing; no `--id`/`--version` required.
- `--dataset-url` and `--dataset-file` are opaque; `--id` and `--version` are required at dispatch.
- Cache pre-check must happen before any archive download or extraction for all source types.
- `--force` does not bypass checksum verification, safe extraction, or manifest validation.
- Materialized paths are semantic: `<cache-dir>/<dataset-id>/<datasetVersion>/` (no hash in path).
- Content hash is recorded in provenance only; not used as part of the materialized path.

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

## Slice S3 — `ctxbench dataset fetch` _(SUPERSEDED by S-A1 for CLI surface)_

> **Amendment A1**: CLI surface (positional `<dataset-id>`, `--origin`, `--version`) superseded by S-A1. Parser wiring and `file-copy` dispatch remain as prior work. Do not use S3 command examples as the canonical reference.

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

## Slice S3a — Verified Archive and Release-Asset Acquisition _(SUPERSEDED by S-A1 for argument model)_

> **Amendment A1**: The `--asset-name` flag and release tag URL + asset name form are superseded. Archive download and checksum verification logic preserved. S-A1 replaces the argument model with `--dataset-url`/`--sha256`/`--sha256-url`.

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

## Slice S3b — Safe Extraction and Manifest Discovery _(PARTIALLY SUPERSEDED by S-A1)_

> **Amendment A1**: Archive safety logic remains valid. Manifest discovery is superseded: target name changes to `ctxbench.dataset.json` and identity/version are read from the manifest rather than validated against CLI args. S-A1 updates manifest discovery.

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

- [x] T040 [S10] Create `tests/fixtures/lattes_provider_free/dataset/` with minimal Lattes-structured fixture data: one instance file, one task file, one context artifact file, one evidence artifact file — enough to exercise all mandatory `DatasetPackage` extension points without real provider calls.
- [x] T041 [S10] Implement `LattesDatasetPackage` in `src/ctxbench/datasets/lattes/package.py` satisfying `DatasetPackage` protocol: expose `identity()` → `"ctxbench/lattes"`, `version()` → current Lattes data version string, `metadata()`, `get_context_artifact()`, `get_evidence_artifact()`, and the package/adapter methods needed by current planning semantics.
- [x] T042 [P] [S10] In `src/ctxbench/datasets/lattes/package.py`, implement `LattesDatasetPackage.tool_provider()` wrapping Lattes tool runtime ownership behind the dataset package boundary.
- [x] T043 [S10] Write `tests/test_lattes_dataset_package.py` asserting: (a) `LattesDatasetPackage()` passes `isinstance(obj, DatasetPackage)` check; (b) `fixtures()` returns a path containing at least one instance and one task file; (c) `identity()` and `version()` return non-empty strings; (d) `capability_report()` returns a `DatasetCapabilityReport` with `conformant=True` and empty `missing_mandatory`.

### Checkpoint

- [x] `pytest tests/test_lattes_dataset_package.py` passes.
- [x] No real provider tokens consumed.
- [x] Diff is reviewable.

---

## Slice S11 — Fake Dataset Provider-Free Workflow

**Goal**: Synthetic fake dataset validates generic distribution mechanics and Spec 004 boundary
neutrality without any Lattes-specific terms.  
**Validation**: `pytest tests/test_fake_dataset_workflow.py`  
**Depends on**: S1, S4, S5, S7  
**Suggested commit**: `test(dataset): add fake dataset provider-free workflow`

### Tasks

- [x] T044 [S11] Create an on-disk fake dataset fixture under `tests/fixtures/fake_dataset/` using the same local-root compatibility path as real datasets: `questions.json`, `questions.instance.json`, minimal context/evidence artifacts, and an `experiment.json`. Do not require importing a Python package object from the fixture path.
- [x] T045 [S11] No fake-package adapter helper was needed; keep the production resolution path the same as local-root datasets.
- [x] T046 [S11] Write `tests/test_fake_dataset_workflow.py` as a provider-free integration test: (a) resolve the fake dataset via `DatasetResolver` local-root flow; (b) call `plan_command` with `tests/fixtures/fake_dataset/experiment.json` and assert `trials.jsonl` is written with generic vocabulary only; (c) assert no Lattes-specific terms (`lattes`, `curriculum`, `LattesProvider`) appear in any trial record; (d) assert `manifest.json` contains `dataset.id = "ctxbench/fake-dataset"`; (e) assert no real provider calls were made.

### Checkpoint

- [x] `pytest tests/test_fake_dataset_workflow.py` passes.
- [x] No Lattes terms in trial records.
- [x] No provider calls.
- [x] Diff is reviewable.

---

## Slice S12 — Executor/Evaluation Decoupling and Lattes Conformance

**Goal**: Remove direct Lattes imports from generic execution/evaluation code and verify the
provider-free Lattes conformance workflow end to end.  
**Validation**: `pytest tests/test_lattes_dataset_conformance.py` + static leakage grep  
**Depends on**: S7, S8, S10  
**Suggested commit**: `refactor(core): decouple generic execution from lattes services`

### Tasks

- [x] T047 [S12] Create `tests/fixtures/lattes_provider_free/` directory with: `__init__.py`, `experiment.json`, `fake_responder.py`, and `fake_judge.py` for provider-free end-to-end testing.
- [x] T048 [P] [S12] Create `tests/fixtures/lattes_provider_free/conftest.py` defining pytest fixtures that monkeypatch `ctxbench.benchmark.executor` and `ctxbench.benchmark.evaluation` to use `FakeResponder` and `FakeJudge`.
- [x] T049 [P] [S12] Update `src/ctxbench/benchmark/executor.py` to consume the tool provider through the resolved dataset package/adapter boundary instead of directly importing `LattesMCPServer` or `LattesToolService`.
- [x] T050 [P] [S12] Update `src/ctxbench/benchmark/evaluation.py` to consume dataset-backed evidence through the resolved dataset package/adapter boundary rather than rebuilding from `dataset.root` alone.
- [x] T051 [S12] Run static leakage grep and assert zero hits: `grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/`. Fix any remaining leakage in scope before proceeding.
- [x] T052 [S12] Write `tests/test_lattes_dataset_conformance.py` as a provider-free integration test using the monkeypatched responder and judge fixtures: fetch fixture, inspect, plan, execute, eval, export, then assert dataset provenance and non-empty trial output.

### Checkpoint

- [x] `pytest tests/test_lattes_dataset_conformance.py` passes.
- [x] `grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/` → zero hits.
- [x] No real provider tokens consumed.
- [x] Diff is reviewable.

---

## Slice S13 — Documentation and Architecture Update

**Goal**: Update all docs affected by dataset acquisition, inspection, resolution, and package
authoring; verify S11 checklist from `plan.md` passes.  
**Validation**: S11 documentation checklist  
**Depends on**: S1–S12 (for accurate command behavior to document)  
**Suggested commit**: `docs(dataset): document external dataset workflow and authoring guide`

### Tasks

- [x] T053 [P] [S13] Create `docs/datasets/using-external-datasets.md`: remote dataset workflow (`ctxbench dataset fetch` → `ctxbench dataset inspect` → `ctxbench plan` → `execute` → `eval` → `export`); local-path dataset shortcut; conflict and ambiguity error resolution steps; no-implicit-network rule (FR-050, FR-051, FR-052, FR-058).
- [x] T054 [P] [S13] Create `docs/datasets/creating-a-dataset.md`: dataset author guide covering all mandatory extension points (FR-005–FR-015), optional extension points (FR-016–FR-018), fixture requirement (FR-015), `StrategyDescriptor` nine-field requirement (FR-029), provider-free validation with `ctxbench dataset inspect`, identity/version conflict avoidance (FR-053), and archive packaging/release asset guidance.
- [x] T055 [P] [S13] Update `docs/architecture/vocabulary.md` with all ten new terms from FR-057: `dataset repository`, `dataset package`, `dataset materialization`, `dataset cache`, `dataset resolver`, `dataset capability report`, `dataset origin`, `resolved revision`, `content hash`, `single-dataset experiment`.
- [x] T056 [P] [S13] Update `docs/architecture/workflow.md` canonical workflow diagram to include dataset acquisition and cache step before `ctxbench plan` for remote datasets; add local-path shortcut note.
- [x] T057 [P] [S13] Update `docs/architecture/cli-architecture.md` to explicitly separate lifecycle commands (`plan`, `execute`, `eval`, `export`, `status`) from dataset-management commands (`dataset fetch`, `dataset inspect`) per D10 nested subparser structure (FR-055).
- [x] T058 [P] [S13] Update `docs/architecture/container.md` to show: remote dataset repository, local dataset materialization cache, `DatasetResolver`, `DatasetPackage` boundary, benchmark lifecycle, artifact store (FR-054).
- [x] T059 [P] [S13] Update `docs/architecture/component.md` Mermaid diagram to show `DatasetResolver`, `DatasetPackage` boundary, and dataset cache as distinct components (FR-054).
- [x] T060 [P] [S13] Update `docs/architecture/dynamic.md` to include flows: (a) successful remote dataset fetch; (b) inspect reporting non-conformant package; (c) plan rejected on missing dataset; (d) plan rejected on ambiguous dataset (FR-054).
- [x] T061 [S13] Update `README.md` quickstart section to include `ctxbench dataset fetch` and `ctxbench dataset inspect` steps for remote datasets before `ctxbench plan`; add note that local-path datasets skip the fetch step.
- [x] T062 [P] [S13] Create `specs/003-dataset-distribution/quickstart.md` with provider-free validation steps: fetch fixture, inspect, plan, execute (monkeypatched), eval (monkeypatched), export; expected outputs at each step.
- [x] T063 [P] [S13] Create `specs/003-dataset-distribution/contracts/dataset-commands.md` documenting the dataset command contract: subcommand surface, argument schemas, exit codes, error message formats, and the nested subparser registration pattern (D10).
- [x] T063a [P] [S13] Document verified archive acquisition examples in `docs/datasets/using-external-datasets.md` and `specs/003-dataset-distribution/contracts/dataset-commands.md`, including:
  - direct `.tar.gz` URL + `--sha256`;
  - release tag URL + `--asset-name` + `--sha256-url`;
  - failure behavior for missing/invalid checksums;
  - safe extraction guarantees and manifest discovery rules.

### Checkpoint

```text
[x] README quickstart includes dataset fetch/inspect for remote datasets.
[x] workflow.md diagram includes dataset acquisition and cache.
[x] cli-architecture.md separates lifecycle from dataset-management commands.
[x] container.md shows remote dataset repository and local dataset cache.
[x] component.md shows DatasetResolver, DatasetPackage boundary, and artifact store.
[x] dynamic.md includes fetch, inspect, missing dataset, ambiguous dataset flows.
[x] vocabulary.md defines all ten new dataset distribution terms.
[x] artifact-contracts.md documents dataset provenance fields (updated in S8).
[x] using-external-datasets.md exists.
[x] creating-a-dataset.md exists.
[x] Spec 004 ownership of internal boundaries is referenced in creating-a-dataset.md.
```

```bash
test -f docs/datasets/using-external-datasets.md
test -f docs/datasets/creating-a-dataset.md
grep -R "ctxbench dataset fetch" README.md docs/ specs/003-dataset-distribution/
grep -R "ctxbench dataset inspect" README.md docs/ specs/003-dataset-distribution/
grep -R "single-dataset" docs/architecture/vocabulary.md
```

---

---

## Slice S-A1a — Simplified Fetch Surface and Manifest-Driven Identity (Amendment A1)

**Goal**: Replace the verbose `ctxbench dataset fetch <dataset-id> --origin --version` CLI surface with the simplified source-selector UX. Read identity and `datasetVersion` from `ctxbench.dataset.json` during fetch and print the materialized path.  
**Validation**: `pytest tests/test_dataset_fetch.py tests/test_dataset_archive_fetch.py tests/test_dataset_manifest_discovery.py tests/test_dataset_archive_safety.py`  
**Depends on**: S2, S3  
**Suggested commit**: `feat(cli): simplify ctxbench dataset fetch UX (Amendment A1)`

### Tasks

- [x] T-A1a-1 [S-A1a] Update the `fetch` subparser in `src/ctxbench/cli.py`: remove positional `<dataset-id>`, `--origin`, mandatory `--version`, and public `--asset-name`; add `--dataset-url`, `--dataset-file`, and `--dataset-dir` as a mutually exclusive group (exactly one required); add `--sha256-file`; keep `--sha256` and `--sha256-url`; add optional `--id` / `--version` only if they are implemented strictly as validation overrides per FR-019f.
- [x] T-A1a-2 [P] [S-A1a] Update acquisition and manifest handling in `src/ctxbench/dataset/acquisition.py` and `src/ctxbench/dataset/archive.py` to use `--dataset-url` / `--dataset-file` / `--dataset-dir` as the primary source selector; enforce checksum requirements per FR-019a/b/c/d; target `ctxbench.dataset.json` as the canonical manifest; read identity and `datasetVersion` from the discovered manifest; validate optional `--id` / `--version` overrides only if `T-A1a-1` adds them.
- [x] T-A1a-3 [S-A1a] Update `fetch_command()` and `fetch_command_from_args()` in `src/ctxbench/commands/dataset.py` to dispatch on source type (`--dataset-url` → archive-download, `--dataset-file` → local archive, `--dataset-dir` → directory import); remove the old `<dataset-id> --origin --version` primary flow; preserve archive safety logic; print identity, `datasetVersion`, verified checksum (when available), and final materialized path after successful materialization.
- [x] T-A1a-4 [S-A1a] Update `tests/test_dataset_fetch.py` for the new parser and fetch behavior: cover `--dataset-url` + `--sha256-url`, `--dataset-file` + `--sha256-file`, `--dataset-dir`, no source flag error, multiple source flag error, missing checksum rejection for `--dataset-url`, missing checksum rejection for `--dataset-file`, and fetch output containing identity, `datasetVersion`, and materialized path.
- [x] T-A1a-5 [P] [S-A1a] Update `tests/test_dataset_archive_fetch.py` and `tests/test_dataset_manifest_discovery.py` to use the source-selector argument form and `ctxbench.dataset.json`; remove tests that treat `--origin` / `--asset-name` or release-tag URL + asset-name as the canonical CLI surface; keep `tests/test_dataset_archive_safety.py` as validation-only because archive safety logic is unchanged.

### Checkpoint

- [x] `pytest tests/test_dataset_fetch.py` passes with source-selector UX.
- [x] `pytest tests/test_dataset_archive_fetch.py` passes with updated argument form.
- [x] `pytest tests/test_dataset_manifest_discovery.py` passes targeting `ctxbench.dataset.json`.
- [x] `pytest tests/test_dataset_archive_safety.py` passes unchanged.
- [x] `ctxbench dataset fetch --help` shows `--dataset-url`, `--dataset-file`, and `--dataset-dir`; does NOT show positional `<dataset-id>`, `--origin`, or `--asset-name` as the primary flow.
- [x] `ctxbench dataset fetch` without a source flag prints an argparse error, not a traceback.
- [x] No provider calls; no real remote fetches.
- [x] Diff is reviewable.

---

## Slice S-A1b — Shared Cache Root and Materialization Compatibility (Amendment A1)

**Goal**: Add shared cache-root selection for dataset-resolving commands and keep materialization metadata aligned with Amendment A1 without opportunistic schema refactors.  
**Validation**: `pytest tests/test_dataset_cache.py tests/test_dataset_inspect.py tests/test_fake_dataset_workflow.py tests/test_dataset_distribution_workflow.py -k "plan or inspect"`  
**Depends on**: S-A1a  
**Suggested commit**: `feat(cache): share dataset cache root across fetch inspect and plan`

### Tasks

- [x] T-A1b-1 [S-A1b] Update `src/ctxbench/cli.py` so `ctxbench dataset inspect` and `ctxbench plan` accept `--cache-dir`; ensure `ctxbench dataset fetch` passes `--cache-dir` through its args path as part of the shared cache-root contract in D14 / FR-019j.
- [x] T-A1b-2 [P] [S-A1b] Update `DatasetCache` in `src/ctxbench/dataset/cache.py` to accept an optional cache root and resolve it in this order: constructor arg → `CTXBENCH_DATASET_CACHE` env var → default location (D13 / FR-019h). Keep the change scoped to cache-root resolution; do not refactor unrelated cache semantics.
- [x] T-A1b-3 [P] [S-A1b] Update `src/ctxbench/commands/dataset.py`, `src/ctxbench/commands/plan.py`, and `src/ctxbench/dataset/materialization.py` so inspect and plan construct `DatasetCache` with the resolved cache root and materialization metadata records `datasetVersion` as authoritative while keeping `requestedVersion` compatibility explicit and narrow.
- [x] T-A1b-4 [S-A1b] Add focused provider-free tests in `tests/test_dataset_cache.py`, `tests/test_dataset_inspect.py`, `tests/test_fake_dataset_workflow.py`, and `tests/test_dataset_distribution_workflow.py` for: `--cache-dir` overrides default, `CTXBENCH_DATASET_CACHE` overrides default, explicit `--cache-dir` takes priority over the env var, and `ctxbench dataset inspect` / `ctxbench plan` resolve datasets from the same non-default cache root.
- [x] T-A1b-5 [P] [S-A1b] Update `docs/datasets/using-external-datasets.md`, `specs/003-dataset-distribution/contracts/dataset-commands.md`, and `README.md` to document the simplified source-selector fetch UX and shared `--cache-dir` behavior without introducing any new dataset commands.

### Checkpoint

- [x] `pytest tests/test_dataset_cache.py` passes.
- [x] `pytest tests/test_dataset_inspect.py` passes.
- [x] `pytest tests/test_fake_dataset_workflow.py` passes.
- [x] `pytest tests/test_dataset_distribution_workflow.py -k "plan or inspect"` passes.
- [x] `ctxbench dataset inspect --help` and `ctxbench plan --help` show `--cache-dir`.
- [x] `CTXBENCH_DATASET_CACHE` and explicit `--cache-dir` precedence are both covered by focused provider-free tests.
- [x] No provider calls; no real remote fetches.
- [x] Diff is reviewable.

---

## Slice S-A1-R1 — Descriptor Acquisition and Cache Reuse (Amendment A1-R1)

**Goal**: Add the distribution descriptor source, cache pre-check, no-op reuse, conflict/force behavior, descriptor-vs-manifest validation, semantic materialization paths, and provenance additions.  
**Validation**: `pytest tests/test_dataset_descriptor.py tests/test_dataset_fetch.py tests/test_dataset_cache.py tests/test_dataset_archive_fetch.py`  
**Depends on**: S-A1b (all prior fetch slices)  
**Suggested commit**: `feat(fetch): add descriptor-based acquisition and cache reuse (A1-R1)`

### Tasks

- [x] T-R1-1 [S-A1-R1] Update the `fetch` subparser in `src/ctxbench/cli.py` to add `--descriptor-url` and `--descriptor-file` to the mutually exclusive source group (group now has 5 members: `--descriptor-url`, `--descriptor-file`, `--dataset-url`, `--dataset-file`, `--dataset-dir`). Add `--id` and `--version` as optional standalone validation overrides for opaque archive sources, add `--force` for conflict replacement, and keep `--sha256`, `--sha256-url`, and `--sha256-file` as standalone flags.

- [x] T-R1-2 [S-A1-R1] Create `src/ctxbench/dataset/descriptor.py` with `DistributionDescriptor` dataclass containing required fields (`id`, `datasetVersion`, `descriptorSchemaVersion`, `archive_type`, `archive_url`, `archive_sha256`) and optional fields (`name`, `description`, `release_tag`). Validate all required fields at construction; raise a structured `DescriptorValidationError` on any missing field.

- [x] T-R1-3 [P] [S-A1-R1] Implement `load_descriptor(source: str, *, from_url: bool) -> DistributionDescriptor` in `src/ctxbench/dataset/descriptor.py`. For `from_url=True`: download the JSON from the URL. For `from_url=False`: read from the local file path. Parse into `DistributionDescriptor` and validate required fields before returning.

- [x] T-R1-4 [P] [S-A1-R1] Update `MaterializationManifest` in `src/ctxbench/dataset/materialization.py` to add `descriptorUrl: str | None` and `descriptorSchemaVersion: int | None`. Populate these fields when `--descriptor-url` or `--descriptor-file` is the source. Update manifest serialization/deserialization accordingly.

- [x] T-R1-5 [P] [S-A1-R1] Update `DatasetCache.store()` and its target-path logic in `src/ctxbench/dataset/cache.py` to use the semantic path `<cache_root>/<dataset_id>/<datasetVersion>/`. Remove any content-hash segment from the materialized path. Decide this slice's compatibility rule explicitly in implementation notes and tests; do not expand into a broader cache migration refactor.

- [x] T-R1-6 [P] [S-A1-R1] Add a cache pre-check helper in `src/ctxbench/dataset/cache.py` or `src/ctxbench/dataset/acquisition.py` that accepts dataset identity, version, and expected content identity when available. Return a no-op hit only when the existing materialization matches the requested content identity, return a conflict result when the same id/version exists with different content identity, and return a miss otherwise.

- [x] T-R1-7 [S-A1-R1] In `src/ctxbench/commands/dataset.py`, enforce that `--dataset-url` and `--dataset-file` require both `--id` and `--version` at fetch dispatch time. Raise an error with a clear message naming which required flags are missing before any download or extraction begins, and add dispatch branches for `--descriptor-url` and `--descriptor-file`.

- [x] T-R1-8 [P] [S-A1-R1] In `src/ctxbench/dataset/acquisition.py`, integrate cache pre-check into the fetch flow for self-describing descriptor sources and opaque archive sources only (`--descriptor-url`, `--descriptor-file`, `--dataset-url`, `--dataset-file`). On hit: print the existing materialized path and exit without acquiring. On conflict without `--force`: raise `DatasetConflictError`. On conflict with `--force`: record the conflict, proceed with all validation, then replace the existing materialization after all steps succeed. Keep `--dataset-dir` on its existing validation/store path in this slice.

- [x] T-R1-9 [P] [S-A1-R1] In `src/ctxbench/dataset/acquisition.py`, implement descriptor-vs-manifest validation: after extraction, compare descriptor `id` and `datasetVersion` with the corresponding fields in the discovered `ctxbench.dataset.json`. A mismatch MUST raise a structured error before materialization.

- [x] T-R1-10 [S-A1-R1] Write `tests/test_dataset_descriptor.py` asserting: (a) valid descriptor with all required fields parses without error; (b) descriptor missing any single required field raises `DescriptorValidationError`; (c) `load_descriptor` from a local JSON file returns a valid `DistributionDescriptor`; (d) `load_descriptor` from a URL (mocked HTTP) returns a valid `DistributionDescriptor`; (e) optional fields are accepted when present.

- [x] T-R1-11 [S-A1-R1] Update `tests/test_dataset_fetch.py` to cover A1-R1 additions: (a) `--descriptor-url` triggers descriptor load, cache pre-check, then archive download when miss; (b) `--descriptor-file` triggers local descriptor parse, cache pre-check, then archive download when miss; (c) `--dataset-url` without `--id` fails with clear error; (d) `--dataset-url` without `--version` fails with clear error; (e) `--dataset-file` without `--id` or `--version` fails with clear error; (f) no-op when cache pre-check returns a hit (no download, prints existing path); (g) conflict raises error when `--force` not set; (h) `--force` replaces after successful validation; (i) descriptor `id` or `datasetVersion` mismatch against `ctxbench.dataset.json` fails before materialization; (j) all 5 source flags remain mutually exclusive.

- [x] T-R1-12 [P] [S-A1-R1] Update `tests/test_dataset_cache.py` to cover: (a) cache pre-check returns hit for matching materialization and expected content identity; (b) cache pre-check returns conflict for same id/version with different content; (c) cache pre-check returns miss when no materialization exists; (d) semantic path format (`<id>/<version>/`) is used in `store()`; (e) content hash is recorded in the manifest, not the path; (f) descriptor provenance fields (`descriptorUrl`, `descriptorSchemaVersion`) round-trip through manifest IO.

- [x] T-R1-13 [P] [S-A1-R1] Update `tests/test_dataset_archive_fetch.py` to cover descriptor-driven archive acquisition helpers and provider-free archive-source validation paths needed by A1-R1, without duplicating cache-path assertions already owned by `tests/test_dataset_cache.py`.

- [x] T-R1-14 [P] [S-A1-R1] Update `docs/datasets/using-external-datasets.md` and `specs/003-dataset-distribution/contracts/dataset-commands.md` to document: (a) `--descriptor-url` and `--descriptor-file` as canonical acquisition sources; (b) `--id`/`--version` requirement for opaque archive sources; (c) cache reuse no-op behavior and what is printed; (d) conflict error and `--force` behavior; (e) semantic materialized path structure.

### Checkpoint

- [x] `pytest tests/test_dataset_descriptor.py` passes.
- [x] `pytest tests/test_dataset_fetch.py` passes with 5-source selector and A1-R1 behaviors.
- [x] `pytest tests/test_dataset_cache.py` includes cache pre-check and semantic path assertions.
- [x] `pytest tests/test_dataset_archive_fetch.py` passes with A1-R1 descriptor-driven archive validation tests.
- [x] `ctxbench dataset fetch --help` shows `--descriptor-url` and `--descriptor-file` as source options; shows `--id` and `--version` as optional flags; shows `--force` for conflict replacement.
- [x] `ctxbench dataset fetch --descriptor-url <url>` when dataset is already cached: prints existing path, no download.
- [x] No provider calls; no real remote fetches.
- [x] Diff is reviewable.

---

## Final Audit

- [x] T064 [Audit] Run full provider-free test suite: `pytest tests/test_dataset_package_contract.py tests/test_dataset_cache.py tests/test_dataset_fetch.py tests/test_dataset_resolver.py tests/test_dataset_conflicts.py tests/test_dataset_local_package.py tests/test_dataset_inspect.py tests/test_dataset_distribution_workflow.py tests/test_dataset_provenance_artifacts.py tests/test_lifecycle_no_network.py tests/test_lattes_dataset_package.py tests/test_lattes_dataset_conformance.py tests/test_fake_dataset_workflow.py` — all must pass.
- [x] T064a [Audit] Run archive/provider-free fetch tests: `pytest tests/test_dataset_archive_fetch.py tests/test_dataset_archive_safety.py tests/test_dataset_manifest_discovery.py` — all must pass.
- [x] T064b [Audit] After S-A1a: re-run the full fetch/archive/manifest test suite with the simplified source-selector UX: `pytest tests/test_dataset_fetch.py tests/test_dataset_archive_fetch.py tests/test_dataset_manifest_discovery.py tests/test_dataset_archive_safety.py` — all must pass with the new argument form.
- [x] T064c [Audit] After S-A1b: run focused provider-free cache-root and compatibility validation: `pytest tests/test_dataset_cache.py tests/test_dataset_inspect.py tests/test_fake_dataset_workflow.py tests/test_dataset_distribution_workflow.py -k "plan or inspect"` — all must pass with shared `--cache-dir` / `CTXBENCH_DATASET_CACHE` behavior.
- [x] T064d [Audit] After S-A1-R1: run descriptor and cache-reuse test suite: `pytest tests/test_dataset_descriptor.py tests/test_dataset_fetch.py tests/test_dataset_cache.py tests/test_dataset_archive_fetch.py` — all must pass with descriptor source, cache pre-check, no-op, conflict, and `--force` behaviors.
- [x] T065 [Audit] Run static leakage grep: `grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/` — zero hits required.
- [x] T066 [Audit] Run S13 documentation validation checklist manually; confirm all eleven items pass.
- [x] T067 [Audit] Update `worklog.md` with final validation summary, decisions made during implementation, and deferred items.

---

## Dependencies and Execution Order

```text
S1  ──────────────────────────────────────────────┐
S2                                                 │
S3 (needs S2)              [superseded CLI surface]│
S3a (needs S2, S3)         [superseded arg model] │
S3b (needs S2, S3a)        [manifest name updated]│
S-A1a (needs S2, S3)       [fetch UX + manifest]  │
S-A1b (needs S-A1a)        [shared cache root]    │
S-A1-R1 (needs S-A1b)      [descriptor + reuse]   │
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
Audit (needs all slices complete, including S-A1a/S-A1b/S-A1-R1)
```

S3 and S4 may begin in parallel once S2 is complete (disjoint files).  
S-A1a may begin once S3 is complete (amends S3 files).  
S-A1b may begin once S-A1a is complete (shared cache-root and compatibility follow-on).  
S-A1-R1 may begin once S-A1b is complete (adds descriptor layer on top of fetch surface).  
S8 and S9 may begin in parallel once S7 is complete (disjoint files).  
S10 and S11 may begin in parallel once S7 is complete (disjoint files).  
Within S13, all [P]-marked tasks may run in parallel.

## Provider and Cost Controls

- Do not run real `ctxbench execute` or `ctxbench eval` with provider tokens.
- All execution tests must use `FakeResponder` and `FakeJudge` via `monkeypatch.setattr`.
- Resolver tests must stub `DatasetCache.lookup` rather than hitting the real filesystem.
- Cache tests must use a temporary directory fixture (`tmp_path`) rather than `~/.cache/ctxbench/`.
- Git-clone tests must be skipped (`@pytest.mark.skip(reason="requires network")`) unless run explicitly.
