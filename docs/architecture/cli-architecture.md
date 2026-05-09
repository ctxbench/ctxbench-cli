# CLI Architecture

## Purpose

The CLI exposes the benchmark workflow.

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

The CLI is implemented in Python and should remain thin: parse arguments, resolve selectors, and delegate to command handlers.

## CLI component structure

```mermaid
flowchart TB
    CLI["ctxbench CLI<br/>argument parsing"]
    Selectors["Selector parser"]
    Plan["plan command"]
    Execute["execute command"]
    Eval["eval command"]
    Export["export command"]
    Status["status command"]
    Core["Benchmark core"]
    Store["Artifact store"]

    CLI --> Selectors
    CLI --> Plan
    CLI --> Execute
    CLI --> Eval
    CLI --> Export
    CLI --> Status

    Plan --> Core
    Execute --> Core
    Eval --> Core
    Export --> Core
    Status --> Store
    Core --> Store
```

## Commands

| Command | Responsibility |
|---|---|
| `ctxbench plan` | Expand experiment into trials. |
| `ctxbench execute` | Execute trials and collect responses. |
| `ctxbench eval` | Evaluate responses. |
| `ctxbench export` | Build analysis-ready files. |
| `ctxbench status` | Report progress. |

## Common selectors

Recommended selectors:

```text
--model
--provider
--instance
--task
--strategy
--format
--repetition
--trial-id
--ids-file
--status
--judge
```

Compatibility aliases:

```text
--question -> --task
--repeat -> --repetition
--ids -> --trial-id / ids list
```

## Migration notes

| Current | Target |
|---|---|
| `copa` | `ctxbench` |
| `copa query` | `ctxbench execute` |
| `queries.jsonl` | `trials.jsonl` |
| `answers.jsonl` | `responses.jsonl` |
