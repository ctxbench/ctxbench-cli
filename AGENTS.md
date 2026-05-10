# AGENTS.md

## Repository purpose

This repository is part of a PhD research project on context provisioning for LLM-based systems.

The benchmark compares different ways of giving context to LLMs, including inline context, local function calling, local MCP, and remote MCP.

Primary evaluation dimensions:

- answer quality;
- token cost;
- execution time;
- tool usage;
- traceability;
- judge agreement;
- reproducibility.

## Expected agent behavior

Work like a careful research software engineer.

Default behavior:

- stay scoped;
- minimize context usage;
- inspect before editing;
- prefer small patches;
- verify with targeted tests;
- preserve reproducibility.

Do not make broad architectural changes unless explicitly requested.

Do not silently change experiment semantics.

Do not silently change generated artifact formats.

Do not run expensive experiments unless explicitly requested.

## Prompt interpretation

For every task, infer and preserve:

- Goal: what behavior or artifact should change.
- Context: which files, commands, examples, or errors are relevant.
- Constraints: what must not change.
- Done when: what verification proves the task is complete.

If the request is ambiguous and implementation could affect experiment validity, ask before editing.

For simple mechanical changes, proceed with the smallest safe change.

## Project workflow

The benchmark workflow is:

```text
experiment config
  -> cxbench plan
  -> trials.jsonl + manifest.json
  -> ctxbench execute
  -> responses.jsonl + trials traces
  -> ctxbench eval
  -> evals.jsonl + judge_votes.jsonl + eval traces
  -> ctxbench export
  -> results.csv
```

Use current CLI commands:

```bash
ctxbench plan
ctxbench execute
ctxbench eval
ctxbench export
ctxbench status
```

Do not introduce documentation or scripts using obsolete command names.

## Current and target naming

The current implementation may still contain legacy names such as `copa`, `query`,
`queries.jsonl`, `responses.jsonl`, `trialId`, `questionId`, and `answer`.

The target architecture uses `ctxbench`, `execute`, `trials.jsonl`, `responses.jsonl`,
`trialId`, `taskId`, and `response`.

Treat them implementation contracts. If artifact names or formats change, the
specification must define canonical vs. derived artifacts, migration impact, and schema
compatibility.

Treat legacy names as migration details, not permanent concepts. New specs, docs, examples,
and code should prefer target terminology unless explicitly working on compatibility.

## File and artifact discipline

Large benchmark artifacts must not be loaded entirely into the conversation.

Avoid reading complete files such as:

- `responses.jsonl`
- `evals.jsonl`
- `judge_votes.jsonl`
- `results.csv` when large
- `traces/**/*.json`
- `raw.html`
- `clean.html`
- large `parsed.json`
- large `blocks.json`

Use targeted inspection:

```bash
head -n 5 responses.jsonl
jq -c 'select(.trialId == "TRIAL_ID")' responses.jsonl
rg '"taskId":"q_sup"' responses.jsonl
rg '"strategy":"inline"' responses.jsonl
```

For repeated analysis, create or use small scripts instead of pasting data into the conversation.

## Coding conventions

Prefer explicit, readable code over clever abstractions.

Keep benchmark concerns separated:

- CLI parsing;
- experiment planning;
- trials execution;
- strategy orchestration;
- model provider adapters;
- MCP runtime;
- evaluation;
- export;
- analysis utilities.

Avoid coupling generic benchmark code to the domain-specific dataset.

Avoid coupling provider-specific behavior to strategy-independent logic.

Use typed data structures where the project already uses them.

Preserve existing naming conventions.

## Strategy rules

The strategy layer owns context-provisioning behavior.

Provider adapters should expose model capabilities but should not decide benchmark strategy.

Inline strategies may serialize context into prompts.

Tool-based strategies should expose tools and run the tool loop according to the benchmark design.

MCP strategies should preserve the distinction between:

- local MCP;
- remote MCP;
- function calling;
- provider-native tool use.

## Evaluation rules

Keep trial execution and evaluation separate.

Do not include judge token usage in answer-generation cost.

Do not overwrite answer traces with evaluation traces.

Preserve individual judge votes.

Preserve aggregate evaluation outputs.

When changing evaluation logic, consider:

- correctness;
- completeness;
- majority outcome;
- unanimous outcome;
- judge disagreement;
- judge errors.

## Reproducibility rules

All experiment-affecting changes should be reproducible.

Prefer deterministic tests.

Avoid hidden environment assumptions.

If an environment variable is required, document it.

Do not commit secrets, API keys, provider tokens, or private credentials.

Do not add generated large artifacts unless explicitly requested.

## Commands

Use targeted commands first.

Discover tests:

```bash
rg "def test_" tests
```

Run focused tests:

```bash
pytest -k plan
pytest -k exec
pytest -k eval
pytest -k export
pytest -k cli
```

Run formatting or linting only if configured in the repository.

Do not install new dependencies without asking.

Do not change lockfiles unless dependency changes are explicitly requested.

## Documentation rules

Documentation must match the current implementation.

When updating README or experiment documentation:

- include exact commands;
- identify required input files;
- identify generated output files;
- explain how to reproduce results;
- explain how to inspect status;
- avoid vague claims about accuracy or superiority;
- distinguish benchmark results from general conclusions.

## Analysis rules

For benchmark analysis, prefer notebooks, pandas, DuckDB, or small scripts.

Do not ask the model to manually inspect many rows.

Prefer aggregations such as:

- accuracy by strategy;
- accuracy by model;
- token cost by strategy;
- duration by strategy;
- tool calls by task;
- judge disagreement by task;
- failures by provider;
- cache effects by model.

## Safety and cost controls

Never run these commands against real providers unless explicitly requested:

```bash
ctxbench execute
ctxbench eval
```

Before running provider-backed commands, state the likely cost or risk.

Prefer dry runs, planning, status checks, fixture-based tests, or mocked providers.

## Pull request / final response expectations

When finished, report:

- summary of what changed;
- files changed;
- commands run;
- test results;
- assumptions;
- remaining risks.

If no tests were run, say so clearly and explain why.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
