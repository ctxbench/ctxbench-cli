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
--trial-id-file
--status
--judge
```

## Historical migration reference

The table below is a migration reference only. Public CLI commands and selectors use the target forms only and do not expose aliases.
For the authoritative artifact reference, see `docs/architecture/artifact-contracts.md`.

| Current | Target |
|---|---|
| `copa` | `ctxbench` |
| `query` | `execute` |
| `exec` | prohibited abbreviation; use `execute` |
| `queries.jsonl` | `trials.jsonl` |
| `answers.jsonl` | `responses.jsonl` |
| `--question` | `--task` |
| `--repeat` | `--repetition` |
| `--ids` | `--trial-id` |
