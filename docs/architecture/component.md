# C4 — Component Diagram

## Diagram

```mermaid
flowchart TB
    subgraph Planning["Planning components"]
        ExperimentLoader["Experiment Loader"]
        DatasetResolver["Dataset Resolver"]
        DatasetCache["Dataset cache"]
        DatasetPackage["DatasetPackage boundary"]
        TrialPlanner["Trial Planner"]
        ManifestWriter["Manifest Writer"]
        TrialWriter["Trial Writer"]
    end

    subgraph Execution["Execution components"]
        TrialReader["Trial Reader"]
        ExecutionEngine["Execution Engine"]
        StrategyFactory["Strategy Factory"]
        ModelAdapter["Model Adapter"]
        ToolRuntime["Function / MCP Runtime"]
        ResponseWriter["Response Writer"]
        ExecutionTraceWriter["Execution Trace Writer"]
    end

    subgraph Evaluation["Evaluation components"]
        ResponseReader["Response Reader"]
        EvalJobBuilder["Evaluation Job Builder"]
        JudgeAdapter["Judge Model Adapter"]
        VoteWriter["Judge Vote Writer"]
        EvalAggregator["Evaluation Aggregator"]
        EvalWriter["Evaluation Writer"]
        EvalTraceWriter["Evaluation Trace Writer"]
    end

    subgraph Export["Export components"]
        ArtifactReader["Artifact Reader"]
        RowBuilder["Result Row Builder"]
        CsvWriter["CSV Writer"]
    end

    ExperimentLoader --> DatasetResolver
    DatasetResolver --> DatasetCache
    DatasetResolver --> DatasetPackage
    DatasetPackage --> TrialPlanner
    TrialPlanner --> ManifestWriter
    TrialPlanner --> TrialWriter

    TrialReader --> ExecutionEngine
    DatasetPackage --> ExecutionEngine
    ExecutionEngine --> StrategyFactory
    StrategyFactory --> ModelAdapter
    StrategyFactory --> ToolRuntime
    ExecutionEngine --> ResponseWriter
    ExecutionEngine --> ExecutionTraceWriter

    ResponseReader --> EvalJobBuilder
    DatasetPackage --> EvalJobBuilder
    EvalJobBuilder --> JudgeAdapter
    JudgeAdapter --> VoteWriter
    VoteWriter --> EvalAggregator
    EvalAggregator --> EvalWriter
    JudgeAdapter --> EvalTraceWriter

    ArtifactReader --> RowBuilder
    RowBuilder --> CsvWriter
```

## Component notes

The components are implemented as Python modules. During migration, some implementation details may
still live behind compatibility adapters, but the target ownership is:

```text
ctxbench.cli
ctxbench.commands
ctxbench.benchmark
ctxbench.dataset
ctxbench.ai
```
