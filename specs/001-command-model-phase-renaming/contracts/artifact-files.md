# Contract: Public Artifact File Names

## Target file names in the experiment output directory

`outputs/<experimentId>/` MUST contain only artifacts named below.

| File | Producer phase | Class | Notes |
|------|----------------|-------|-------|
| `manifest.json` | plan | canonical | Records inputs for reproducibility. |
| `trials.jsonl` | plan | canonical | One record per planned trial. |
| `responses.jsonl` | execute | canonical | One record per executed trial. |
| `evals.jsonl` | eval | canonical | One record per evaluated response. |
| `judge_votes.jsonl` | eval | canonical | Per-judge votes. |
| `evals-summary.json` | eval | derived | Aggregate evaluation outcomes. |
| `results.csv` | export | derived | Analysis-ready export. |

Trace files (`traces/executions/<trialId>.json`,
`traces/evals/<trialId>.json`) are **governed by spec 002** and are not
part of this contract.

## Writer obligations

- `ctxbench plan` writes `trials.jsonl` (NOT `queries.jsonl`).
- `ctxbench execute` writes `responses.jsonl` (NOT `answers.jsonl`).
- No phase emits `queries.jsonl` or `answers.jsonl` under any flag,
  environment variable, or configuration.

## Reader obligations

- All phases consume only target file names.
- Pre-existing files named `queries.jsonl` or `answers.jsonl` in the
  output directory are neither read nor overwritten; they are silently
  ignored (FR-008).
- A `ctxbench execute` invoked in a directory that already contains a
  legacy `answers.jsonl` produces its own `responses.jsonl` alongside;
  the researcher is responsible for archiving the legacy file.

## Verification

```
ctxbench plan ./experiment.json --output ./outputs/demo
ls outputs/demo/                                # 'trials.jsonl' present; 'queries.jsonl' absent
ctxbench execute
ls outputs/demo/                                # 'responses.jsonl' present; 'answers.jsonl' absent
```
