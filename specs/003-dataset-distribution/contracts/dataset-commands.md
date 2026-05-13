# Dataset Command Contract

## Scope

This document defines the public contract for the dataset-management CLI surface introduced by
Spec 003.

Dataset-management commands are separate from lifecycle commands:

- dataset-management: `ctxbench dataset fetch`, `ctxbench dataset inspect`
- lifecycle: `ctxbench plan`, `ctxbench execute`, `ctxbench eval`, `ctxbench export`, `ctxbench status`

## Parser structure

The CLI uses a nested subparser registration pattern:

```text
ctxbench
  dataset
    fetch
    inspect
  plan
  execute
  eval
  export
  status
```

`ctxbench dataset` is not a valid terminal command by itself. A dataset subcommand is required.

## `ctxbench dataset fetch`

### Purpose

Materialize a dataset into the local cache from an explicit source selector.

### Arguments

Required:

- exactly one of `--descriptor-url`, `--descriptor-file`, `--dataset-url`, `--dataset-file`, or `--dataset-dir`

Optional:

- `--id`
- `--version`
- `--sha256`
- `--sha256-url`
- `--sha256-file`
- `--force`
- `--cache-dir`

### Accepted source forms

1. distribution descriptor URL via `--descriptor-url`
2. local distribution descriptor path via `--descriptor-file`
3. direct `.tar.gz` archive URL via `--dataset-url`
4. local `.tar.gz` archive path via `--dataset-file`
5. local unpacked dataset directory via `--dataset-dir`

### Descriptor-first acquisition examples

Canonical remote workflow:

```bash
ctxbench dataset fetch \
  --descriptor-url https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.dataset.json
```

Offline descriptor workflow:

```bash
ctxbench dataset fetch \
  --descriptor-file ./downloads/ctxbench-lattes-v0.1.0.dataset.json
```

### Opaque archive acquisition examples

Direct archive URL plus `--sha256`:

```bash
ctxbench dataset fetch \
  --dataset-url https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.tar.gz \
  --id ctxbench/lattes \
  --version 0.1.0 \
  --sha256 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Direct archive URL plus `--sha256-url`:

```bash
ctxbench dataset fetch \
  --dataset-url https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.tar.gz \
  --id ctxbench/lattes \
  --version 0.1.0 \
  --sha256-url https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.sha256
```

Local archive plus `--sha256-file`:

```bash
ctxbench dataset fetch \
  --dataset-file ./downloads/ctxbench-lattes-v0.1.0.tar.gz \
  --id ctxbench/lattes \
  --version 0.1.0 \
  --sha256-file ./downloads/ctxbench-lattes-v0.1.0.sha256
```

Local unpacked directory:

```bash
ctxbench dataset fetch --dataset-dir ./datasets/lattes
```

### Failure rules

- missing or multiple source-selector flags fail in argparse before command execution
- `--descriptor-url` and `--descriptor-file` are self-describing sources
- `--dataset-url` without `--sha256` or `--sha256-url` fails
- `--dataset-file` without `--sha256` or `--sha256-file` fails
- `--dataset-url` and `--dataset-file` without `--id` or `--version` fail before download or extraction
- checksum mismatch fails before extraction
- no manifest or multiple manifests after extraction fails
- descriptor-vs-manifest identity/version mismatch fails before materialization
- unsafe tar entries fail

### Cache reuse and replacement

- when cached content identity matches, fetch prints the existing materialized path and exits without acquiring
- when the same `datasetId@version` exists with conflicting content, fetch fails by default
- `--force` allows replacement only after all validation steps succeed
- the user-facing materialized path is `<cache-dir>/<dataset-id>/<datasetVersion>/`

### Safe extraction guarantees

Extraction rejects:

- path traversal
- absolute paths
- unsafe symlinks
- unsafe hardlinks
- device nodes
- FIFOs
- other special files

### Exit behavior

- returns success on successful local materialization
- raises an error on invalid source, invalid checksum, invalid archive, or conflicting manifest/provenance

## `ctxbench dataset inspect`

### Purpose

Resolve a local or cached dataset reference and report capability/provenance metadata without
modifying benchmark artifacts.

### Arguments

Required:

- positional `dataset_ref`

Optional:

- `--json`
- `--cache-dir`

### Accepted reference forms

1. local dataset root path
2. `dataset-id@version`

### Output forms

Human-readable output includes:

- `identity`
- `version`
- `conformant`
- `origin`
- `missing_mandatory`

JSON output is intended for conformant reports whose payload is JSON-serializable.

### Exit behavior

- succeeds for a resolvable local or cached dataset reference
- fails for missing datasets, ambiguous cached references, or invalid package layout

## Shared cache-root selection

`ctxbench dataset fetch`, `ctxbench dataset inspect`, and `ctxbench plan` share the same cache-root
selection rules:

1. `--cache-dir` takes highest precedence
2. `CTXBENCH_DATASET_CACHE` is used when `--cache-dir` is omitted
3. otherwise CTXBench uses the default dataset cache location

## Error message expectations

The command layer uses explicit remediation-oriented messages where possible:

- missing cached dataset during planning suggests `ctxbench dataset fetch`
- ambiguous cached dataset reports ambiguity rather than choosing one silently
- lifecycle commands fail locally rather than performing implicit acquisition

The exact Python exception type is not part of the public CLI contract. The behavioral contract is:

- no silent acquisition in lifecycle commands
- no silent conflict resolution
- fail before extraction on checksum problems

## No-network boundary

`ctxbench dataset fetch` is the explicit acquisition boundary.

The following commands must not fetch or resolve remote datasets implicitly:

- `ctxbench plan`
- `ctxbench execute`
- `ctxbench eval`
- `ctxbench export`
- `ctxbench status`
