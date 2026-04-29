# COPA Benchmark

COPA is a benchmark runner for comparing how LLMs answer dataset-backed questions under different execution strategies.

The current codebase is centered on a simple idea:

- keep the question set fixed
- vary how the model accesses the source information
- evaluate the answer qualitatively with either deterministic heuristics or a judge model

The repository currently ships a Lattes-based dataset and resource-oriented tool layer.

## What Changed

This version no longer uses the legacy evaluation model based on `exact`, `analytical`, `unanswerable`, numeric scores, or rubric dimensions.

The benchmark now uses:

- dataset instances organized by folder
- question-level `validation.type`
- instance-level `acceptedAnswers`, `contextRefs`, and `themes`
- qualitative evaluation only
- Lattes tools named as `get_<resource>`

## Core Concepts

### Dataset

A dataset is composed of:

- `questions.json`
- `questions.instance.json`
- `context/<instanceId>/...`

`questions.json` defines the stable question catalog.

```json
{
  "datasetId": "example-lattes-v2",
  "questions": [
    {
      "id": "q_phd_year",
      "question": "In which year did the researcher obtain their PhD?",
      "tags": ["objective", "factual", "simple"],
      "validation": {
        "type": "heuristic",
        "schema": { "type": "number" }
      }
    },
    {
      "id": "q_research_summary",
      "question": "Summarize the researcher's main research areas based only on the available context.",
      "tags": ["subjective", "factual", "simple"],
      "validation": {
        "type": "judge"
      }
    }
  ]
}
```

`questions.instance.json` binds each question to one instance.

```json
{
  "datasetId": "example-lattes-v2",
  "instances": [
    {
      "instanceId": "5660469902738038",
      "contextBlocks": "context/5660469902738038/blocks.json",
      "questions": [
        {
          "id": "q_phd_year",
          "acceptedAnswers": [1999]
        },
        {
          "id": "q_research_summary",
          "contextRefs": ["summary", "research"],
          "themes": ["software engineering", "distributed systems"]
        }
      ]
    }
  ]
}
```

Each instance lives in its own directory:

```text
dataset-root/
  questions.json
  questions.instance.json
  context/
    5660469902738038/
      raw.html
      cleaned.html
      parsed.json
      blocks.json
```

### Validation Modes

Only two validation modes exist:

- `heuristic`
  Used when the answer can be checked deterministically against `acceptedAnswers`.
- `judge`
  Used when the answer must be evaluated qualitatively against `contextRefs` and `themes`.

Judge outputs are qualitative. They include one rating and one justification for each criterion:

- `groundedness`
- `correctness`
- `completeness`

There is no `score` and no `meanScore`.

### Experiment

An experiment selects:

- which dataset to use
- which instances and questions to include via `scope`
- which provider/model pairs to run
- which strategies and formats to test
- whether evaluation is enabled

Example:

```json
{
  "id": "lattes_full_001",
  "output": "/abs/path/to/outputs",
  "dataset": "lattes/",
  "scope": {
    "instances": [],
    "questions": []
  },
  "factors": {
    "model": [
      { "provider": "openai", "name": "gpt-5.4-nano" }
    ],
    "strategy": ["inline", "local_function", "local_mcp", "mcp"],
    "format": ["json", "html"]
  },
  "evaluation": {
    "enabled": true,
    "judge": {
      "provider": "openai",
      "model": "gpt-5.4-mini",
      "temperature": 0
    }
  },
  "execution": {
    "repeats": 1
  }
}
```

`scope.instances` and `scope.questions` act as filters. Empty lists mean "all available".

## Strategies

COPA currently supports four execution strategies.

### `inline`

The model receives the context artifact directly in the prompt.

Typical formats:

- `json` -> `parsed.json`
- `html` -> `raw.html`
- `cleaned_html` -> `cleaned.html`

### `local_function`

The benchmark controls the tool loop and exposes local Python tools directly.

For Lattes, the model interacts with:

- `get_profile`
- `get_expertise`
- `get_education`
- `get_projects`
- `get_supervisions`
- `get_experience`
- `get_academic_activities`
- `get_publications`
- `get_technical_output`
- `get_artistic_output`

### `local_mcp`

The benchmark still controls the loop, but the tools are accessed through a local MCP runtime.

### `mcp`

The model provider controls the remote MCP interaction.

This path is less observable by design. Some metrics may be `null` because the benchmark cannot reliably observe provider-side tool execution.

## Lattes Tool Layer

The Lattes integration is resource-oriented.

The parsed curriculum in `parsed.json` is treated as the source of truth for tool-based execution. The tool surface is fixed and shared across `local_function`, `local_mcp`, and `mcp`:

- `get_profile`
- `get_expertise`
- `get_education`
- `get_projects`
- `get_supervisions`
- `get_experience`
- `get_academic_activities`
- `get_publications`
- `get_technical_output`
- `get_artistic_output`

All tools are read-only. Temporal filters are exposed only where they make sense through `start_year` and `end_year`.

`get_supervisions` returns a grouped structure by supervision level:

- `masters`
- `doctoral`
- `undergraduate`
- `specialization`
- `others`

Each level contains:

- `completed`
- `ongoing`

This keeps the benchmark simpler and makes tool usage easier to compare across strategies.

## CLI

The CLI entrypoint is `copa`.

### Validate an Experiment

```bash
copa experiment validate datasets/lattes/experiment.json
```

### Expand an Experiment into RunSpecs

```bash
copa experiment expand datasets/lattes/experiment.json --out runspecs --jsonl runs.jsonl
```

### Execute Runs

```bash
copa run runspecs --out results --jsonl results.jsonl
```

To force re-execution even when artifacts already exist:

```bash
copa run runspecs --out results --jsonl results.jsonl --force
```

`Ctrl-C` stops after the current item and leaves a checkpoint behind. Rerunning the same command resumes from the last completed `runId`.

### Evaluate Run Results

From a directory:

```bash
copa eval \
  --run-results-dir results \
  --experiment datasets/lattes/experiment.json \
  --output-dir eval \
  --output-jsonl evaluation.jsonl \
  --output-csv evaluation.csv
```

From one JSON or JSONL input:

```bash
copa eval \
  --run-results-json results.jsonl \
  --experiment datasets/lattes/experiment.json \
  --output-dir eval
```

Optional filters:

- `--only <questionId>`
- `--mode heuristic`
- `--mode judge`

## Output Artifacts

The benchmark persists:

- runspec JSON files
- run result JSON files
- evaluation result JSON files
- optional JSONL aggregations
- optional CSV export for evaluation rows
- trace artifacts
- checkpoint files for interrupted batches (`runs.checkpoint.json`, `evaluation.checkpoint.json`)

JSONL artifacts are the default canonical source for analysis:

- `runs.jsonl`
- `results.jsonl`
- `evaluation.jsonl`

Per-item JSON files (`runs/rs_*.json`, `results/rr_*.json`, `evaluation/re_*.json`) are optional debug artifacts. Enable them explicitly:

```json
{
  "artifacts": {
    "writeJsonl": true,
    "writeIndividualJson": true
  },
  "trace": {
    "enabled": true,
    "writeFiles": true
  }
}
```

Run results include a compact `metricsSummary` separate from the raw trace. When a strategy does not expose a metric reliably, the field is stored as `null`.

Evaluation rows persist qualitative details and expose common fields directly (`outcome`, `correctness`, `completeness`, judge metadata and evaluation token/duration fields) for easier CSV export.

Model factors can include a short `id` for filtering and reporting:

```json
{
  "provider": "openai",
  "id": "gpt-mini",
  "name": "gpt-5.4-mini-2026-03-17"
}
```

Run and evaluation commands accept selectors:

```bash
copa run runs.jsonl --model gpt-mini --question q_sup
copa eval --run-jsonl results.jsonl --model gpt-mini --instance 5521922960404236
```

`--model` matches either the short `modelId` or the full model name. Selectors are available for provider, model, instance, question, strategy, format, and repeat; evaluation also supports status. Each of those fields also has an `--exclude-*` variant.

## Repository Layout

- `src/copa/cli.py`
  CLI entrypoint
- `src/copa/commands/`
  `experiment`, `run`, and `eval` commands
- `src/copa/benchmark/`
  experiment schema, runspec generation, execution, evaluation, persistence
- `src/copa/ai/`
  model adapters, strategies, trace collection, runtimes
- `src/copa/dataset/`
  generic dataset loading and validation
- `src/copa/datasets/lattes/`
  section-based Lattes provider, tools, and MCP server
- `examples/datasets/`
  example dataset and experiment fixtures
- `datasets/lattes/`
  main Lattes dataset

## Development

Install the project in editable mode:

```bash
pip install -e .[dev]
```

Run the test suite:

```bash
pytest -q
```

## Current Status

The refactor is aligned around simplicity:

- no compatibility with the legacy dataset/evaluation contract
- no score aggregation
- no rubric dimensions
- no broad domain-specific tool surface
- section-first retrieval for Lattes

If you are extending the benchmark, prefer preserving these constraints instead of reintroducing legacy abstractions.
