# Artifact Contracts

This document is the authoritative reference for the CTXBench artifact set, artifact classification, legacy no-alias policy, and metric provenance taxonomy.

## Artifact lifecycle

| Artifact | Producing phase | Class | Role |
|---|---|---|---|
| `manifest.json` | `plan` | `canonical` | Execution artifacts |
| `trials.jsonl` | `plan` | `canonical` | Execution artifacts |
| `responses.jsonl` | `execute` | `canonical` | Execution artifacts |
| `evals.jsonl` | `eval` | `canonical` | Evaluation artifacts |
| `judge_votes.jsonl` | `eval` | `canonical` | Evaluation artifacts |
| `evals-summary.json` | `eval` | `derived` | Analysis-ready exports |
| `results.csv` | `export` | `derived` | Analysis-ready exports |
| `traces/executions/<trialId>.json` | `execute` | `canonical` | Traces |
| `traces/evals/<trialId>.json` | `eval` | `canonical` | Traces |

## Classification rules

Canonical artifacts are the authoritative record of a benchmark phase.

Derived artifacts are reproducible from canonical artifacts without re-invoking providers. Regenerating `evals-summary.json` or `results.csv` must not require re-running `ctxbench execute` or `ctxbench eval`.

## Execution Artifacts

Execution artifacts are the records needed to define and carry out planned benchmark trials.

- `manifest.json` is the plan-phase canonical artifact that records the inputs needed to reproduce subsequent phases.
- `trials.jsonl` is the plan-phase canonical artifact that enumerates the benchmark trials scheduled for execution.
- `responses.jsonl` is the execute-phase canonical artifact that records benchmark responses for completed trials.

## Evaluation Artifacts

Evaluation artifacts are the canonical records produced by the evaluation phase.

- `evals.jsonl` is the eval-phase canonical artifact containing trial-level evaluation records.
- `judge_votes.jsonl` is the eval-phase canonical artifact containing judge-level voting records used to support evaluation outcomes and agreement analysis.

## Analysis-Ready Exports

Analysis-ready exports are reproducible summaries or tabular outputs intended for downstream analysis.

- `evals-summary.json` is an eval-phase derived artifact reproducible from evaluation-phase canonical artifacts without provider re-runs.
- `results.csv` is an export-phase derived artifact reproducible from canonical artifacts without provider re-runs.

## Traces

Trace artifacts preserve per-trial execution and evaluation observability.

- `traces/executions/<trialId>.json` is the execute-phase canonical trace for one `trialId`.
- `traces/evals/<trialId>.json` is the eval-phase canonical trace for one `trialId`.

## Metric provenance taxonomy

Every metric in a canonical or derived artifact must be representable under exactly one provenance class per record.

| Class | Definition |
|---|---|
| `reported` | Returned by a provider API, SDK, or another authoritative runtime. |
| `measured` | Measured directly by benchmark-controlled instrumentation. |
| `derived` | Computed deterministically from reported or measured values. |
| `estimated` | Approximated from heuristics, tokenizers, assumptions, or incomplete information. |
| `unavailable` | Not available and not responsibly estimated for that record. |

Rules:

- `estimated` must not be presented as `reported` or `measured`.
- `unavailable` must not be recorded as zero unless zero is the observed value.
- This taxonomy is closed in this specification. It defines exactly five classes and does not permit sub-classes, confidence scores, or other extensions.

## Legacy migration

The following mappings are migration guidance only. Each legacy name has no alias, and migration is the researcher's responsibility.

| Legacy name | Target name | Policy |
|---|---|---|
| `queries.jsonl` | `trials.jsonl` | No alias. Writers and readers use the target name only. |
| `answers.jsonl` | `responses.jsonl` | No alias. Writers and readers use the target name only. |
| `traces/queries/<runId>.json` | `traces/executions/<trialId>.json` | No alias. Writers and readers use the target name only. |

No automated migration tooling is committed to by this specification.

## Reader and writer policy

- Writers must produce only target artifact names. No phase writes legacy names.
- Readers do not consume legacy artifact names. If legacy files are present in an input directory, they are silently ignored rather than treated as an error.
