# Research: 002-artifact-contracts

## Artifact name state (code)

**Decision**: All target artifact names are already emitted by writers. No legacy names are written.

| Artifact | Code location | Status |
|---|---|---|
| `manifest.json` | `commands/plan.py:42–70` | ✓ target name |
| `trials.jsonl` | `benchmark/paths.py:resolve_trials_path` | ✓ default target |
| `responses.jsonl` | `benchmark/paths.py:resolve_responses_path` | ✓ default target |
| `evals.jsonl` | `benchmark/paths.py:resolve_evals_path` | ✓ default target |
| `judge_votes.jsonl` | `commands/export.py:303` | ✓ target name |
| `evals-summary.json` | `commands/eval.py:418` | ✓ target name (hardcoded; not in paths.py) |
| `results.csv` | `commands/export.py:331` | ✓ target name |
| `traces/executions/<trialId>.json` | `benchmark/results.py:write_trace_file` | ✓ target path |
| `traces/evals/<trialId>.json` | `benchmark/results.py:write_evaluation_trace_file` | ✓ target path |

## Legacy aliases in paths.py

Six legacy alias functions remain in `benchmark/paths.py`. None are called outside that file except two that are still used by `commands/experiment.py`.

| Function | Used outside paths.py? | Action |
|---|---|---|
| `resolve_queries_path` | No | Remove |
| `resolve_answers_path` | No | Remove |
| `resolve_run_jsonl_path` | No | Remove |
| `resolve_eval_jsonl_path` | No | Remove |
| `resolve_run_output_dir` | No | Remove |
| `resolve_eval_output_dir` | No | Remove |
| `resolve_expand_jsonl_path` | Yes (`experiment.py:68`) | Keep for now |
| `resolve_expand_output_dir` | Yes (`experiment.py:63`) | Keep for now |

## Legacy names in documentation

Legacy names appear in three historical-migration tables. They are correctly labeled as migration context, not as current artifact names.

| File | Context | Action |
|---|---|---|
| `docs/architecture/vocabulary.md` | "Historical migration reference" section | Add pointer to artifact-contracts.md |
| `docs/architecture/README.md` | Migration table | Same |
| `docs/architecture/cli-architecture.md` | Migration table | Same |

`docs/architecture/workflow.md` uses only target names. No action needed.

## Missing documentation

No `docs/architecture/artifact-contracts.md` exists. This is the primary deliverable.

## `evals-summary.json` path

Hardcoded in `commands/eval.py:418` as `source_root / "evals-summary.json"`. Not in `paths.py`. Produced by `ctxbench eval`, classified as a derived artifact (computable from `evals.jsonl` + `judge_votes.jsonl`).

## Constitution alignment

- Phase separation: no phases touched. Pass.
- Metric provenance: spec formalizes the taxonomy already in the constitution. Aligned.
- Artifact contracts (Constitution §V): this spec IS the artifact-contracts definition. Aligned.
- Provider-free validation: all validation is documentation inspection + pytest. Pass.
