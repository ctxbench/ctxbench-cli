# Spec: Dataset Distribution

**Branch**: `feat/dataset-distribution`  
**Created**: 2026-05-11  
**Status**: Draft  
**Related specs**: Spec 001, Spec 002, Spec 004

## Goal

Define the distribution boundary between `ctxbench-cli` and external dataset repositories/packages.

This specification defines:

- how externally distributed datasets are acquired and materialized locally;
- how experiments reference one external dataset package;
- how `ctxbench-cli` resolves, inspects, and validates dataset package metadata and capabilities;
- how dataset identity, origin, version, resolved revision, and content provenance are recorded in artifacts;
- how dataset-provided optional extensions are made explicit and comparable;
- how Lattes-specific code and data currently embedded in `ctxbench-cli` are classified as distribution debt and targeted for relocation to `ctxbench/lattes`.

The `ctxbench/lattes` repository is the first real conformance target and reference implementation. It is not the contract definition.

This specification operationalizes:

- Constitution Principle VII — Boundary Isolation;
- Constitution Principle VIII — Reproducibility;
- Constitution Principle X — Provider-free Validation;
- Constitution Principle XII — Simplicity.

## Relationship to Spec 004

Spec 004 owns the internal benchmark core vs. dataset/domain adapter boundary contracts:

- instance loading;
- task loading;
- context artifact provider;
- evidence artifact provider;
- tool provider;
- evaluation evidence provider;
- dataset/instance enumeration.

This spec does **not** redefine those internal contracts. It carries them across the **external distribution boundary** and adds only distribution-specific responsibilities:

- dataset metadata;
- dataset identity;
- dataset version;
- dataset origin;
- explicit acquisition/materialization;
- local materialization cache;
- capability inspection;
- fixture coverage;
- provenance recording;
- conflict detection;
- comparability metadata for dataset-contributed strategies.

`ctxbench dataset fetch` and `ctxbench dataset inspect` are dataset-management commands. They are not benchmark lifecycle phases and do not change the lifecycle vocabulary governed by Spec 001 and Spec 004:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

## Scope

### In Scope

- Distribution boundary between `ctxbench-cli` and external dataset repositories/packages.
- Dataset package contract at the distribution boundary.
- Explicit acquisition/materialization of an external dataset repository/package into a local CTXBench dataset cache.
- Read-only dataset inspection before benchmark execution.
- Dataset reference and resolution from experiment configuration.
- Single-dataset experiment model: each experiment references exactly one dataset package.
- Dataset identity, version, origin, resolved revision, materialized path, and content hash provenance.
- Dataset conflict detection and ambiguity handling.
- Provider-free validation for dataset package conformance.
- `ctxbench/lattes` as the first real conformance target.
- Documentation updates for:
  - new researcher workflow;
  - dataset authoring;
  - architecture diagrams;
  - CLI reference;
  - artifact provenance;
  - vocabulary;
  - conflict handling.

### Out of Scope

- Implementing a second concrete research domain, such as software repositories.
- Supporting multiple datasets in a single experiment.
- Fully migrating Lattes data, fixtures, or artifacts in this spec.
- Refactoring Lattes internals or finalizing Lattes-internal naming.
- Designing a generic plugin framework, package marketplace, dynamic loader, opaque auto-discovery mechanism, or runtime-extensible adapter registry.
- Executing code from a remote dataset during acquisition.
- Implicit network access during benchmark lifecycle phases.
- Provider-backed execution for contract authoring or validation.
- Changing model provider adapters.
- Redesigning artifact roles or representations beyond provenance additions governed by Spec 002.
- Changing lifecycle phase names or generic vocabulary.

## Key Decisions

### D1 — Dataset acquisition is explicit

Datasets that live in external repositories are not fetched implicitly.

A researcher obtains a remote dataset explicitly using source-selector flags. Dataset identity and version are read from the dataset package manifest (`ctxbench.dataset.json`). Canonical workflows:

**Remote archive:**
```bash
ctxbench dataset fetch \
  --dataset-url <dataset.tar.gz-url> \
  --sha256-url <dataset.sha256-url>
```

**Local archive:**
```bash
ctxbench dataset fetch \
  --dataset-file <dataset.tar.gz> \
  --sha256-file <dataset.sha256>
```

**Local unpacked directory:**
```bash
ctxbench dataset fetch \
  --dataset-dir <dataset-root>
```

The old form `ctxbench dataset fetch <dataset-id> --origin <origin> --version <version>` is **superseded by Amendment A1** and MUST NOT be the canonical workflow. See D9–D15 below.

The fetch command materializes the dataset into a local CTXBench dataset cache and records acquisition provenance.

### D2 — No implicit network access in lifecycle phases

The following commands MUST NOT fetch remote datasets:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

If a referenced dataset is not available locally, the command fails with an explicit remediation message suggesting `ctxbench dataset fetch`.

### D3 — `dataset fetch` is materialization, not loading

`ctxbench dataset fetch` may clone, download, or copy a declared dataset origin at a declared version into a local cache.

It MUST NOT:

- import Python modules from the dataset;
- execute dataset code;
- run setup scripts;
- install dependencies;
- execute readers, tools, or strategy code;
- dynamically register adapters;
- perform opaque auto-discovery.

For archive-based acquisition, `ctxbench dataset fetch` may also download a release archive asset,
but only when archive integrity is explicitly verified before extraction.

### D4 — `dataset inspect` is read-only

`ctxbench dataset inspect` resolves a local or cached dataset reference, validates metadata and capability declarations, and reports a `DatasetCapabilityReport`.

It MUST NOT:

- fetch remote data;
- create trials;
- write benchmark artifacts;
- execute provider calls;
- register datasets;
- mutate the dataset cache except for optional read-only validation logs if explicitly requested.

### D5 — Materialization cache is not a registry

The local dataset cache stores explicitly fetched datasets and their provenance. It is not a plugin registry, adapter registry, marketplace, or discovery service.

Resolution is based on explicit references:

```text
dataset id
dataset version
origin, when needed for disambiguation
resolved revision, when needed for exact reproduction
```

### D6 — Single-dataset experiment model

Each `experiment.json` references exactly one dataset package.

`ctxbench-cli` may materialize and inspect many datasets locally, but one experiment plans trials over one dataset only.

Cross-dataset comparison is performed by separate experiments and downstream analysis, or by a future study/suite orchestration spec.

### D7 — DatasetPackage is the distribution envelope

`DatasetPackage` exposes the distribution boundary. Its internal capabilities map to Spec 004 boundary contracts, but this spec does not redefine their semantics.

### D8 — Existing models are reused where possible

This spec MUST NOT introduce parallel task/instance models that duplicate existing internal models.

For this spec, the implementation may use aliases or adapter-facing wrappers over current models. Renaming or replacing task/instance models belongs to the domain-boundary implementation work, not to this distribution slice.

### D9 — Dataset identity and version come from the manifest (Amendment A1)

Dataset identity MUST be read from the dataset package manifest (`ctxbench.dataset.json`).
Dataset version (`datasetVersion`) MUST be read from the dataset package manifest.

Neither identity nor version must be required as positional arguments or mandatory CLI flags in the common `fetch` workflow. Optional user-provided `--id` or `--version` flags MAY exist only as validation overrides, not as the source of truth.

### D10 — Dataset package manifest is named `ctxbench.dataset.json` (Amendment A1)

The canonical dataset package manifest MUST be named `ctxbench.dataset.json` to avoid confusion with the benchmark lifecycle `manifest.json`.

### D11 — Version terminology is explicit and unambiguous (Amendment A1)

The spec distinguishes:

- `datasetVersion`: authoritative version of the dataset package contents; read from `ctxbench.dataset.json`;
- `manifestSchemaVersion`: version of the `ctxbench.dataset.json` schema format;
- `ctxbenchVersion`: version of the CTXBench CLI/framework;
- `releaseTag`: distribution tag associated with an archive or release asset; not the authoritative dataset version;
- `contentHash` / `verifiedSha256`: integrity and exact content identity, not semantic version.

The field name `version` in experiment references means `datasetVersion`.

### D12 — Fetch source selection is exclusive (Amendment A1)

Exactly one of the following source flags MUST be provided to `ctxbench dataset fetch`:

```text
--dataset-url   — remote .tar.gz archive URL
--dataset-file  — local .tar.gz archive path
--dataset-dir   — local unpacked dataset directory
```

Providing none or more than one is an error.

### D13 — User chooses the cache root, not the final internal path (Amendment A1)

Dataset materialization happens inside a dataset cache.

The user may choose the cache root using `--cache-dir <path>` or the environment variable `CTXBENCH_DATASET_CACHE`. If neither is provided, CTXBench uses its default dataset cache location.

The final materialized path is computed by CTXBench from dataset identity, `datasetVersion`, and content identity. The user must not be required to provide the exact final materialized directory.

### D14 — Cache root selection is shared across dataset commands (Amendment A1)

The same cache root selection mechanism must be available to all commands that resolve cached datasets. At minimum: `ctxbench dataset fetch`, `ctxbench dataset inspect`, and `ctxbench plan` must support cache root selection consistently.

`export` and `status` are artifact-only commands and must not require dataset cache access when sufficient provenance is already present in lifecycle artifacts.

### D15 — Fetch must report the materialized path (Amendment A1)

After successful materialization, `ctxbench dataset fetch` MUST print:

- dataset identity;
- `datasetVersion`;
- verified checksum or content hash when available;
- final materialized path.

## Requirements

### Core vs. External Distribution

- **FR-001**: `ctxbench-cli` MUST support datasets distributed by external repositories or packages. The benchmark MUST function with datasets physically located outside the `ctxbench-cli` repository.
- **FR-002**: `ctxbench-cli` MUST NOT require any concrete dataset payload to live inside its own repository.
- **FR-003**: Generic benchmark core MUST NOT import, reference, or branch on dataset-specific modules, identifiers, readers, tools, artifact mappings, or payload structures.
- **FR-004**: Lattes-specific readers, artifact mappings, fixtures, evidence providers, and tool definitions belong in `ctxbench/lattes` and MUST NOT remain in `ctxbench-cli` after the migration enabled by this spec.

### Dataset Package Contract — Mandatory Extension Points

The dataset package MUST expose the following responsibilities. The concrete implementation surface is resolved in the plan, while the internal semantics of boundary capabilities remain owned by Spec 004.

- **FR-005**: **Dataset metadata.** The dataset package MUST expose human-readable metadata describing purpose, domain, intended uses, known limitations, license/terms pointer where applicable, and citation pointer where applicable.
- **FR-006**: **Dataset identity.** The dataset package MUST expose a stable, unique dataset identity.
- **FR-007**: **Dataset version.** The dataset package MUST expose a stable dataset version identifying the dataset revision.
- **FR-008**: **Dataset origin.** The dataset package MUST expose or be associated with an origin sufficient for another researcher to obtain it.
- **FR-009**: **Instance loading.** The dataset package MUST expose the instance-loading capability defined by Spec 004.
- **FR-010**: **Task loading.** The dataset package MUST expose the task-loading capability defined by Spec 004.
- **FR-011**: **Artifact location and resolution.** The dataset package MUST expose the means to locate and resolve the artifacts required by the benchmark. File layout remains internal to the package.
- **FR-012**: **Context artifact provider.** The dataset package MUST expose the context-artifact provider boundary defined by Spec 004.
- **FR-013**: **Evidence artifact provider.** The dataset package MUST expose the evidence-artifact provider boundary defined by Spec 004.
- **FR-014**: **Format-specific readers.** The dataset package MUST expose or compose internally the readers required for its payload formats. The benchmark core MUST NOT override dataset-supplied readers.
- **FR-015**: **Fixtures for provider-free tests.** The dataset package MUST expose at least one fixture or example sufficient to exercise mandatory extension points without real provider calls.

### Dataset Package Contract — Optional Extension Points

- **FR-016**: **Tool provider.** A dataset package MAY expose a tool provider for strategies requiring tools. If unavailable, tool-based strategies MUST surface a clear capability-unavailable path and MUST NOT fall back to embedded dataset-specific behavior.
- **FR-017**: **Evaluation helpers.** A dataset package MAY expose evaluation helpers. Their use MUST be recorded as dataset-supplied behavior in evaluation traces.
- **FR-018**: **Strategy descriptors.** A dataset package MAY contribute strategy presets, dataset-specific strategies, or experimental strategy descriptors. All dataset-contributed strategies MUST satisfy FR-026.

### Dataset Acquisition and Materialization

- **FR-019**: `ctxbench-cli` MUST provide an explicit dataset acquisition command `ctxbench dataset fetch` using source-selector flags. The canonical forms are:

  ```bash
  # Remote archive
  ctxbench dataset fetch --dataset-url <url> --sha256-url <sha256-url>
  ctxbench dataset fetch --dataset-url <url> --sha256 <hex>

  # Local archive
  ctxbench dataset fetch --dataset-file <path> --sha256-file <path>
  ctxbench dataset fetch --dataset-file <path> --sha256 <hex>

  # Local unpacked directory
  ctxbench dataset fetch --dataset-dir <path>
  ```

  The form `ctxbench dataset fetch <dataset-id> --origin <origin> --version <version>` is **superseded by Amendment A1** and MUST NOT be the canonical workflow.

- **FR-019a**: Exactly one source flag (`--dataset-url`, `--dataset-file`, or `--dataset-dir`) MUST be provided; providing none or more than one is an error.

- **FR-019b**: `--dataset-url` MUST require either `--sha256` (inline hex string) or `--sha256-url` (URL to a checksum file).

- **FR-019c**: `--dataset-file` MUST require either `--sha256` (inline hex string) or `--sha256-file` (path to a local checksum file).

- **FR-019d**: `--dataset-dir` does NOT require checksum material but the directory MUST contain a valid `ctxbench.dataset.json` manifest.

- **FR-019e**: The canonical dataset package manifest MUST be named `ctxbench.dataset.json`.

- **FR-019f**: Dataset identity and `datasetVersion` MUST be read from `ctxbench.dataset.json` after extraction or discovery. The user MUST NOT be required to provide identity or version as CLI flags in the common workflow. Optional `--id` and `--version` flags MAY exist only as validation overrides.

- **FR-019g**: `datasetVersion` is the authoritative version of the dataset package contents as declared in `ctxbench.dataset.json`. It MUST be clearly distinguished from `manifestSchemaVersion`, `ctxbenchVersion`, `releaseTag`, and `contentHash`.

- **FR-019h**: The user may specify a custom cache root using `--cache-dir` or the environment variable `CTXBENCH_DATASET_CACHE`. When neither is provided, CTXBench uses its default cache location.

- **FR-019i**: After successful materialization, `ctxbench dataset fetch` MUST print the dataset identity, `datasetVersion`, verified checksum (when available), and the final materialized path.

- **FR-019j**: The cache root selection mechanism (D14) MUST be consistently available to `ctxbench dataset fetch`, `ctxbench dataset inspect`, and `ctxbench plan`.

- **FR-020**: Dataset acquisition MUST materialize the dataset into a local CTXBench dataset cache.
- **FR-021**: Dataset acquisition MUST record a materialization manifest containing at least:
  - dataset identity (read from `ctxbench.dataset.json`);
  - `datasetVersion` (authoritative version read from `ctxbench.dataset.json`);
  - resolved revision or content identity;
  - origin (source URL or path used for acquisition);
  - acquisition source type;
  - materialized path;
  - verified SHA-256 or content hash when available;
  - acquisition timestamp;
  - CTXBench version (`ctxbenchVersion`);
  - fetch method.
- **FR-022**: Dataset acquisition MUST NOT execute code from the remote dataset repository/package.
- **FR-022a**: When acquisition uses `--dataset-url`, the archive MUST be downloaded before extraction and MUST require explicit SHA-256 verification through either `--sha256` (inline hex) or `--sha256-url` (URL to a checksum file). When acquisition uses `--dataset-file`, SHA-256 verification MUST be required through either `--sha256` or `--sha256-file` (path to a local checksum file).
- **FR-022b**: Archive acquisition MUST fail before extraction if checksum material is missing,
  cannot be obtained, or does not match the downloaded bytes.
- **FR-022c**: Archive extraction MUST reject:
  - path traversal entries;
  - absolute paths;
  - unsafe symlinks;
  - unsafe hardlinks;
  - device nodes;
  - FIFOs;
  - sockets or other special files.
- **FR-022d**: After safe extraction, CTXBench MUST locate exactly one `ctxbench.dataset.json` dataset package manifest. It MUST support either a single top-level directory or files extracted directly at archive root. It MUST fail when no manifest is found or when multiple manifests are found.
- **FR-022e**: After manifest discovery, CTXBench MUST read dataset identity and `datasetVersion` from `ctxbench.dataset.json`. If the user provided optional `--id` or `--version` override flags, CTXBench MUST validate the manifest values against those overrides and fail on mismatch before materialization.
- **FR-022f**: Archive or release-asset acquisition MUST record archive provenance in the
  materialization manifest, including the verified SHA-256 and enough source information to
  reproduce the exact downloaded asset.
- **FR-023**: Lifecycle commands MUST NOT perform implicit dataset acquisition or network fetches.
- **FR-024**: If a lifecycle command references a dataset not available locally, it MUST fail with a clear message naming the missing dataset and suggesting a `ctxbench dataset fetch` command when enough origin/version information is available.

### Dataset Inspection and Discoverability

- **FR-025**: `ctxbench-cli` MUST provide a read-only dataset inspection command:

  ```bash
  ctxbench dataset inspect <dataset-ref>
  ctxbench dataset inspect <dataset-ref> --json
  ```

- **FR-026**: Inspection MUST report:
  - dataset identity;
  - version;
  - origin;
  - resolved revision, if known;
  - materialized path, if cached;
  - content hash, if available;
  - human-readable metadata;
  - mandatory capabilities and whether each is available;
  - optional capabilities and whether each is available;
  - contributed tools, if any;
  - evaluation helpers, if any;
  - strategy descriptors, if any;
  - missing mandatory capabilities;
  - non-conformant strategy descriptors.
- **FR-027**: Inspection MUST be usable before running any benchmark lifecycle phase.
- **FR-028**: The same package validation logic used by `dataset inspect` MUST also be used by `ctxbench plan`; inspection is advisory, while planning remains the provenance-producing validation point.

### Strategy Comparability for Dataset-Contributed Strategies

- **FR-029**: Every dataset-contributed strategy descriptor MUST include:
  - strategy name;
  - classification: canonical preset, dataset-specific, or experimental;
  - context access mode;
  - inline-vs-operation classification;
  - local-vs-remote classification;
  - loop ownership;
  - metric provenance per strategy-specific metric;
  - observability limitations;
  - comparability implications.
- **FR-030**: A dataset-contributed strategy missing any required comparability field MUST be treated as non-conformant.

### Experiment Reference and Resolution

- **FR-031**: Experiment configurations MUST reference exactly one dataset package.
- **FR-032**: An experiment reference MUST be stable and declarative. It MUST NOT require dynamic remote code execution to resolve.
- **FR-033**: A dataset reference MAY use:
  - a local dataset root;
  - a cached dataset identity and version;
  - an origin/version pair that has already been materialized.
- **FR-034**: Experiment references to multiple datasets are out of scope. If an experiment declares `datasets` or otherwise references more than one dataset package, planning MUST fail with an explicit error.
- **FR-035**: `ctxbench plan` MUST resolve the dataset package before planning trials and MUST record the resolved dataset provenance in the planning manifest.
- **FR-036**: The dataset resolver MUST refuse to resolve ambiguous references.

### Dataset Conflicts and Ambiguity

- **FR-037**: The local dataset cache MUST detect ambiguous dataset references.
- **FR-038**: A reference is ambiguous when the same dataset identity and version map to more than one origin, resolved revision, materialized path, or content hash.
- **FR-039**: When ambiguity is detected, `ctxbench dataset inspect` and `ctxbench plan` MUST fail with an explicit error listing conflicting candidates and requiring disambiguation by origin or resolved revision.
- **FR-040**: If a dataset identity/version pair is materialized again and resolves to different content, the command MUST not silently overwrite the existing materialization. It MUST either fail, store a distinct materialization keyed by resolved revision/content hash, or require an explicit force/update flag.
- **FR-041**: Tags or mutable version references MUST be resolved to immutable revisions when possible, and the immutable revision MUST be recorded in provenance.
- **FR-041a**: _(Superseded by Amendment A1)_ Under the simplified fetch UX, GitHub Release asset acquisition uses `--dataset-url` with a direct asset download URL. The release tag URL + `--asset-name` form is no longer a first-class CLI surface. If a release tag URL is provided as `--dataset-url`, the behavior is acquisition-layer implementation detail and is not required by the CLI contract. CTXBench MUST record enough source information in the materialization manifest to reproduce the exact downloaded asset.
- **FR-041b**: Direct archive URL acquisition is a valid acquisition source when checksum
  verification succeeds.

### Dataset Identity, Version, and Provenance in Artifacts

- **FR-042**: Every run MUST record enough information to identify the dataset package origin, identity, version, resolved revision when available, and content hash when available.
- **FR-043**: Dataset provenance recorded at planning time MUST be preserved unchanged through execution, evaluation, and export.
- **FR-044**: Provenance MUST be available in:
  - `manifest.json`;
  - `trials.jsonl`;
  - `responses.jsonl`;
  - `evals.jsonl`;
  - `judge_votes.jsonl` when applicable;
  - `results.csv` or an accompanying export manifest.
- **FR-045**: No phase may silently overwrite, coerce, or recompute dataset identity/version fields from a different source than the planning manifest.

### `ctxbench/lattes` as First Conformance Target

- **FR-046**: `ctxbench/lattes` MUST be treated as the first real dataset package conformance target.
- **FR-047**: Divergence between this contract and current Lattes behavior MUST be resolved by changing `ctxbench/lattes` or amending this spec, not by silently widening generic core behavior.
- **FR-048**: The provider-free validation workflow MUST be re-runnable against `ctxbench/lattes` once the contract is implemented.
- **FR-049**: Fake dataset validation does not satisfy Lattes conformance. It validates generic mechanics only.

### Documentation and Architecture Updates

- **FR-050**: Documentation MUST update the canonical researcher workflow to include explicit dataset acquisition and inspection before planning when the dataset is remote.
- **FR-051**: Documentation MUST explain that local-path datasets can still be used directly, while remote datasets must be materialized explicitly before lifecycle phases.
- **FR-052**: Documentation MUST include a guide for researchers using external datasets.
- **FR-053**: Documentation MUST include a guide for authors creating CTXBench dataset packages.
- **FR-054**: Architecture diagrams MUST distinguish:
  - remote dataset repository;
  - local dataset materialization cache;
  - dataset resolver;
  - dataset package boundary;
  - benchmark lifecycle phases;
  - artifact store.
- **FR-055**: CLI documentation MUST separate lifecycle commands from dataset-management commands.
- **FR-056**: Artifact documentation MUST describe dataset provenance fields and their carriers.
- **FR-057**: Vocabulary documentation MUST define:
  - dataset repository;
  - dataset package;
  - dataset materialization;
  - dataset cache;
  - dataset resolver;
  - dataset capability report;
  - dataset origin;
  - resolved revision;
  - content hash;
  - single-dataset experiment;
  - `datasetVersion` (authoritative version of dataset package contents, from `ctxbench.dataset.json`);
  - `ctxbench.dataset.json` (canonical dataset package manifest name);
  - `manifestSchemaVersion` (version of the `ctxbench.dataset.json` schema format, distinct from `datasetVersion`).
- **FR-058**: Documentation MUST describe dataset conflict/ambiguity errors and how to resolve them.

## Acceptance Scenarios

### External Dataset Acquisition (Remote Archive)

Given a researcher wants to use `ctxbench/lattes` and has a remote `.tar.gz` archive URL and checksum URL,  
When they run:

```bash
ctxbench dataset fetch \
  --dataset-url https://github.com/ctxbench/lattes/releases/download/v0.1.0/lattes.tar.gz \
  --sha256-url https://github.com/ctxbench/lattes/releases/download/v0.1.0/lattes.tar.gz.sha256
```

Then CTXBench downloads the archive, verifies SHA-256 before extraction, safely extracts it, reads dataset identity and `datasetVersion` from `ctxbench.dataset.json`, materializes the dataset into the local cache, records a materialization manifest with identity, origin, `datasetVersion`, verified SHA-256, materialized path, and acquisition timestamp, and prints the final materialized path.

### Archive Acquisition (Inline Checksum)

Given a researcher has a direct `.tar.gz` dataset archive URL and a trusted SHA-256 hex value,  
When they run:

```bash
ctxbench dataset fetch \
  --dataset-url https://github.com/ctxbench/lattes/releases/download/v0.1.0/lattes.tar.gz \
  --sha256 <hex>
```

Then CTXBench downloads the archive, verifies SHA-256 before extraction, safely extracts it, discovers exactly one `ctxbench.dataset.json` manifest, reads identity and `datasetVersion` from the manifest, and materializes the dataset into the local cache.

### Local Archive Acquisition

Given a researcher has a locally downloaded `.tar.gz` dataset archive and a SHA-256 checksum file,  
When they run:

```bash
ctxbench dataset fetch \
  --dataset-file /path/to/lattes.tar.gz \
  --sha256-file /path/to/lattes.tar.gz.sha256
```

Then CTXBench reads the checksum file, verifies SHA-256 before extraction, safely extracts the archive, discovers exactly one `ctxbench.dataset.json` manifest, reads identity and `datasetVersion`, and materializes the dataset into the local cache.

### Local Directory Acquisition

Given a researcher has an already-unpacked dataset directory,  
When they run:

```bash
ctxbench dataset fetch --dataset-dir /path/to/lattes
```

Then CTXBench locates `ctxbench.dataset.json` in the directory, reads identity and `datasetVersion`, and materializes the dataset into the local cache. No checksum material is required, but the manifest must be valid.

### Custom Cache Root

Given a researcher wants to use a project-local cache,  
When they run:

```bash
ctxbench dataset fetch \
  --dataset-file lattes.tar.gz \
  --sha256-file lattes.tar.gz.sha256 \
  --cache-dir ./.ctxbench/datasets
```

Then CTXBench materializes the dataset under `./.ctxbench/datasets` and prints the final materialized path. Subsequent `ctxbench dataset inspect` and `ctxbench plan` commands using the same `--cache-dir` find the materialized dataset.

### Unsafe Archive Rejection

Given an archive contains path traversal, absolute paths, unsafe links, or special files,  
When the researcher runs `ctxbench dataset fetch`,  
Then CTXBench fails before materialization and does not extract unsafe entries into the cache.

### Dataset Inspection

Given a dataset has been materialized,  
When the researcher runs:

```bash
ctxbench dataset inspect ctxbench/lattes@v0.1.0
```

Then CTXBench reports metadata, mandatory capabilities, optional capabilities, strategy descriptors, and conformance status without creating benchmark artifacts or executing provider calls.

### Planning With a Cached Dataset

Given an experiment references `ctxbench/lattes@v0.1.0`,  
When the researcher runs `ctxbench plan`,  
Then CTXBench resolves the local materialization, validates the dataset package, writes dataset provenance to `manifest.json`, and produces `trials.jsonl`.

### Missing Dataset

Given an experiment references a dataset that is not materialized locally,  
When the researcher runs `ctxbench plan`,  
Then planning fails with an explicit error naming the missing dataset and suggesting a `ctxbench dataset fetch` command if origin and version are known.

### No Implicit Network

Given a dataset is missing locally,  
When the researcher runs `ctxbench plan`, `execute`, `eval`, `export`, or `status`,  
Then the command MUST NOT fetch or clone the dataset automatically.

### Single-Dataset Experiment

Given an experiment file declares multiple datasets,  
When the researcher runs `ctxbench plan`,  
Then planning fails with an explicit error stating that multi-dataset experiments are out of scope for Spec 003.

### Ambiguous Dataset

Given the local cache contains two materializations for the same dataset identity and version but different origins or revisions,  
When the researcher runs `ctxbench dataset inspect ctxbench/lattes@v0.1.0` or `ctxbench plan`,  
Then the command fails and lists the conflicting candidates.

### Lattes Conformance

Given `ctxbench/lattes` satisfies the dataset package contract,  
When the maintainer runs the provider-free workflow:

```text
ctxbench dataset fetch
ctxbench dataset inspect
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
```

Then the workflow completes without provider tokens and without generic core reaching into Lattes internals.

### Dataset Authoring

Given a future dataset author reads the documentation,  
When they follow the dataset author guide,  
Then they can create a dataset package with metadata, identity, version, instances, tasks, context artifacts, evidence artifacts, fixtures, and optional extensions without modifying `ctxbench-cli` core.

## Impact

### CLI Surface

Adds dataset-management commands:

```text
ctxbench dataset fetch
ctxbench dataset inspect
```

Does not change benchmark lifecycle phase commands:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

### Artifacts

Artifact names remain governed by Spec 002. This spec adds dataset provenance fields and capability reports to existing artifacts, primarily:

- `manifest.json`;
- `trials.jsonl`;
- `responses.jsonl`;
- `evals.jsonl`;
- `judge_votes.jsonl`;
- `results.csv` or export manifest.

### Documentation

The following documentation must be updated or created:

- `README.md`;
- `docs/architecture/README.md`;
- `docs/architecture/workflow.md`;
- `docs/architecture/cli-architecture.md`;
- `docs/architecture/container.md`;
- `docs/architecture/component.md`;
- `docs/architecture/dynamic.md`;
- `docs/architecture/vocabulary.md`;
- `docs/architecture/artifact-contracts.md`;
- `docs/datasets/using-external-datasets.md`;
- `docs/datasets/creating-a-dataset.md`;
- `specs/003-dataset-distribution/quickstart.md`;
- `specs/003-dataset-distribution/contracts/dataset-commands.md`.

### Internal Architecture

Adds or updates the following conceptual components:

- Dataset Materialization Cache;
- Dataset Resolver;
- Dataset Package boundary;
- Dataset Capability Report;
- Materialization Manifest.

## Validation

- `ctxbench-cli` builds and installs without Lattes-specific source files or payloads.
- `ctxbench dataset fetch` materializes a fixture dataset without executing remote code.
- `ctxbench dataset inspect` reports conformance and capabilities.
- `ctxbench plan` refuses missing datasets and ambiguous datasets.
- `ctxbench plan` records dataset provenance in `manifest.json`.
- `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, and `results.csv` preserve dataset identity and version.
- Provider-free workflow against fake dataset succeeds.
- Provider-free workflow against `ctxbench/lattes` succeeds once Lattes package conformance is implemented.
- Documentation includes both researcher and dataset-author guides.

## Dependencies

### Depends On

- **Spec 001 — Command Model and Phase Renaming**: lifecycle phase names and generic vocabulary.
- **Spec 002 — Artifact Contracts**: canonical artifacts and provenance taxonomy.
- **Spec 004 — Domain Architecture Boundaries**: internal core/adapter boundary contracts.

### Enables

- Lattes adapter/package conformance spec.
- Software-repository dataset spec.
- Study/suite-level orchestration for cross-dataset comparisons.
- Dataset package contract interface spec.
- Dataset provenance carrier refinements.

## Open Questions

The following remain deferred:

- Whether dataset packages may later be installable Python distributions.
- Whether multiple versions may share storage using content-addressed deduplication.
- Whether remote dataset origins beyond Git repositories are supported.
- Whether future study/suite orchestration will support multi-dataset comparison as a first-class artifact.
- Whether dataset-supplied evaluation helpers may affect aggregation semantics or only evidence construction.
