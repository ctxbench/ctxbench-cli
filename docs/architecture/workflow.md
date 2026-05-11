# Workflow

## Overview

The diagram below depicts the flow for executing an experiment. First you have to design your experiment describing the dataset you're going to use, the models executing the tasks and how the responses should be evaluated. The `plan` command generates `trials` to be executed posterior. This summarizes the *Planning* phase.
During *Execution*, the benchmark runs the planned `trials` and stores the `responses`. The benchmark logs the execution in `traces` that could map to `trials`. For each `trial` there is a `trace` that *tells the story* about the execution of that particular `trial`. Finally, the configured `judges` evaluate the responses of the `trials` in the *Evaluation* phase.

```mermaid
flowchart LR
    A["experiment.json"] --> B["ctxbench plan"]
    B --> C["trials.jsonl<br/>manifest.json"]
    C --> D["ctxbench execute"]
    D --> E["responses.jsonl<br/>traces/executions/"]
    E --> F["ctxbench eval"]
    F --> G["evals.jsonl<br/>judge_votes.jsonl<br/>evals-summary.json<br/>traces/evals/"]
    G --> H["ctxbench export"]
    H --> I["results.csv"]
```

## Planning

```bash
ctxbench plan experiments/lattes_baseline_001.json   --output outputs/lattes_baseline_001
```

Produces:

```text
manifest.json
trials.jsonl
```

## Execution

```bash
ctxbench execute outputs/lattes_baseline_001/trials.jsonl
```

Produces:

```text
responses.jsonl
traces/executions/<trialId>.json
```

## Evaluation

```bash
ctxbench eval outputs/lattes_baseline_001/responses.jsonl
```

Produces:

```text
evals.jsonl
judge_votes.jsonl
traces/evals/<trialId>.json
evals-summary.json
```

## Export

```bash
ctxbench export outputs/lattes_baseline_001/evals.jsonl   --to csv   --output outputs/lattes_baseline_001/results.csv
```

Produces:

```text
results.csv
```

## Status

```bash
ctxbench status outputs/lattes_baseline_001
ctxbench status outputs/lattes_baseline_001 --by judge
```

## Strategies

| Strategy | Description |
|---|---|
| `inline` | Inserts the selected context artifact directly into the model input. |
| `local_function` | Exposes local Python functions while CTXBench controls the tool loop. |
| `local_mcp` | Exposes tools through a local MCP runtime while CTXBench controls the loop. |
| `remote_mcp` | Uses a remote MCP server; provider/remote integration may control part of the loop. |

For detailed runtime flows, see `dynamic.md`.

For physical deployment/topology see `deployment.md`.
