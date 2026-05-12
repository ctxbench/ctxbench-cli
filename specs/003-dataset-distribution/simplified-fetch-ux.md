# Amendment A1 — Simplified Dataset Fetch UX

**Spec**: `specs/003-dataset-distribution/spec.md`  
**Branch**: `feat/dataset-distribution`  
**Status**: Proposed  
**Purpose**: Record the intended change to dataset acquisition UX before regenerating plan and tasks.

## Context

The current dataset distribution design makes `ctxbench dataset fetch` too verbose for the common case.

The existing command shape requires the user to provide dataset identity, origin, and version explicitly:

```bash
ctxbench dataset fetch <dataset-id> \
  --origin <origin> \
  --version <version>
```

Additional archive/release options make the common `.tar.gz` workflow even harder to use.

This creates three problems:

1. The user has to provide information that should already exist inside the dataset package manifest.
2. The meaning of `version` is ambiguous.
3. A user who has either a remote `.tar.gz`, a local `.tar.gz`, or an already unpacked dataset directory does not have a simple, direct command.

## Intent

Keep `ctxbench dataset fetch` as the single explicit command for dataset acquisition and materialization.

Do **not** introduce a separate `ctxbench dataset install` command.

The command should be simple for the three common cases:

### Remote dataset archive

```bash
ctxbench dataset fetch \
  --dataset-url <dataset.tar.gz-url> \
  --sha256-url <dataset.sha256-url>
```

or:

```bash
ctxbench dataset fetch \
  --dataset-url <dataset.tar.gz-url> \
  --sha256 <sha256>
```

### Local dataset archive

```bash
ctxbench dataset fetch \
  --dataset-file <dataset.tar.gz> \
  --sha256-file <dataset.sha256>
```

or:

```bash
ctxbench dataset fetch \
  --dataset-file <dataset.tar.gz> \
  --sha256 <sha256>
```

### Local unpacked dataset directory

```bash
ctxbench dataset fetch \
  --dataset-dir <dataset-root>
```

## Decisions

### D1 — Dataset identity comes from the manifest

Dataset identity MUST be read from the dataset package manifest.

It should not be required as a positional argument in the common `fetch` workflow.

Optional user-provided identity may be supported only as a validation override, not as the source of truth.

### D2 — Dataset version comes from the manifest

Dataset version MUST be read from the dataset package manifest.

It should not be required as a command-line argument in the common `fetch` workflow.

Optional user-provided version may be supported only as a validation override, not as the source of truth.

### D3 — Version terminology must be explicit

The spec must distinguish at least:

- `datasetVersion`: version of the dataset package contents;
- `manifestSchemaVersion`: version of the dataset manifest schema;
- `ctxbenchVersion`: version of the CTXBench CLI/framework;
- `artifactSchemaVersion`: version of produced benchmark artifact schemas, if applicable;
- `releaseTag`: distribution tag, not authoritative dataset version;
- `contentHash` or `verifiedSha256`: exact content/integrity identity, not semantic version.

The ambiguous field name `version` may remain in experiment references for compatibility, but documentation must state that it means dataset version.

### D4 — Dataset manifest should have a distinct name

The canonical dataset package manifest SHOULD be named:

```text
ctxbench.dataset.json
```

This avoids confusion with benchmark lifecycle `manifest.json`.

### D5 — Archive integrity remains mandatory

Archive acquisition MUST verify SHA-256 before extraction and before cache materialization.

For `--dataset-url`, the user MUST provide either:

```text
--sha256
```

or:

```text
--sha256-url
```

For `--dataset-file`, the user MUST provide either:

```text
--sha256
```

or:

```text
--sha256-file
```

For `--dataset-dir`, checksum material is not required, but the directory MUST contain a valid dataset manifest.

### D6 — Source selection must be explicit

Exactly one dataset source must be provided:

```text
--dataset-url
--dataset-file
--dataset-dir
```

Providing none or more than one is an error.

### D7 — User chooses the cache root, not the final internal path

Dataset materialization happens inside a dataset cache.

The user may choose the cache root using:

```text
--cache-dir <path>
```

or the environment variable:

```text
CTXBENCH_DATASET_CACHE
```

If neither is provided, CTXBench uses its default dataset cache location.

The final materialized path is computed by CTXBench from dataset identity, dataset version, and immutable content identity.

The user should not normally provide the exact final materialized directory.

### D8 — Cache root selection must be reusable

The same cache root selection mechanism must be available to commands that need to resolve cached datasets.

At minimum:

```text
ctxbench dataset fetch
ctxbench dataset inspect
ctxbench plan
```

must support cache root selection consistently.

Commands that only read completed benchmark artifacts, such as `export` and `status`, should remain artifact-only and should not require dataset cache access when sufficient provenance is already present.

### D9 — Fetch must report where the dataset was materialized

After successful materialization, `ctxbench dataset fetch` MUST print:

- dataset identity;
- dataset version;
- verified checksum or content hash when available;
- final materialized path.

### D10 — Lifecycle commands still must not fetch

This amendment does not change the no-implicit-network rule.

The following commands MUST NOT acquire datasets implicitly:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

If a lifecycle command needs a materialized dataset and cannot find it, it must fail with a clear remediation message.

## Out of scope

This amendment does not introduce:

- a dataset registry;
- `ctxbench dataset install`;
- dynamic plugin loading;
- remote code execution from datasets;
- provider-backed validation;
- multi-dataset experiments;
- a package marketplace;
- implicit network access during lifecycle phases.

## Expected spec effect

Spec 003 should be updated so the canonical acquisition model is based on:

```text
--dataset-url
--dataset-file
--dataset-dir
--sha256
--sha256-url
--sha256-file
--cache-dir
CTXBENCH_DATASET_CACHE
```

The old form:

```bash
ctxbench dataset fetch <dataset-id> --origin <origin> --version <version>
```

should no longer be the canonical workflow.

If kept temporarily, it should be documented as compatibility or advanced behavior only.

## Acceptance criteria

After applying this amendment:

1. A researcher can materialize a remote dataset archive using only dataset URL and checksum URL.
2. A researcher can materialize a local dataset archive using archive path and checksum path/value.
3. A researcher can materialize an already unpacked local dataset directory.
4. Dataset identity and dataset version are read from the dataset manifest.
5. The meaning of dataset version is not confused with manifest schema version, CTXBench version, release tag, or content hash.
6. The user can choose the dataset cache root.
7. Fetch reports the final materialized path.
8. Planning can resolve datasets from a custom cache root.
9. Lifecycle commands still do not fetch datasets implicitly.
10. The documentation presents the simplified `fetch` UX as the canonical path.
