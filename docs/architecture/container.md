# C4 — Container Diagram

## Diagram

```mermaid
flowchart TB
    User["Researcher / Analyst"]
    Repo["Remote dataset repository"]
    Cache["Local dataset cache"]
    DatasetRoot["Local dataset root"]

    subgraph CTX["CTXBench Python application"]
        CLI["CLI Layer"]
        EXP["Experiment Loader"]
        RES["Dataset Resolver"]
        PKG["DatasetPackage boundary"]
        PLAN["Planner"]
        EXEC["Execution Engine"]
        STRAT["Strategy Layer"]
        EVAL["Evaluation Engine"]
        EXPORT["Export Engine"]
        STATUS["Status Reader"]
        STORE["Artifact Store Interface"]
    end

    FS["Local filesystem<br/>experiments, outputs, traces"]
    LLM["LLM Provider APIs"]
    MCP["Remote MCP Server<br/>optional"]

    User --> CLI
    CLI --> RES
    CLI --> EXP
    CLI --> PLAN
    CLI --> EXEC
    CLI --> EVAL
    CLI --> EXPORT
    CLI --> STATUS

    Repo --> RES
    Cache <--> RES
    DatasetRoot --> RES
    EXP --> RES
    RES --> PKG
    PKG --> PLAN
    PKG --> EXEC
    PKG --> EVAL
    PLAN --> STORE
    EXEC --> STRAT
    STRAT --> LLM
    STRAT --> MCP
    EXEC --> STORE
    EVAL --> LLM
    EVAL --> STORE
    EXPORT --> STORE
    STATUS --> STORE
    STORE <--> FS
```

## Containers

| Container | Responsibility |
|---|---|
| CLI Layer | Parses commands and arguments. |
| Experiment Loader | Loads and validates experiment definitions. |
| Dataset Resolver | Resolves local dataset roots and cached `dataset.id@version` references without implicit network access. |
| DatasetPackage boundary | Domain-neutral package surface used by planning, execution, and evaluation. |
| Planner | Generates `trials.jsonl` and `manifest.json`. |
| Execution Engine | Executes trials and writes responses/traces. |
| Strategy Layer | Implements context provisioning alternatives. |
| Evaluation Engine | Evaluates responses and writes eval artifacts. |
| Export Engine | Produces derived analysis artifacts. |
| Status Reader | Reads artifacts and reports lifecycle progress without dataset resolution. |
| Artifact Store Interface | Reads/writes local JSONL, JSON, CSV, and traces. |
