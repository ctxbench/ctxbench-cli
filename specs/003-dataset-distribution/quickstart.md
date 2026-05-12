# Spec 003 Quickstart

This quickstart describes the provider-free validation path used to confirm the dataset
distribution workflow without real provider calls.

## 1. Fetch the fixture dataset into a temporary cache

Fixture source:

```text
tests/fixtures/lattes_provider_free/dataset
```

Representative command:

```bash
ctxbench dataset fetch \
  --dataset-dir tests/fixtures/lattes_provider_free/dataset \
  --cache-dir ./.ctxbench/datasets
```

Expected result:

- dataset is materialized into the local cache
- dataset identity and `datasetVersion` are read from `ctxbench.dataset.json`
- a materialization manifest records local-directory provenance

## 2. Inspect the fetched dataset

```bash
ctxbench dataset inspect ctxbench/lattes@2026-04-28 --cache-dir ./.ctxbench/datasets
```

Expected result:

- printed identity `ctxbench/lattes`
- printed version `2026-04-28`
- `conformant: True`

## 3. Plan trials

Experiment fixture:

```text
tests/fixtures/lattes_provider_free/experiment.json
```

Representative command:

```bash
ctxbench plan tests/fixtures/lattes_provider_free/experiment.json \
  --output outputs/lattes_provider_free \
  --cache-dir ./.ctxbench/datasets
```

Expected result:

- `manifest.json`
- `trials.jsonl`
- manifest dataset provenance populated with `id`, `version`, and local materialization metadata

## 4. Execute with a fake responder

The provider-free conformance test monkeypatches execution with:

```text
tests/fixtures/lattes_provider_free/fake_responder.py
tests/fixtures/lattes_provider_free/conftest.py
```

Expected result:

- `responses.jsonl`
- no real provider tokens consumed
- dataset provenance preserved from planning

## 5. Evaluate with a fake judge

The provider-free conformance test monkeypatches evaluation with:

```text
tests/fixtures/lattes_provider_free/fake_judge.py
tests/fixtures/lattes_provider_free/conftest.py
```

Expected result:

- `evals.jsonl`
- `judge_votes.jsonl`
- `evals-summary.json`
- no real provider tokens consumed

## 6. Export results

```bash
ctxbench export outputs/lattes_provider_free/evals.jsonl --to csv --output outputs/lattes_provider_free/results.csv
```

Expected result:

- `results.csv`
- `dataset_id`
- `dataset_version`

## 7. Canonical provider-free validation entry point

The repository’s conformance check for this path is:

```bash
pytest tests/test_lattes_dataset_conformance.py
```

This is the recommended proof that the Spec 003 workflow is functioning provider-free.
