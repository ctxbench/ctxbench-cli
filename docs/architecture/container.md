# C4 — Container Diagram

## Diagram

```mermaid
flowchart TB
    User["Researcher / Analyst"]

    subgraph CTX["CTXBench Python application"]
        CLI["CLI Layer"]
        EXP["Experiment Loader"]
        DATA["Dataset Provider"]
        PLAN["Planner"]
        EXEC["Execution Engine"]
        STRAT["Strategy Layer"]
        EVAL["Evaluation Engine"]
        EXPORT["Export Engine"]
        STORE["Artifact Store Interface"]
    end

    FS["Local filesystem<br/>datasets, experiments, outputs"]
    LLM["LLM Provider APIs"]
    MCP["Remote MCP Server<br/>optional"]

    User --> CLI
    CLI --> EXP
    CLI --> PLAN
    CLI --> EXEC
    CLI --> EVAL
    CLI --> EXPORT

    EXP --> DATA
    DATA <--> FS
    PLAN --> STORE
    EXEC --> STRAT
    STRAT --> LLM
    STRAT --> MCP
    EXEC --> STORE
    EVAL --> LLM
    EVAL --> STORE
    EXPORT --> STORE
    STORE <--> FS
```

## Containers

| Container | Responsibility |
|---|---|
| CLI Layer | Parses commands and arguments. |
| Experiment Loader | Loads and validates experiment definitions. |
| Dataset Provider | Provides domain-neutral access to dataset inputs. |
| Planner | Generates `trials.jsonl` and `manifest.json`. |
| Execution Engine | Executes trials and writes responses/traces. |
| Strategy Layer | Implements context provisioning alternatives. |
| Evaluation Engine | Evaluates responses and writes eval artifacts. |
| Export Engine | Produces derived analysis artifacts. |
| Artifact Store Interface | Reads/writes local JSONL, JSON, CSV, and traces. |
