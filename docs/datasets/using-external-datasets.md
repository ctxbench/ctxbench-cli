# Using External Datasets

## Purpose

This guide documents the supported workflow for working with datasets that live outside the
`ctxbench-cli` repository.

Two command families matter:

- dataset-management commands: `ctxbench dataset fetch`, `ctxbench dataset inspect`
- lifecycle commands: `ctxbench plan`, `ctxbench execute`, `ctxbench eval`, `ctxbench export`, `ctxbench status`

Lifecycle commands are local-only. They do not fetch, clone, or download datasets.

## Remote dataset workflow

Use this path when the experiment references a dataset by `id` and `version`.

```bash
ctxbench dataset fetch ctxbench/lattes \
  --origin https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.tar.gz \
  --version 2026-04-28 \
  --sha256 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

ctxbench dataset inspect ctxbench/lattes@2026-04-28

ctxbench plan tests/fixtures/lattes_provider_free/experiment.json --output outputs/lattes_example
ctxbench execute outputs/lattes_example/trials.jsonl
ctxbench eval outputs/lattes_example/responses.jsonl
ctxbench export outputs/lattes_example/evals.jsonl --format csv --output outputs/lattes_example/results.csv
ctxbench status outputs/lattes_example
```

Expected artifact progression:

- `ctxbench dataset fetch`: materializes the dataset into the local cache
- `ctxbench dataset inspect`: reports capability and provenance metadata
- `ctxbench plan`: writes `manifest.json` and `trials.jsonl`
- `ctxbench execute`: writes `responses.jsonl` and execution traces
- `ctxbench eval`: writes `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, and eval traces
- `ctxbench export`: writes `results.csv`

## Local-path shortcut

Use this path when the experiment points directly to a dataset root.

```json
{
  "dataset": {
    "root": "datasets/local-dataset"
  }
}
```

For local paths, skip `ctxbench dataset fetch` and go straight to inspection or planning:

```bash
ctxbench dataset inspect datasets/local-dataset
ctxbench plan experiment.json --output outputs/local_example
```

## Verified archive acquisition

### Direct archive URL with `--sha256`

```bash
ctxbench dataset fetch ctxbench/lattes \
  --origin https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.tar.gz \
  --version 2026-04-28 \
  --sha256 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

### Release tag URL with `--asset-name` and `--sha256-url`

```bash
ctxbench dataset fetch ctxbench/lattes \
  --origin https://github.com/ctxbench/lattes/releases/tag/v0.1.0-dataset \
  --version 2026-04-28 \
  --asset-name ctxbench-lattes-v0.1.0.tar.gz \
  --sha256-url https://github.com/ctxbench/lattes/releases/download/v0.1.0-dataset/ctxbench-lattes-v0.1.0.sha256
```

Rules:

- archive and release acquisition require either `--sha256` or `--sha256-url`
- checksum verification happens before extraction
- missing checksum input fails fast
- invalid checksum fails before extraction or materialization

Archive extraction is safety-checked. The fetch command rejects:

- path traversal entries
- absolute paths
- unsafe symlinks
- unsafe hardlinks
- device nodes
- FIFOs
- other special files

After extraction, CTXBench requires exactly one dataset manifest. It accepts either:

- a single top-level directory containing the dataset package
- files directly at the archive root

It fails if there is no manifest, or more than one manifest.

## Conflict and ambiguity handling

### Missing dataset

If `ctxbench plan` cannot resolve `dataset.id@version` locally, it fails and tells you to run:

```bash
ctxbench dataset fetch <dataset-id> --origin ... --version ...
```

### Ambiguous dataset

If the local cache contains multiple materializations for the same `datasetId` and requested
version but with conflicting provenance, planning and inspection fail with an ambiguity error.

Resolution options:

1. Remove the conflicting cache entry outside the benchmark workflow.
2. Re-fetch the intended dataset from the authoritative origin.
3. Switch the experiment to a local `root` reference if you are intentionally using a one-off local copy.

### Identity/version mismatch

If the fetched or unpacked dataset manifest does not match the requested identity/version, the
fetch operation fails and nothing is materialized into the cache.

## No implicit network rule

The lifecycle commands below do not acquire datasets:

- `ctxbench plan`
- `ctxbench execute`
- `ctxbench eval`
- `ctxbench export`
- `ctxbench status`

Consequences:

- `plan` fails if a referenced `dataset.id@version` is not already materialized locally
- `execute` and `eval` fail if required local dataset artifacts are missing
- `export` and `status` work from existing artifacts and preserved provenance only

## Provenance in artifacts

Dataset provenance is preserved across canonical artifacts as a nested `dataset` object with:

- `id`
- `version`
- `origin`
- `resolvedRevision`
- `contentHash`
- `materializedPath`

Flat export adds:

- `dataset_id`
- `dataset_version`
