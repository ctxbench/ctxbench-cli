# Plan: Dataset Distribution

**Spec**: `specs/003-dataset-distribution/spec.md`  
**Branch**: `feat/dataset-distribution`  
**Status**: Draft — Amendment A1 applied (Simplified Fetch UX) — Amendment A1-R1 applied (Descriptor-Based Acquisition and Cache Reuse)  
**Related specs**: Spec 001, Spec 002, Spec 004  
**Amendments**: `specs/003-dataset-distribution/amendments/001-simplified-fetch-ux.md`, `specs/003-dataset-distribution/amendments/descriptor-and-cache-reuse.md`

## Summary

Implement the dataset distribution boundary for CTXBench.

This plan introduces explicit dataset acquisition and inspection commands:

```text
ctxbench dataset fetch
ctxbench dataset inspect
```

It also introduces:

- a local dataset materialization cache;
- a dataset resolver;
- a dataset package distribution envelope;
- dataset capability reporting;
- dataset conflict detection;
- dataset provenance propagation through artifacts;
- a single-dataset experiment rule;
- provider-free validation with both a fake dataset and the real `ctxbench/lattes` package;
- documentation updates for the new workflow and dataset authoring.

Spec 004 remains the owner of internal core/adapter boundary semantics. This plan only carries those contracts across the external distribution boundary.

## Decisions

### D1 — Add a dataset-management namespace (spec D1)

Add:

```text
ctxbench dataset fetch
ctxbench dataset inspect
```

These are support commands, not lifecycle phases.

Lifecycle remains:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

### D2 — Fetch is explicit and non-executing (spec D3)

`ctxbench dataset fetch` materializes an external dataset repository/package into a local cache.

It MUST NOT execute code from the fetched dataset.

Archive- and release-asset-based fetches are allowed only when checksum verification succeeds
before extraction.

### D3 — Inspect is read-only (spec D4)

`ctxbench dataset inspect` validates metadata and reports capabilities. It does not fetch, plan, execute, evaluate, export, or mutate benchmark artifacts.

### D4 — Lifecycle commands never fetch remote datasets (spec D2)

`plan`, `execute`, `eval`, `export`, and `status` operate only on local/cached datasets and artifacts.

### D5 — One experiment references one dataset (spec D6)

Spec 003 keeps the current single-dataset experiment model. Multiple datasets can be cached locally, but an `experiment.json` references exactly one dataset.

### D6 — Dataset cache is not a registry (spec D5)

The local dataset cache is a materialization cache keyed by explicit identity/version/origin/revision information. It does not perform plugin discovery, package marketplace behavior, dynamic loading, or adapter registration.

### D6a — Acquisition source types are explicit (amended by A1, refined by A1-R1)

Dataset acquisition source selection uses five exclusive flags:

- `--descriptor-url`: download and parse a remote distribution descriptor; check cache; download archive only if needed; (canonical remote workflow; A1-R1)
- `--descriptor-file`: parse a local distribution descriptor; check cache; download archive only if needed; (offline descriptor workflow; A1-R1)
- `--dataset-url`: download a remote `.tar.gz` archive; requires `--id`, `--version`, `--sha256` or `--sha256-url`; cache pre-check uses `--id`/`--version` before download; (A1-R1 adds `--id`/`--version` requirement)
- `--dataset-file`: use a local `.tar.gz` archive; requires `--id`, `--version`, `--sha256` or `--sha256-file`; cache pre-check uses `--id`/`--version` before extraction; (A1-R1 adds `--id`/`--version` requirement)
- `--dataset-dir`: import an already-unpacked local directory; manifest must be present; self-describing.

Exactly one source flag must be provided. Providing none or more than one is an error.

The old positional `<dataset-id> --origin <origin> --version <version>` CLI surface is superseded. The GitHub Release tag URL + `--asset-name` form is also superseded.

Archive and release-asset flows are acquisition-only behaviors. They do not change the no-network rule for lifecycle commands.

### D7 — Reuse existing task/instance models where possible (spec D8)

Do not create parallel `DatasetTask` / `DatasetInstance` models duplicating existing question/task structures. Use aliases, wrappers, or adapter-facing views where needed.

### D8 — Fake dataset and Lattes conformance have different roles (spec FR-049)

Fake dataset validates generic distribution mechanics and provider-free workflow.

`ctxbench/lattes` validates real dataset package conformance.

### D9a — Dataset identity and version come from `ctxbench.dataset.json` (Amendment A1)

Dataset identity and `datasetVersion` are read from the dataset package manifest (`ctxbench.dataset.json`), not from CLI arguments. Optional `--id` and `--version` CLI flags may exist only as validation overrides. The manifest name `ctxbench.dataset.json` is fixed to avoid confusion with lifecycle `manifest.json`.

Version terminology: `datasetVersion` (from manifest) is distinct from `ctxbenchVersion`, `manifestSchemaVersion`, `releaseTag`, and `contentHash`.

### D9b — Cache root selection is injectable and shared (Amendment A1)

`DatasetCache` accepts an optional `cache_root` parameter. Resolution order: constructor arg → `CTXBENCH_DATASET_CACHE` env var → default location. All of `ctxbench dataset fetch`, `ctxbench dataset inspect`, and `ctxbench plan` must support `--cache-dir` / `CTXBENCH_DATASET_CACHE` consistently.

### D9c — Descriptor model, cache pre-check, semantic paths, and force behavior (Amendment A1-R1)

1. **Descriptor model** (`src/ctxbench/dataset/descriptor.py` — NEW): `DistributionDescriptor` dataclass with required fields (`id`, `datasetVersion`, `descriptorSchemaVersion`, `archive.type`, `archive.url`, `archive.sha256`) and optional fields (`name`, `description`, `releaseTag`). A `load_descriptor(source, *, from_url)` function handles both URL download and local file read. Missing required fields raise a structured validation error before any cache lookup.

2. **Source exclusivity** (`src/ctxbench/cli.py`): Add `--descriptor-url` and `--descriptor-file` to the mutually exclusive fetch source group (5 total). `--id` and `--version` remain optional standalone flags. The `--sha256`, `--sha256-url`, and `--sha256-file` flags remain standalone.

3. **--id/--version enforcement** (`src/ctxbench/commands/dataset.py`): Validated at dispatch time for `--dataset-url` and `--dataset-file` sources; argparse does not enforce cross-flag requirements.

4. **Cache pre-check** (`src/ctxbench/dataset/cache.py` or `acquisition.py`): Before downloading or extracting, call `DatasetCache.lookup(id, version)`. If a materialization with matching content identity exists, return it immediately as a no-op result. If a materialization exists with conflicting content identity, raise `DatasetConflictError`. `--force` flag clears the conflicting entry only after all downstream validation succeeds.

5. **Descriptor-vs-manifest validation** (`src/ctxbench/dataset/acquisition.py`): After extraction, compare descriptor `id` / `datasetVersion` with the discovered `ctxbench.dataset.json`. Mismatch raises a structured error before materialization.

6. **Semantic paths** (`src/ctxbench/dataset/cache.py`): `DatasetCache.materialize()` writes to `<cache_root>/<dataset_id>/<datasetVersion>/`. No content hash in the path. Content hash recorded in the manifest.

7. **Materialization manifest additions** (`src/ctxbench/dataset/materialization.py`): Add `descriptorUrl: str | None` and `descriptorSchemaVersion: int | None`. Record descriptor URL when `--descriptor-url` or `--descriptor-file` is used.

### D9 — Materialization manifest and artifact provenance use different schemas

The materialization manifest (written by `ctxbench dataset fetch`) uses a flat camelCase schema:

```json
{ "datasetId": "...", "requestedVersion": "...", "resolvedRevision": "..." }
```

Artifact provenance (written by lifecycle phases) uses a nested `dataset` object:

```json
{ "dataset": { "id": "...", "version": "...", "resolvedRevision": "..." } }
```

These are intentionally different representations with different owners. The materialization manifest is owned by the cache layer; artifact provenance is owned by the planning phase and propagated through lifecycle artifacts. Both record the same identity/version/origin/resolvedRevision/contentHash values.

For archive/release acquisition, the materialization manifest additionally records acquisition
source and checksum provenance not required in lifecycle artifact carriers.

### D10 — `ctxbench dataset` uses nested argparse subparsers

`ctxbench dataset` is registered as a top-level subcommand in `build_parser()` with its own
`add_subparsers()` call, producing nested `fetch` and `inspect` sub-subcommands:

```python
dataset_parser = subparsers.add_parser("dataset", help="Dataset management")
dataset_sub = dataset_parser.add_subparsers(dest="dataset_command", required=True)
fetch_parser = dataset_sub.add_parser("fetch", ...)
inspect_parser = dataset_sub.add_parser("inspect", ...)
```

Dispatch reads `args.command == "dataset"` and delegates on `args.dataset_command`. No flat
compound names (`dataset-fetch`, `dataset-inspect`) are introduced. `dataset_parser` itself has no
`func` default — invoking `ctxbench dataset` without a subcommand produces an argparse usage error.

### D11 — Local-path datasets remain a supported compatibility input

Existing experiment configs using either:

```json
{ "dataset": "/abs/or/relative/path" }
```

or:

```json
{ "dataset": { "root": "/abs/or/relative/path" } }
```

remain valid in Spec 003.

The resolver normalizes both forms into the same resolved local-dataset representation. For
local-path datasets that do not come from the materialization cache, provenance written to lifecycle
artifacts records:

- the resolved local path;
- dataset identity/version/origin/resolvedRevision/contentHash when the dataset package can declare
  them locally;
- `null` for any provenance field that is not responsibly knowable from the local package.

String-path acceptance is a compatibility requirement for this spec slice. Removal of string-path
input would require a follow-on spec.

### D12 — Lifecycle commands split into dataset-consuming vs. artifact-only behavior

Lifecycle commands do not all interact with datasets in the same way.

- `plan` must resolve a local dataset reference and must fail on missing or ambiguous datasets.
- `execute` may consume only the dataset provenance and materialized/local package selected at
  planning time; it must not fetch or re-resolve to a different dataset.
- `eval` may read dataset-backed evaluation evidence only from the dataset provenance and
  materialization selected at planning time; it must not fetch or re-resolve to a different
  dataset.
- `export` and `status` are artifact-only readers in the current architecture. They must not fetch,
  clone, or require the local dataset to still exist when the necessary provenance is already
  present in lifecycle artifacts.

This means “no implicit fetch during lifecycle” is enforced differently by command:

- `plan` rejects unresolved datasets up front;
- `execute` and `eval` reject missing local materializations required by the planned run;
- `export` and `status` preserve offline usability by reading artifacts only.

### D13 — Generic execution/evaluation must not depend on embedded Lattes services

Current execution still imports Lattes-specific runtimes directly from generic benchmark code.
Spec 003 must remove that coupling as part of implementation, not as deferred cleanup.

Tool-based execution and dataset-backed evaluation evidence must flow through the resolved dataset
package boundary or a narrow adapter owned by the dataset layer. Generic benchmark code must not:

- import `ctxbench.datasets.lattes.*` from execution or evaluation modules;
- assume `dataset.contexts` exists as a generic contract;
- branch on dataset identity to choose tool runtimes or evidence readers.

## Files Likely Affected

```text
src/ctxbench/cli.py
src/ctxbench/commands/dataset.py                         # NEW
src/ctxbench/dataset/package.py                          # NEW
src/ctxbench/dataset/resolver.py                         # NEW
src/ctxbench/dataset/cache.py                            # NEW
src/ctxbench/dataset/inspect.py                          # NEW
src/ctxbench/dataset/materialization.py                  # NEW
src/ctxbench/dataset/acquisition.py                      # NEW
src/ctxbench/dataset/archive.py                          # NEW
src/ctxbench/dataset/capabilities.py                     # NEW
src/ctxbench/dataset/validation.py                       # NEW — shared capability validation (S5/S6)
src/ctxbench/dataset/conflicts.py                        # NEW
src/ctxbench/dataset/provider.py                         # adapt / legacy wrapper
src/ctxbench/benchmark/models.py                         # ExperimentDataset provenance fields
src/ctxbench/benchmark/runspec_generator.py              # use resolved package
src/ctxbench/benchmark/executor.py                       # remove direct root/Lattes coupling
src/ctxbench/commands/plan.py                            # resolve/validate dataset package
src/ctxbench/commands/execute.py                         # provenance pass-through
src/ctxbench/commands/eval.py                            # provenance pass-through
src/ctxbench/commands/export.py                          # dataset columns / export manifest
src/ctxbench/commands/status.py                          # preserve artifact-only offline behavior
src/ctxbench/benchmark/evaluation.py                     # package-based evidence access
src/ctxbench/benchmark/results.py                        # provenance serialization
src/ctxbench/datasets/lattes/package.py                  # temporary wrapper / conformance target
tests/fixtures/fake_dataset/
tests/fixtures/lattes_provider_free/                     # NEW — fake responder for S9
tests/test_dataset_cache.py
tests/test_dataset_fetch.py
tests/test_dataset_archive_fetch.py                      # NEW
tests/test_dataset_archive_safety.py                     # NEW
tests/test_dataset_manifest_discovery.py                 # NEW
tests/test_dataset_inspect.py
tests/test_dataset_resolver.py
tests/test_dataset_conflicts.py
tests/test_dataset_package_contract.py
tests/test_lattes_dataset_package.py
tests/test_dataset_distribution_workflow.py
tests/test_dataset_path_compatibility.py
tests/test_export_dataset_provenance.py
tests/test_status_dataset_provenance.py
README.md
docs/architecture/README.md
docs/architecture/workflow.md
docs/architecture/cli-architecture.md
docs/architecture/container.md
docs/architecture/component.md
docs/architecture/dynamic.md
docs/architecture/vocabulary.md
docs/architecture/artifact-contracts.md
docs/datasets/using-external-datasets.md                 # NEW
docs/datasets/creating-a-dataset.md                      # NEW
specs/003-dataset-distribution/quickstart.md
specs/003-dataset-distribution/contracts/dataset-commands.md
```

## Implementation Slices

### S1 — Dataset Package Distribution Envelope

**Goal**: Define the distribution-facing `DatasetPackage` protocol or structural interface.

The envelope exposes distribution requirements and maps internal capability methods to Spec 004 boundaries.

**Key rules**:

- Do not redefine Spec 004 semantics.
- Do not duplicate task/instance models.
- Include metadata, identity, version, origin, fixtures, and capability report hooks.

**Likely files**:

```text
src/ctxbench/dataset/package.py
src/ctxbench/dataset/capabilities.py
src/ctxbench/dataset/__init__.py
tests/test_dataset_package_contract.py
```

**Surface sketch**:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DatasetPackage(Protocol):
    def metadata(self) -> DatasetMetadata: ...
    def identity(self) -> str: ...
    def version(self) -> str: ...
    def origin(self) -> str | None: ...

    # Spec 004 boundary capabilities, carried across distribution boundary.
    def list_instance_ids(self) -> list[str]: ...
    def list_task_ids(self) -> list[str]: ...
    def get_context_artifact(self, instance_id: str, task_id: str, strategy: str, format_name: str) -> object: ...
    def get_evidence_artifact(self, instance_id: str, task_id: str) -> object: ...

    # Required provider-free fixtures.
    def fixtures(self) -> object: ...

    # Optional capabilities.
    def tool_provider(self) -> object | None: ...
    def evaluation_helpers(self) -> object | None: ...
    def strategy_descriptors(self) -> list[StrategyDescriptor] | None: ...

    # Inspection.
    def capability_report(self) -> DatasetCapabilityReport: ...


@dataclass
class StrategyDescriptor:
    # All nine fields required by spec FR-029.
    name: str                         # identifier under which the strategy is exposed
    classification: str               # "canonical", "dataset-specific", or "experimental"
    context_access_mode: str          # how context is exposed to the model under test
    inline_vs_operation: str          # "inline" or "operation"
    local_vs_remote: str              # "local" or "remote"
    loop_ownership: str               # "benchmark", "provider", or "dataset"
    metric_provenance: dict[str, str] # per strategy-specific metric → provenance class
    observability_limitations: str    # description of unobservable or provider-side signals
    comparability_implications: str   # notes on comparability with canonical strategies
```

**Validation**:

```bash
pytest tests/test_dataset_package_contract.py
```

`test_dataset_package_contract.py` must assert:
- A class implementing all mandatory methods passes `isinstance(obj, DatasetPackage)`.
- A class missing one mandatory method fails the check.
- `StrategyDescriptor` contains all nine required fields from FR-029 (name, classification, context_access_mode, inline_vs_operation, local_vs_remote, loop_ownership, metric_provenance, observability_limitations, comparability_implications).
- A `StrategyDescriptor` missing any required field is rejected at construction time (or by inspection validation).

**Commit**:

```text
feat(dataset): add dataset package distribution envelope
```

---

### S2 — Dataset Materialization Cache and Provenance Model

**Goal**: Add local cache support for explicitly fetched external datasets.

**Responsibilities**:

- Determine cache location.
- Store materialized datasets.
- Write materialization manifest.
- Refuse silent overwrite of conflicting materializations.
- Support lookup by identity/version/origin/revision.
- Preserve acquisition source and verified checksum provenance.

**Likely files**:

```text
src/ctxbench/dataset/cache.py
src/ctxbench/dataset/materialization.py
tests/test_dataset_cache.py
```

**Manifest example** (all fields required by FR-021, updated for A1-R1):

```json
{
  "datasetId": "ctxbench/lattes",
  "datasetVersion": "0.2.0",
  "requestedVersion": "0.2.0",
  "resolvedRevision": null,
  "origin": "https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.tar.gz",
  "sourceType": "archive-download",
  "descriptorUrl": "https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.dataset.json",
  "descriptorSchemaVersion": 1,
  "archiveUrl": "https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.tar.gz",
  "verifiedSha256": "sha256:...",
  "materializedPath": "~/.cache/ctxbench/datasets/ctxbench/lattes/0.2.0",
  "contentHash": "sha256:...",
  "fetchedAt": "2026-05-11T00:00:00Z",
  "ctxbenchVersion": "...",
  "fetchMethod": "archive-download"
}
```

Note: `materializedPath` is now semantic (`<cache_root>/<id>/<datasetVersion>/`); `resolvedRevision` is `null` for archive-based sources without a Git backend. `descriptorUrl` is populated when descriptor source was used.

Valid `fetchMethod` values: `"git-clone"` (clone a git repository by URL), `"file-copy"` (copy
from a local filesystem path), `"archive-download"` (download and extract a verified archive).
Additional values require a follow-on spec amendment; unknown values MUST be rejected at
manifest-read time with an explicit error.

**Validation**:

```bash
pytest tests/test_dataset_cache.py
```

**Commit**:

```text
feat(dataset): add local materialization cache
```

---

### S3 — Acquisition Source Model and CLI Surface _(SUPERSEDED by S-A1)_

> **Amendment A1**: The CLI surface defined in S3 (positional `<dataset-id>`, `--origin`, `--version`) is superseded by S-A1. Core dispatch and `file-copy` acquisition logic implemented in S3 is preserved as prior work. The `--asset-name` flag is no longer a first-class CLI surface.

**Command** _(superseded — do not use as canonical reference)_:

```bash
ctxbench dataset fetch <dataset-id> --origin <origin> --version <version>
ctxbench dataset fetch <dataset-id> --origin <release-tag-url> --asset-name <asset.tar.gz> --version <version>
ctxbench dataset fetch <dataset-id> --origin <archive.tar.gz-url> --version <version> --sha256 <hex>
ctxbench dataset fetch <dataset-id> --origin <archive.tar.gz-url> --version <version> --sha256-url <url>
```

**Rules**:

- May clone/download/copy from explicit origin.
- Must resolve tag/version to immutable revision when possible.
- Must write materialization manifest (including `fetchMethod` field).
- Must require `--sha256` or `--sha256-url` for archive/release asset acquisition.
- Must not execute dataset code.
- Must not import dataset modules.
- Must not install dependencies.
- Must not auto-register adapters.

**Likely files**:

```text
src/ctxbench/commands/dataset.py
src/ctxbench/cli.py
src/ctxbench/dataset/acquisition.py
src/ctxbench/dataset/materialization.py
tests/test_dataset_fetch.py
```

**Validation**:

```bash
pytest tests/test_dataset_fetch.py
```

`test_dataset_fetch.py` must assert (FR-022):
- `dataset fetch` completes without importing any Python module from the fetched dataset path.
- `dataset fetch` completes without calling `exec`, `eval`, `subprocess.run`, or `importlib.import_module` on dataset content.
- The written manifest contains all required FR-021 fields, including `fetchMethod`.
- archive/release inputs without `--sha256` or `--sha256-url` fail before download/extraction.

**Commit**:

```text
feat(cli): add ctxbench dataset fetch
```

---

### S3a — Verified Archive and Release-Asset Acquisition _(SUPERSEDED by S-A1)_

> **Amendment A1**: The CLI surface in S3a (release tag URL + `--asset-name`) is superseded. Archive download and checksum verification logic is preserved as prior work. S-A1 replaces the argument model with `--dataset-url`/`--sha256`/`--sha256-url`.

**Goal** _(prior work — archived for reference)_: Support verified dataset materialization from direct `.tar.gz` URLs and GitHub Release
tag URLs plus explicit asset names.

**Responsibilities**:

- model archive vs release-asset acquisition sources;
- download archive bytes;
- require checksum verification before extraction;
- resolve release tag URL + asset name to exactly one asset URL;
- record archive/release provenance in the materialization manifest.

**Likely files**:

```text
src/ctxbench/commands/dataset.py
src/ctxbench/dataset/acquisition.py
src/ctxbench/dataset/materialization.py
tests/test_dataset_archive_fetch.py
```

**Validation**:

```bash
pytest tests/test_dataset_archive_fetch.py
```

---

### S3b — Safe Extraction and Manifest Discovery _(PARTIALLY SUPERSEDED by S-A1)_

> **Amendment A1**: Archive safety logic (path traversal rejection, unsafe link rejection, device node rejection) remains valid. Manifest discovery is superseded: the target manifest name changes to `ctxbench.dataset.json` (from an unspecified name). Identity/version validation changes: values now come from the manifest, not from CLI args. S-A1 implements the updated manifest discovery.

**Goal** _(prior work — archive safety remains valid; manifest discovery superseded)_: Safely extract verified archives and locate exactly one dataset package manifest before
cache materialization.

**Responsibilities**:

- reject path traversal, absolute paths, unsafe links, and special files;
- support either a single top-level directory or files extracted at archive root;
- find exactly one dataset manifest;
- fail on no manifest or multiple manifests;
- validate dataset identity/version before materialization.

**Likely files**:

```text
src/ctxbench/dataset/archive.py
src/ctxbench/dataset/acquisition.py
tests/test_dataset_archive_safety.py
tests/test_dataset_manifest_discovery.py
```

**Validation**:

```bash
pytest tests/test_dataset_archive_safety.py
pytest tests/test_dataset_manifest_discovery.py
```

---

### S-A1a — Simplified Fetch Surface and Manifest-Driven Identity (Amendment A1)

**Goal**: Replace the verbose `ctxbench dataset fetch <dataset-id> --origin <origin> --version <version>` CLI surface (implemented in S3/S3a/S3b) with the simplified source-selector UX defined by Amendment A1. Read dataset identity and `datasetVersion` from `ctxbench.dataset.json` during fetch and print the materialized path.

**Supersedes**: CLI surface of S3, argument handling in S3a, manifest discovery target in S3b. Core archive safety logic from S3b/S3e-S3i remains valid.

**Key changes**:

1. `cli.py` fetch parser: remove positional `<dataset-id>`, `--origin`, and mandatory `--version`; add a mutually exclusive `--dataset-url` / `--dataset-file` / `--dataset-dir` selector; add `--sha256-file`; keep `--sha256` and `--sha256-url`; add optional `--id` / `--version` only as validation overrides if implemented.
2. `acquisition.py`: update source classification and checksum handling to use `--dataset-url` / `--dataset-file` / `--dataset-dir` as the primary selector and enforce FR-019a/b/c/d.
3. `archive.py`: discover `ctxbench.dataset.json` as the canonical dataset package manifest and validate identity/version from the manifest, not from required CLI args.
4. `commands/dataset.py` fetch path: dispatch by source type, read identity and `datasetVersion` from the discovered manifest, validate optional `--id` / `--version` overrides when supported, and print identity, `datasetVersion`, verified checksum, and materialized path.

**Likely files**:

```text
src/ctxbench/cli.py
src/ctxbench/commands/dataset.py
src/ctxbench/dataset/acquisition.py
src/ctxbench/dataset/archive.py
tests/test_dataset_fetch.py
tests/test_dataset_archive_fetch.py
tests/test_dataset_manifest_discovery.py
tests/test_dataset_archive_safety.py
```

**Validation**:

```bash
pytest tests/test_dataset_fetch.py
pytest tests/test_dataset_archive_fetch.py
pytest tests/test_dataset_manifest_discovery.py
pytest tests/test_dataset_archive_safety.py
```

**Dependencies**: S2 (cache), S3 (parser wiring base)

**Commit**:

```text
feat(cli): simplify ctxbench dataset fetch UX (Amendment A1)
```

### S-A1b — Shared Cache Root and Materialization Compatibility (Amendment A1)

**Goal**: Add shared cache-root selection for dataset-resolving commands and keep materialization metadata consistent with Amendment A1 without broad schema churn.

**Key changes**:

1. `cli.py`: add `--cache-dir` to `ctxbench dataset inspect` and `ctxbench plan`, and ensure `ctxbench dataset fetch` passes it through.
2. `cache.py`: `DatasetCache` accepts an optional cache root and resolves it in the order constructor arg → `CTXBENCH_DATASET_CACHE` → default location.
3. `commands/dataset.py` inspect path and `commands/plan.py`: construct `DatasetCache` with the resolved cache root.
4. `materialization.py`: add `datasetVersion` as the authoritative dataset package version while keeping `requestedVersion` compatibility explicit and scoped to existing cache and resolver behavior.
5. Update docs/contracts for the simplified fetch UX and shared cache-root behavior.

**Likely files**:

```text
src/ctxbench/cli.py
src/ctxbench/commands/dataset.py
src/ctxbench/commands/plan.py
src/ctxbench/dataset/cache.py
src/ctxbench/dataset/materialization.py
tests/test_dataset_cache.py
tests/test_dataset_inspect.py
tests/test_fake_dataset_workflow.py
tests/test_dataset_distribution_workflow.py
docs/datasets/using-external-datasets.md
specs/003-dataset-distribution/contracts/dataset-commands.md
README.md
```

**Validation**:

```bash
pytest tests/test_dataset_cache.py
pytest tests/test_dataset_inspect.py
pytest tests/test_fake_dataset_workflow.py
pytest tests/test_dataset_distribution_workflow.py -k "plan or inspect"
```

**Dependencies**: S-A1a

**Commit**:

```text
feat(cache): share dataset cache root across fetch inspect and plan
```

---

### S-A1-R1 — Descriptor Acquisition and Cache Reuse (Amendment A1-R1)

**Goal**: Add the distribution descriptor source type, cache pre-check before archive acquisition, no-op behavior when already materialized, conflict detection and `--force` replacement, descriptor-vs-manifest validation, semantic materialization paths, and materialization manifest provenance additions.

**Supersedes/Refines**: Refines S-A1a (CLI surface adds two new source flags) and S-A1b (semantic paths replace content-hash paths). All prior archive safety logic (S3b) and archive-fetch logic (S-A1a) remain valid.

**Key changes**:

1. `src/ctxbench/dataset/descriptor.py` (NEW): `DistributionDescriptor` dataclass with required fields (`id`, `datasetVersion`, `descriptorSchemaVersion`, `archive.type`, `archive.url`, `archive.sha256`) and optional fields. `load_descriptor(source, *, from_url: bool)` handles URL download and local file read. Validates required fields and raises a structured error on missing fields.

2. `src/ctxbench/cli.py`: Add `--descriptor-url` and `--descriptor-file` to the fetch source mutually exclusive group (group now has 5 members). `--id` and `--version` remain optional standalone flags for opaque archive sources.

3. `src/ctxbench/commands/dataset.py`: Enforce `--id`/`--version` at fetch dispatch time when `--dataset-url` or `--dataset-file` is selected. Add dispatch branches for `--descriptor-url` and `--descriptor-file`. Implement no-op reporting when cache pre-check returns a hit.

4. `src/ctxbench/dataset/cache.py`: Update `DatasetCache.materialize()` to use the semantic path `<cache_root>/<dataset_id>/<datasetVersion>/`. Remove content hash from the materialized path. Add `cache_precheck(id, version) -> CacheCheckResult` returning hit (with path), conflict (with conflicting manifest), or miss.

5. `src/ctxbench/dataset/acquisition.py`: After descriptor load or for opaque sources, call `cache_precheck`. On hit: report and return. On conflict without `--force`: raise `DatasetConflictError`. On conflict with `--force`: record conflict, proceed with full validation, then replace after all steps succeed. After extraction: validate descriptor `id`/`datasetVersion` against `ctxbench.dataset.json` (FR-019o).

6. `src/ctxbench/dataset/materialization.py`: Add `descriptorUrl: str | None` and `descriptorSchemaVersion: int | None` to `MaterializationManifest`. Update `fetchMethod` enum if needed. Update manifest read/write.

**Likely files**:

```text
src/ctxbench/dataset/descriptor.py                   # NEW
src/ctxbench/cli.py
src/ctxbench/commands/dataset.py
src/ctxbench/dataset/acquisition.py
src/ctxbench/dataset/cache.py
src/ctxbench/dataset/materialization.py
tests/test_dataset_descriptor.py                     # NEW
tests/test_dataset_fetch.py
tests/test_dataset_cache.py
tests/test_dataset_archive_fetch.py
docs/datasets/using-external-datasets.md
specs/003-dataset-distribution/contracts/dataset-commands.md
```

**Validation**:

```bash
pytest tests/test_dataset_descriptor.py
pytest tests/test_dataset_fetch.py
pytest tests/test_dataset_cache.py
pytest tests/test_dataset_archive_fetch.py
```

`test_dataset_descriptor.py` must assert:
- Valid descriptor with all required fields parses successfully.
- Descriptor with any missing required field raises a structured validation error.
- `load_descriptor` from a local file reads and returns a valid `DistributionDescriptor`.
- `load_descriptor` from a URL (mocked HTTP) reads and returns a valid `DistributionDescriptor`.
- Optional fields (`name`, `description`, `releaseTag`) are accepted when present.

`test_dataset_fetch.py` must assert (A1-R1 additions):
- `--descriptor-url` is accepted; triggers descriptor load, cache pre-check, then archive download when miss.
- `--descriptor-file` is accepted; triggers local descriptor parse, cache pre-check, then archive download when miss.
- `--dataset-url` without `--id` or `--version` fails with a clear error before any download.
- `--dataset-file` without `--id` or `--version` fails with a clear error before any extraction.
- No-op when cache pre-check returns a hit: no download, no extraction, prints existing path.
- Conflict error when cache pre-check returns a conflict and `--force` is not set.
- `--force` proceeds through full validation and replaces the conflicting materialization.
- All 5 source flags are mutually exclusive.

`test_dataset_cache.py` must assert (A1-R1 additions):
- `cache_precheck` returns hit when a matching materialization exists.
- `cache_precheck` returns conflict when same id/version exists with different content identity.
- `cache_precheck` returns miss when no materialization exists.
- Semantic path `<cache_root>/<id>/<version>/` is used in `materialize()`.
- Content hash is recorded in the manifest, not in the path.

**Dependencies**: S-A1b (all prior fetch slices must be complete)

**Commit**:

```text
feat(fetch): add descriptor-based acquisition and cache reuse (A1-R1)
```

---

### S4 — Dataset Resolver and Conflict Detection

**Goal**: Resolve experiment dataset references to exactly one local/cached dataset package.

**Rules**:

- Accept local path references.
- Accept cached id/version references.
- Refuse missing datasets.
- Refuse ambiguous datasets.
- Refuse multiple datasets per experiment.
- Never fetch during lifecycle commands.
- Never branch on dataset-specific identity.

**Compatibility requirements**:

- Accept legacy string-path experiment input unchanged.
- Accept `{ "root": ... }` experiment input unchanged.
- Reject `datasets` or any multi-dataset declaration with an explicit error.
- Normalize both local-path forms into one resolved-reference shape used by planning.

**Likely files**:

```text
src/ctxbench/dataset/resolver.py
src/ctxbench/dataset/conflicts.py
src/ctxbench/benchmark/models.py
tests/test_dataset_resolver.py
tests/test_dataset_conflicts.py
```

**Experiment examples**:

Cached dataset:

```json
{
  "dataset": {
    "id": "ctxbench/lattes",
    "version": "v0.1.0"
  }
}
```

Local path dataset:

```json
{
  "dataset": {
    "root": "../ctxbench-lattes"
  }
}
```

Invalid multi-dataset:

```json
{
  "datasets": [
    {"id": "ctxbench/lattes", "version": "v0.1.0"},
    {"id": "ctxbench/software-repos", "version": "v0.1.0"}
  ]
}
```

**Validation**:

```bash
pytest tests/test_dataset_resolver.py
pytest tests/test_dataset_conflicts.py
```

Resolver coverage must also assert:

- `dataset: "path"` and `dataset: { "root": "path" }` resolve equivalently;
- path-based datasets remain supported without cache materialization;
- multi-dataset declarations fail before any resolution attempt.

**Commit**:

```text
feat(dataset): resolve cached datasets and reject ambiguous references
```

---

### S5 — `ctxbench dataset inspect`

**Goal**: Add read-only inspection of dataset metadata and capabilities.

`ctxbench dataset inspect` calls the same capability validation logic used by `ctxbench plan` (FR-028). The shared logic lives in `src/ctxbench/dataset/validation.py`; both `inspect.py` and `plan.py` call it. This guarantees that conformance gaps are surfaced identically in both commands.

`ctxbench dataset inspect` also calls the conflict-detection logic from `conflicts.py` before reporting results (FR-039). If the reference is ambiguous, inspect fails and lists the conflicting candidates.

**Command**:

```bash
ctxbench dataset inspect <dataset-ref>
ctxbench dataset inspect <dataset-ref> --json
```

**Output includes** (all fields required by FR-026):

- identity;
- version;
- origin;
- resolved revision;
- materialized path;
- content hash;
- metadata;
- mandatory capabilities and whether each is available;
- optional capabilities and whether each is available;
- contributed tools;
- evaluation helpers;
- strategy descriptors;
- missing mandatory capabilities;
- non-conformant strategy descriptors;
- conformance status.

**Likely files**:

```text
src/ctxbench/commands/dataset.py
src/ctxbench/dataset/inspect.py
src/ctxbench/dataset/validation.py      # NEW — shared capability validation (FR-028)
src/ctxbench/dataset/conflicts.py       # already defined in S4; called here for FR-039
tests/test_dataset_inspect.py
```

**Dependencies**: S4 (resolver and conflicts.py must exist before inspect can call them).

**Validation**:

```bash
pytest tests/test_dataset_inspect.py
```

`test_dataset_inspect.py` must assert (FR-039): when the local cache contains two conflicting materializations for the same id+version, `dataset inspect` fails with an error listing both candidates.

**Commit**:

```text
feat(cli): add ctxbench dataset inspect
```

---

### S6 — Planning Integration

**Goal**: Make `ctxbench plan` use the resolver and package validation.

**Changes**:

- Resolve dataset before planning (calls resolver from S4).
- Call shared capability validation from `validation.py` (same function used by `dataset inspect`, per FR-028).
- Validate single-dataset model.
- Print/log capability summary.
- Persist full dataset provenance and capability report in `manifest.json`.
- Pass resolved package into trial generation.
- Stop instantiating `DatasetProvider` directly from path inside planning/generation logic.

**Likely files**:

```text
src/ctxbench/commands/plan.py
src/ctxbench/benchmark/runspec_generator.py
src/ctxbench/dataset/provider.py
src/ctxbench/dataset/validation.py      # shared with S5
tests/test_dataset_distribution_workflow.py
tests/test_dataset_path_compatibility.py
```

**Validation**:

```bash
pytest tests/test_dataset_distribution_workflow.py -k plan
pytest tests/test_dataset_path_compatibility.py
```

Planning coverage must also assert:

- the plan path accepts both string-path and `{root}` dataset inputs;
- planning writes resolved dataset provenance for local-path datasets;
- planning rejects `datasets` before trial expansion.

**Commit**:

```text
refactor(plan): resolve dataset package before trial planning
```

---

### S7 — Provenance Propagation Across Artifacts

**Goal**: Preserve dataset provenance unchanged from planning through execution, evaluation, and export.

**Artifacts** (all required by FR-044):

- `manifest.json`;
- `trials.jsonl`;
- `responses.jsonl`;
- `evals.jsonl`;
- `judge_votes.jsonl`;
- `results.csv` or export manifest.

**Fields** (required by FR-042):

```text
dataset.id
dataset.version
dataset.origin
dataset.resolvedRevision
dataset.contentHash
dataset.materializedPath    # added for operational reproducibility; not required by spec
```

Note: `materializedPath` is additive. It records where the dataset was materialized at run time and may become stale if the cache is reorganized. It MUST NOT be used as the authoritative identity or version field.

**Serializer requirements**:

- `RunSpec` persistence must include the resolved dataset provenance selected during planning.
- `RunResult` persistence must pass through the same dataset provenance unchanged.
- `EvaluationItemResult` persistence must include dataset provenance in `evals.jsonl`.
- `judge_votes.jsonl` rows must also include dataset provenance; this is required because vote rows
  are first-class artifacts under FR-044.
- Trace files may reference the same run/eval IDs but do not become the authoritative source for
  dataset provenance.

**Artifact-only command requirements**:

- `export` must read dataset provenance from `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`,
  or `manifest.json`; it must not resolve datasets again.
- `status` remains artifact-driven and must not gain a dataset-resolution dependency.
- `results.csv` must either carry dataset columns directly or be accompanied by an export manifest
  that carries them. The implementation must choose one explicit representation before tasks.

**Likely files**:

```text
src/ctxbench/benchmark/models.py
src/ctxbench/benchmark/executor.py
src/ctxbench/commands/execute.py
src/ctxbench/commands/eval.py
src/ctxbench/commands/export.py
src/ctxbench/commands/status.py
src/ctxbench/benchmark/results.py
docs/architecture/artifact-contracts.md
tests/test_dataset_provenance_artifacts.py
```

**Validation**:

```bash
pytest tests/test_dataset_provenance_artifacts.py
```

`test_dataset_provenance_artifacts.py` must assert that all six artifact types contain `dataset.id` and `dataset.version`, and that these fields are identical across all artifacts for the same run (FR-043 and FR-045).

It must also assert:

- `evals.jsonl` carries dataset provenance, not just trials/responses;
- `judge_votes.jsonl` carries dataset provenance, not just trial identifiers;
- `export` does not require reopening the dataset root when provenance is already present in
  artifacts;
- `status` remains functional when the original dataset path is absent after planning/execution.

Manual spot checks:

```bash
jq '.dataset.id, .dataset.version, .dataset.origin' outputs/*/manifest.json
jq '.dataset.id, .dataset.version' outputs/*/trials.jsonl | head
jq '.dataset.id, .dataset.version' outputs/*/responses.jsonl | head
jq '.dataset.id, .dataset.version' outputs/*/evals.jsonl | head
jq '.dataset.id, .dataset.version' outputs/*/judge_votes.jsonl | head
```

**Commit**:

```text
feat(artifacts): propagate dataset provenance across phases
```

---

### S8 — Lifecycle No-Network Enforcement

**Goal**: Ensure lifecycle commands never fetch remote datasets.

**Commands affected**:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

**Behavior**:

- `plan`: missing dataset fails with remediation message.
- `plan`: ambiguous dataset fails with conflict details.
- `execute`: fail if the planned dataset materialization/local package is no longer available.
- `eval`: fail if required dataset-backed evidence is unavailable from the planned dataset
  materialization/local package.
- `export` and `status`: do not fetch and do not require dataset re-resolution when artifacts
  already contain sufficient provenance.
- archive/release acquisition logic is unreachable from lifecycle command paths.
- No network acquisition during lifecycle phases.

**Likely files**:

```text
src/ctxbench/dataset/resolver.py
src/ctxbench/commands/plan.py
src/ctxbench/benchmark/executor.py
src/ctxbench/benchmark/evaluation.py
src/ctxbench/commands/export.py
src/ctxbench/commands/status.py
tests/test_lifecycle_no_network.py
```

**Validation**:

```bash
pytest tests/test_lifecycle_no_network.py
```

`test_lifecycle_no_network.py` must distinguish command classes:

- `plan` rejects unresolved remote references without fetching;
- `execute` and `eval` reject missing planned materializations without fetching;
- `export` and `status` succeed from artifacts alone and do not call materialization/fetch code.

**Commit**:

```text
test(dataset): enforce no implicit dataset fetch during lifecycle commands
```

---

### S9 — Lattes Dataset Package Conformance

**Goal**: Make `ctxbench/lattes` the first real conformance target.

**Notes**:

- Temporary in-repo wrapper is allowed only as an implementation bridge.
- The final target remains external `ctxbench/lattes`.
- Lattes-specific readers, tools, artifact mappings, fixtures, and evidence providers are distribution debt until moved.
- Any divergence between this contract and current `ctxbench/lattes` behavior MUST be resolved by changing `ctxbench/lattes`, not by widening generic core behavior (FR-047).

**Provider-free mechanism**: The conformance workflow uses pytest fixtures that monkeypatch the
provider adapter factory and the judge factory before invoking each lifecycle command function
directly. No `--fake-responder` or `--fake-judge` CLI flags are added to the public CLI; no
provider tokens are consumed.

Monkeypatch targets:

- `ctxbench.benchmark.executor` — provider-factory lookup replaced by a callable returning a
  `FakeResponder` that yields pre-scripted responses.
- `ctxbench.benchmark.evaluation` — judge-factory lookup replaced by a callable returning a
  `FakeJudge` that yields pre-scripted evaluations.

The fakes are defined in `tests/fixtures/lattes_provider_free/fake_responder.py` and
`tests/fixtures/lattes_provider_free/fake_judge.py`. They are applied via
`monkeypatch.setattr(...)` in pytest fixtures in `tests/conftest.py` (or a
`tests/fixtures/lattes_provider_free/conftest.py` if scoped separately). The end-to-end
sequence is encapsulated in `tests/test_lattes_dataset_conformance.py`.

**Validation workflow**: fetch and inspect can be verified as direct CLI invocations; plan,
execute, eval, and export run inside pytest with monkeypatched providers.

```bash
# Dataset acquisition and inspection — run directly
ctxbench dataset fetch ctxbench/lattes --origin tests/fixtures/lattes_provider_free --version 0.1.0-test
ctxbench dataset inspect ctxbench/lattes@0.1.0-test

# Full provider-free end-to-end workflow — run via pytest (monkeypatching active)
pytest tests/test_lattes_dataset_conformance.py
```

**Static leakage check** (FR-003): after S9 wraps Lattes behind the package boundary:

```bash
grep -rn "from ctxbench.datasets.lattes" src/ctxbench/benchmark/ src/ctxbench/ai/ src/ctxbench/commands/
# Expected: zero hits
```

**Likely files**:

```text
src/ctxbench/datasets/lattes/package.py
src/ctxbench/benchmark/executor.py
tests/fixtures/lattes_provider_free/
tests/test_lattes_dataset_package.py
tests/test_lattes_dataset_conformance.py
```

**Validation**:

```bash
pytest tests/test_lattes_dataset_package.py
pytest tests/test_lattes_dataset_conformance.py
```

**Commit**:

```text
test(lattes): add provider-free lattes package conformance workflow
```

---

### S10 — Fake Dataset Provider-Free Workflow

**Goal**: Keep a synthetic provider-free dataset for generic contract validation.

**Purpose**:

- Validate generic mechanics.
- Validate Spec 004 boundary neutrality.
- Validate no provider calls.
- Validate no Lattes-specific terms.

**Not purpose**:

- Does not satisfy Lattes conformance.

**Likely files**:

```text
tests/fixtures/fake_dataset/
tests/test_fake_dataset_workflow.py
tests/test_dataset_path_compatibility.py
```

**Validation**:

```bash
pytest tests/test_fake_dataset_workflow.py
pytest tests/test_dataset_path_compatibility.py
```

**Commit**:

```text
test(dataset): add fake dataset provider-free workflow
```

---

### S11 — Documentation and Architecture Update

**Goal**: Update all docs affected by dataset acquisition, inspection, resolution, and package authoring.

**Required files**:

```text
README.md
docs/architecture/README.md
docs/architecture/workflow.md
docs/architecture/cli-architecture.md
docs/architecture/container.md
docs/architecture/component.md
docs/architecture/dynamic.md
docs/architecture/vocabulary.md
docs/architecture/artifact-contracts.md
docs/datasets/using-external-datasets.md
docs/datasets/creating-a-dataset.md
specs/003-dataset-distribution/quickstart.md
specs/003-dataset-distribution/contracts/dataset-commands.md
```

**Required content**:

- New remote dataset workflow:

  ```text
  ctxbench dataset fetch
  ctxbench dataset inspect
  ctxbench plan
  ctxbench execute
  ctxbench eval
  ctxbench export
  ```

- Local path workflow.
- Dataset author guide.
- Dataset repository layout.
- `ctxbench.dataset.json` or equivalent package manifest.
- Required metadata.
- Required capabilities.
- Optional capabilities.
- Strategy descriptor comparability fields.
- Conflict and ambiguity errors.
- Single-dataset experiment rule.
- No implicit network in lifecycle commands.
- Relationship with Spec 004.

**Documentation-specific files**:

#### `docs/datasets/using-external-datasets.md`

> **Amendment A1**: Must use the simplified source-selector UX, not the old `<dataset-id> --origin --version` form.

Must explain:

```bash
ctxbench dataset fetch \
  --dataset-url https://github.com/ctxbench/lattes/releases/download/v0.1.0/lattes.tar.gz \
  --sha256-url https://github.com/ctxbench/lattes/releases/download/v0.1.0/lattes.tar.gz.sha256

ctxbench dataset inspect ctxbench/lattes@v0.1.0

ctxbench plan experiments/lattes-baseline.json --output outputs/lattes-baseline
ctxbench execute outputs/lattes-baseline/trials.jsonl
ctxbench eval outputs/lattes-baseline/responses.jsonl
ctxbench export outputs/lattes-baseline/evals.jsonl --output outputs/lattes-baseline/results.csv
```

#### `docs/datasets/creating-a-dataset.md`

Must explain:

- dataset identity;
- versioning;
- origin;
- metadata;
- instances;
- tasks;
- context artifacts;
- evidence artifacts;
- fixtures;
- optional tools;
- optional evaluation helpers;
- optional strategy descriptors;
- provider-free validation;
- how to test with `ctxbench dataset inspect`;
- how to avoid identity/version conflicts.

**Validation checklist**:

```text
[ ] README quickstart includes dataset fetch/inspect for remote datasets.
[ ] workflow.md diagram includes dataset acquisition and cache.
[ ] cli-architecture.md separates lifecycle from dataset-management commands.
[ ] container.md shows remote dataset repository and local dataset cache.
[ ] component.md shows DatasetResolver, DatasetPackage boundary, and artifact store.
[ ] dynamic.md includes fetch, inspect, missing dataset, ambiguous dataset flows.
[ ] vocabulary.md defines all ten new dataset distribution terms:
      dataset repository, dataset package, dataset materialization, dataset cache,
      dataset resolver, dataset capability report, dataset origin, resolved revision,
      content hash, single-dataset experiment.
[ ] artifact-contracts.md documents dataset provenance fields.
[ ] using-external-datasets.md exists.
[ ] creating-a-dataset.md exists.
[ ] Spec 004 ownership of internal boundaries is referenced.
```

**Commit**:

```text
docs(dataset): document external dataset workflow and authoring guide
```

---

## Validation Plan

### Unit Tests

```bash
pytest tests/test_dataset_package_contract.py
pytest tests/test_dataset_cache.py
pytest tests/test_dataset_fetch.py
pytest tests/test_dataset_inspect.py
pytest tests/test_dataset_resolver.py
pytest tests/test_dataset_conflicts.py
pytest tests/test_dataset_provenance_artifacts.py
pytest tests/test_lifecycle_no_network.py
pytest tests/test_lattes_dataset_package.py
```

### Integration Tests

```bash
pytest tests/test_dataset_distribution_workflow.py
pytest tests/test_fake_dataset_workflow.py
pytest tests/test_lattes_dataset_conformance.py
```

### Manual Checks

```bash
ctxbench dataset fetch ctxbench/fake-dataset --origin tests/fixtures/fake_dataset --version 0.1.0
ctxbench dataset inspect ctxbench/fake-dataset@0.1.0 --json
ctxbench plan examples/fake-dataset.json --output outputs/fake-dataset
ctxbench execute outputs/fake-dataset/trials.jsonl
ctxbench eval outputs/fake-dataset/responses.jsonl
ctxbench export outputs/fake-dataset/evals.jsonl --output outputs/fake-dataset/results.csv
```

### Provenance Checks

```bash
jq '.dataset.id, .dataset.version, .dataset.origin' outputs/fake-dataset/manifest.json
jq '.dataset.id, .dataset.version' outputs/fake-dataset/trials.jsonl | head
jq '.dataset.id, .dataset.version' outputs/fake-dataset/responses.jsonl | head
jq '.dataset.id, .dataset.version' outputs/fake-dataset/evals.jsonl | head
```

### No-Network Checks

Use tests/mocks to assert that lifecycle commands do not call fetch/materialization network code.

## Pre-Task Clarifications Required

Before task generation, the plan treats the following as fixed implementation decisions:

1. `dataset: "path"` and `dataset: { "root": ... }` remain accepted compatibility inputs.
2. `export` and `status` are artifact-only commands and must not be forced through dataset
   re-resolution.
3. `evals.jsonl` and `judge_votes.jsonl` both gain first-class `dataset` provenance fields.
4. Generic execution/evaluation work includes removal of direct Lattes imports from
   `benchmark/executor.py`.
5. Dataset loss after planning is handled differently by command: blocking for `execute`/`eval`,
   non-blocking for artifact-only `export`/`status`.

### Documentation Checks

```bash
test -f docs/datasets/using-external-datasets.md
test -f docs/datasets/creating-a-dataset.md
grep -R "ctxbench dataset fetch" README.md docs specs/003-dataset-distribution
grep -R "ctxbench dataset inspect" README.md docs specs/003-dataset-distribution
grep -R "single-dataset" docs specs/003-dataset-distribution
```

## Risks

### R1 — Conflict with Spec 004

Risk: `DatasetPackage` accidentally redefines internal boundary semantics.

Mitigation: Document that DatasetPackage is the distribution envelope and references Spec 004 for internal semantics.

### R2 — Dataset cache becomes a registry

Risk: materialization cache grows into a plugin registry.

Mitigation: no auto-discovery, no dynamic loading, no remote code execution, explicit id/origin/version only.

### R3 — `dataset fetch` executes remote code

Risk: convenience features accidentally import or install dataset packages.

Mitigation: tests and code review rule: fetch can only materialize and inspect declarative manifests; it cannot import dataset code.

### R4 — Multi-dataset pressure

Risk: users request experiments spanning multiple datasets.

Mitigation: explicit single-dataset rule; recommend separate experiments and downstream analysis; defer study/suite orchestration.

### R5 — Provenance drift

Risk: artifact phases recompute or lose dataset provenance.

Mitigation: propagate from planning manifest; assert unchanged fields in tests.

### R6 — Compatibility break for path-based experiments

Risk: resolver work accidentally removes support for `dataset: "path"` or changes the shape of
existing local-path fixtures without a migration path.

Mitigation: keep string-path and `{root}` inputs as explicit compatibility cases; add dedicated
tests for both forms before broader resolver refactors.

### R7 — Artifact-only commands become needlessly stateful

Risk: `export` or `status` start requiring the original dataset checkout/materialization even
though artifacts already carry enough provenance.

Mitigation: keep these commands artifact-driven; test them after deleting or moving the original
dataset path.

### R6 — Documentation drift

Risk: architecture docs continue showing old workflow starting directly at `experiment.json → ctxbench plan`.

Mitigation: S11 is mandatory and validation checks require fetch/inspect docs.

## Constitution Check

### Principle VII — Boundary Isolation

Satisfied by DatasetPackage distribution envelope, DatasetResolver, and prohibition on core importing dataset-specific modules.

### Principle VIII — Reproducibility

Satisfied by explicit identity, version, origin, resolved revision, materialized path, and content hash provenance.

### Principle X — Provider-free Validation

Satisfied by fake dataset workflow and Lattes provider-free conformance workflow.

### Principle XII — Simplicity

Maintained by:

- single-dataset experiments;
- no plugin registry;
- no dynamic remote code execution;
- no implicit lifecycle network access;
- explicit fetch/inspect commands.

### Principle VI — Strategy Comparability

Satisfied by required strategy descriptor comparability fields for dataset-contributed strategies.

## Commit Sequence

```text
feat(dataset): add dataset package distribution envelope
feat(dataset): add local materialization cache
feat(cli): add ctxbench dataset fetch
feat(dataset): add verified archive acquisition sources
feat(dataset): add safe archive extraction and manifest discovery
feat(dataset): resolve cached datasets and reject ambiguous references
feat(cli): add ctxbench dataset inspect
refactor(plan): resolve dataset package before trial planning
feat(artifacts): propagate dataset provenance across phases
test(dataset): enforce no implicit dataset fetch during lifecycle commands
test(lattes): add provider-free lattes package conformance workflow
test(dataset): add fake dataset provider-free workflow
docs(dataset): document external dataset workflow and authoring guide
feat(cli): simplify ctxbench dataset fetch UX (Amendment A1)
feat(cache): share dataset cache root across fetch inspect and plan
feat(fetch): add descriptor-based acquisition and cache reuse (A1-R1)
```
