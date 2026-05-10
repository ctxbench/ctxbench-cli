---
name: analyze-execution
description: "Analyze a ctxbench experiment run directory for quality, cost, performance, tool usage, judge agreement, failures, and reproducibility without rerunning providers."
---

# Analyze Run

## Purpose

Use this skill to analyze a completed or partially completed ctxbench run directory.

The analysis should help understand answer quality, token cost, execution time, tool behavior, judge agreement, and failures.

## Trigger examples

Use this skill when the user asks:

- "analyze this run"
- "what insights do you see?"
- "compare strategies"
- "compare models"
- "analyze cost and quality"
- "find judge disagreement"
- "what failed in this experiment?"
- "summarize baseline_001"
- "prepare analysis for my paper"

## Expected run artifacts

A run directory may contain:

```text
manifest.json
queries.jsonl
responses.jsonl
evals.jsonl
judge_votes.jsonl
results.csv
traces/
  queries/
  evals/
```

The current workflow is:

```text
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

## Required procedure

1. Start with status and file inventory.

   ```bash
   ctxbench status path/to/run
   find path/to/run -maxdepth 2 -type f | sort
   ```

2. Inspect artifact sizes before opening.

   ```bash
   ls -lh path/to/run
   wc -l path/to/run/*.jsonl
   ```

3. Prefer `results.csv` for broad analysis if it exists.

   If `results.csv` does not exist, derive summaries from:

   - `responses.jsonl`
   - `evals.jsonl`
   - `judge_votes.jsonl`

4. Separate the analysis into dimensions:

   - coverage/progress;
   - quality;
   - token cost;
   - execution time;
   - tool usage;
   - judge agreement;
   - failures/errors;
   - strategy-level insights;
   - model-level insights;
   - task-level insights.

5. Keep execution-phase and evaluation-phase costs separate.

   Query cost comes from answer generation artifacts.

   Evaluation cost comes from judge/evaluation artifacts.

6. Do not rerun provider-backed commands.

## Suggested analyses

### Coverage

- expected queries;
- completed answers;
- failed answers;
- pending answers;
- completed evaluations;
- judge-vote count.

### Quality

Group by:

- strategy;
- model;
- task;
- task tags;
- context format;
- instance.

Consider:

- majority correctness;
- unanimous correctness;
- majority completeness;
- unanimous completeness;
- partial vs misses;
- judge disagreement.

### Cost

Group execution-phase token usage by:

- strategy;
- model;
- format;
- task;
- tool-based vs inline strategy.

Track:

- input tokens;
- output tokens;
- total tokens;
- cached tokens when available;
- reasoning tokens when available.

Do not mix judge tokens into answer-generation cost.

### Performance

Analyze:

- total duration;
- model duration;
- tool duration;
- median vs mean;
- outliers;
- remote MCP overhead;
- local MCP overhead;
- local function overhead.

### Tool usage

Analyze:

- total tool calls;
- MCP tool calls;
- function calls;
- model calls;
- steps;
- tool sequence when traces are available;
- irrelevant or missing tool calls.

### Judge behavior

Analyze:

- disagreement by judge;
- disagreement by task;
- disagreement by strategy;
- judge errors;
- systematic bias.

## Useful commands

### Basic inventory

```bash
RUN_DIR="experiments/baseline_001"
ctxbench status "$RUN_DIR"
find "$RUN_DIR" -maxdepth 2 -type f | sort
wc -l "$RUN_DIR"/*.jsonl
```

### Quick JSONL schema sample

```bash
head -n 1 "$RUN_DIR/responses.jsonl" | jq 'keys'
head -n 1 "$RUN_DIR/evals.jsonl" | jq 'keys'
head -n 1 "$RUN_DIR/judge_votes.jsonl" | jq 'keys'
```

### Pandas starter

```bash
python - <<'PY'
import pandas as pd
from pathlib import Path

run = Path("experiments/baseline_001")
results = run / "results.csv"

if results.exists():
    df = pd.read_csv(results)
    print(df.shape)
    print(df.columns.tolist())
    print(df.groupby(["strategy", "model"]).size())
else:
    print("results.csv not found")
PY
```

## Constraints

- Do not run `ctxbench exec` or `ctxbench eval` unless explicitly requested.
- Do not call real providers.
- Do not read full traces unless the user asks for a specific trialId.
- Do not manually inspect hundreds of rows.
- Do not make claims without pointing to the artifact or command that supports them.

## Output format

Return:

```text
Run analyzed
- ...

Artifact coverage
- ...

Quality insights
- ...

Cost insights
- ...

Performance insights
- ...

Tool-usage insights
- ...

Judge-agreement insights
- ...

Failures and anomalies
- ...

Recommended next analyses
- ...
```

When relevant, include small tables with aggregate results.
