# Amendment A1-R1 — Descriptor-Based Fetch and Cache Reuse

**Spec**: `specs/003-dataset-distribution/spec.md`  
**Branch**: `feat/dataset-distribution`  
**Status**: Proposed  
**Purpose**: Refine Amendment A1 by adding a lightweight dataset distribution descriptor and clarifying cache reuse behavior.

## Context

Amendment A1 simplified dataset acquisition by replacing the previous:

```bash
ctxbench dataset fetch <dataset-id> --origin <origin> --version <version>
```

with explicit source flags such as:

```bash
ctxbench dataset fetch --dataset-url <dataset.tar.gz-url> --sha256-url <dataset.sha256-url>
ctxbench dataset fetch --dataset-file <dataset.tar.gz> --sha256-file <dataset.sha256>
ctxbench dataset fetch --dataset-dir <dataset-root>
```

However, direct archive sources are opaque before download or extraction. CTXBench cannot know the dataset identity and dataset version from a `.tar.gz` archive without acquiring and inspecting it.

This can cause unnecessary download or extraction work when the dataset is already materialized locally.

## Intent

Keep dataset acquisition explicit, reproducible, and user-friendly while avoiding unnecessary archive acquisition work.

The canonical remote workflow should use a small distribution descriptor:

```bash
ctxbench dataset fetch --descriptor-url <dataset-descriptor.json-url>
```

The descriptor provides enough metadata for CTXBench to check the local cache before downloading the dataset archive.

## Decisions

### D1 — Descriptor is the canonical remote acquisition source

The preferred remote acquisition workflow is:

```bash
ctxbench dataset fetch \
  --descriptor-url <dataset-descriptor.json-url>
```

An offline equivalent is also supported:

```bash
ctxbench dataset fetch \
  --descriptor-file <dataset-descriptor.json>
```

### D2 — Descriptor is external to the dataset package

The descriptor is a distribution artifact published alongside the dataset archive.

It does not replace the dataset package manifest.

The dataset archive still contains:

```text
ctxbench.dataset.json
```

CTXBench must validate that the descriptor and the internal package manifest agree on dataset identity and dataset version.

### D3 — Descriptor contains acquisition metadata

A descriptor must provide at least:

```json
{
  "id": "ctxbench/lattes",
  "datasetVersion": "0.2.0",
  "descriptorSchemaVersion": 1,
  "archive": {
    "type": "tar.gz",
    "url": "https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.tar.gz",
    "sha256": "..."
  }
}
```

Additional metadata may be included, such as name, description, release tag, size, license, or citation pointers.

### D4 — Descriptor enables cache pre-check

When using `--descriptor-url` or `--descriptor-file`, CTXBench must:

1. load the descriptor;
2. read dataset identity, dataset version, archive URL, and archive SHA-256;
3. check the selected dataset cache;
4. avoid downloading the archive when a matching materialization already exists;
5. download and materialize only when needed.

### D5 — Direct archive sources are opaque

The following sources are opaque before acquisition:

```text
--dataset-url
--dataset-file
```

Therefore, they require explicit cache pre-check metadata:

```text
--id <dataset-id>
--version <dataset-version>
```

These values are not the authoritative dataset manifest. They are used to:

1. check the local cache before acquisition;
2. validate the internal `ctxbench.dataset.json` after extraction.

### D6 — Local directories are self-describing

`--dataset-dir` does not require `--id` or `--version`, because CTXBench can read:

```text
<dataset-root>/ctxbench.dataset.json
```

`--id` and `--version` may still be accepted as optional validation overrides.

### D7 — Source selection is exclusive

Exactly one source must be provided:

```text
--descriptor-url
--descriptor-file
--dataset-url
--dataset-file
--dataset-dir
```

Providing none or more than one is an error.

### D8 — Cache reuse is the default

If the requested dataset identity and dataset version are already materialized and match the expected content identity, `fetch` must not download, extract, copy, or overwrite.

It must report that the dataset already exists and print the current materialized path.

### D9 — Conflicting content fails by default

If a dataset with the same identity and dataset version already exists but has conflicting content identity, `fetch` must fail by default.

### D10 — `--force` replaces after validation

`--force` allows replacing an existing materialization for the same dataset identity and dataset version.

`--force` must not bypass:

- descriptor validation;
- checksum verification;
- safe archive extraction;
- internal manifest discovery;
- internal manifest validation.

### D11 — Cache paths are semantic

The user-facing materialized path should be based on dataset identity and dataset version:

```text
<cache-dir>/<dataset-id>/<datasetVersion>/
```

Example:

```text
.ctxbench/datasets/ctxbench/lattes/0.2.0/
```

Content hashes and verified SHA-256 values must be recorded in provenance. They do not need to appear in the normal materialization path.

### D12 — Experiments remain semantic

Experiments must continue to reference datasets by identity and dataset version:

```json
{
  "dataset": {
    "id": "ctxbench/lattes",
    "version": "0.2.0"
  }
}
```

Experiments should not reference descriptor URLs, archive URLs, checksum files, or downloaded archives.

### D13 — Lifecycle commands still do not acquire datasets

This amendment does not change the no-implicit-network rule.

The following commands must not fetch, download, copy, replace, or materialize datasets implicitly:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

## Revised fetch UX

### Canonical remote workflow

```bash
ctxbench dataset fetch \
  --descriptor-url https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.dataset.json \
  --cache-dir ./.ctxbench/datasets
```

### Offline descriptor workflow

```bash
ctxbench dataset fetch \
  --descriptor-file ./ctxbench-lattes-v0.2.0.dataset.json \
  --cache-dir ./.ctxbench/datasets
```

### Direct remote archive workflow

```bash
ctxbench dataset fetch \
  --dataset-url https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.tar.gz \
  --id ctxbench/lattes \
  --version 0.2.0 \
  --sha256-url https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.sha256 \
  --cache-dir ./.ctxbench/datasets
```

### Direct local archive workflow

```bash
ctxbench dataset fetch \
  --dataset-file ./ctxbench-lattes-v0.2.0.tar.gz \
  --id ctxbench/lattes \
  --version 0.2.0 \
  --sha256-file ./ctxbench-lattes-v0.2.0.sha256 \
  --cache-dir ./.ctxbench/datasets
```

### Local directory workflow

```bash
ctxbench dataset fetch \
  --dataset-dir ./datasets/lattes \
  --cache-dir ./.ctxbench/datasets
```

### Replacement workflow

```bash
ctxbench dataset fetch \
  --descriptor-url https://github.com/ctxbench/lattes/releases/download/v0.2.0-dataset/ctxbench-lattes-v0.2.0.dataset.json \
  --cache-dir ./.ctxbench/datasets \
  --force
```

## Expected spec effect

Update Spec 003 so that:

- descriptor-based acquisition is the canonical remote workflow;
- `--dataset-url` and `--dataset-file` are treated as opaque archive sources;
- opaque archive sources require `--id`, `--version`, and checksum material;
- `--dataset-dir` remains self-describing;
- cache reuse is the default;
- conflicting materializations fail unless `--force` is used;
- semantic materialization paths are preferred;
- experiment references remain unchanged.

## Acceptance criteria

After applying this amendment:

1. A researcher can fetch a remote dataset using only `--descriptor-url`.
2. A researcher can fetch from a local descriptor using `--descriptor-file`.
3. `--dataset-url` requires `--id`, `--version`, and checksum material.
4. `--dataset-file` requires `--id`, `--version`, and checksum material.
5. `--dataset-dir` does not require `--id`, `--version`, or checksum material.
6. CTXBench does not download an archive when the descriptor identifies an already materialized matching dataset.
7. CTXBench does not extract/copy a local archive when the explicit id/version/checksum identify an already materialized matching dataset.
8. CTXBench validates descriptor identity/version against the internal `ctxbench.dataset.json`.
9. CTXBench materializes datasets to semantic paths such as `.ctxbench/datasets/ctxbench/lattes/0.2.0`.
10. Content identity is recorded in provenance.
11. Conflicting content for the same identity/version fails by default.
12. `--force` replaces only after all validation succeeds.
13. Experiments continue to reference datasets using `{ "id": "...", "version": "..." }`.
14. Lifecycle commands still do not acquire datasets implicitly.
