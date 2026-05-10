# CLAUDE.md

## Project context

This repository supports my PhD research on context provisioning strategies for LLM-based systems.

The main goal is to evaluate how different context provisioning strategies affect answer quality, token cost, execution time, tool usage, observability, and reproducibility.

Core strategies:

- `inline`: context is inserted directly into the prompt.
- `local_function`: local tool/function calling controlled by the benchmark.
- `local_mcp`: local MCP runtime controlled by the benchmark.
- `mcp`: remote MCP server used as a context provider.

Core benchmark workflow:

- `ctxbench plan`
- `ctxbench exec`
- `ctxbench eval`
- `ctxbench export`
- `ctxbench status`

The benchmark artifacts can be large. Be careful with token usage and context size.

## Working style

Use an economical context strategy.

Before editing code:

1. Identify the smallest relevant file set.
2. Use `rg`, `find`, `git diff`, `jq`, or small scripts before opening large files.
3. Read only the necessary functions, classes, or file ranges.
4. Propose a short plan.
5. Wait for confirmation unless the user explicitly asked for direct implementation.

Do not explore the whole repository unless explicitly asked.

Prefer focused changes over broad refactoring.

Do not perform opportunistic refactors.

Do not change public file formats, experiment schemas, dataset schemas, CLI behavior, or output artifact names unless explicitly requested.

## Large files and benchmark artifacts

Never read full large artifacts into context unless explicitly requested.

Avoid opening entire files such as:

- `responses.jsonl`
- `evals.jsonl`
- `judge_votes.jsonl`
- large trace files under `traces/`
- large HTML curriculum files
- full parsed JSON dataset files

Instead, inspect samples with commands like:

```bash
head -n 3 responses.jsonl
jq -c 'select(.trialId == "TRIAL_ID")' responses.jsonl
rg '"taskId":"q_sup"' responses.jsonl
python scripts/inspect_run.py --run-id TRIAL_ID
```

When analyzing benchmark outputs, prefer small scripts that aggregate data outside the conversation.

## Development rules

Use the smallest verification command that makes sense.

For CLI changes:

```bash
pytest -k cli
```

For planning changes:

```bash
pytest -k plan
```

For trial execution changes:

```bash
pytest -k trial
```

For evaluation changes:

```bash
pytest -k eval
```

For export changes:

```bash
pytest -k export
```

If the exact test target is unknown, locate tests first:

```bash
rg "def test_.*export|def test_.*eval|def test_.*query" tests
```

Do not run the full benchmark unless explicitly requested.

Do not call real LLM providers unless explicitly requested.

Prefer fixtures, mocks, and small local examples.

## Research constraints

Preserve separation between:

- answer-generation model usage;
- judge model usage;
- trial traces;
- evaluation traces;
- aggregate exported results.

Do not mix execution-phase token usage with evaluation-phase token usage.

When discussing cost, distinguish:

- input tokens;
- output tokens;
- total tokens;
- cached tokens when available;
- reasoning tokens when available;
- tool-call overhead when observable.

When discussing accuracy, distinguish:

- individual judge votes;
- majority outcome;
- unanimous outcome;
- correctness;
- completeness.

## Architecture constraints

Keep strategy logic separate from model-provider adapters.

Provider adapters should not own benchmark strategy decisions.

Strategies should orchestrate:

- prompt construction;
- tool availability;
- tool-call loop;
- MCP/local-function execution;
- trace collection.

Dataset-specific logic should remain isolated from generic benchmark execution logic.

Avoid hardcoding Lattes-specific behavior in generic ctxbench components.

## MCP rules

Use MCP only when the task is explicitly about MCP behavior, MCP integration, or MCP strategy execution.

Do not enable or inspect unrelated MCP servers.

For remote MCP analysis, pay attention to observability limits:

- which tools were called;
- whether tool calls are visible locally;
- whether usage metrics are provider-side only;
- whether network duration and model duration can be separated.

## Documentation rules

When updating documentation:

- keep it aligned with the actual CLI;
- prefer concise reproducibility instructions;
- include exact commands;
- avoid historical implementation details unless needed;
- avoid overstating what the benchmark proves.

Use the current command names:

- `ctxbench plan`
- `ctxbench exec`
- `ctxbench eval`
- `ctxbench export`
- `ctxbench status`

Do not document obsolete commands unless explicitly writing migration notes.

## Done criteria

A task is done only when:

- the requested behavior is implemented or the analysis is complete;
- the relevant minimal tests or checks were run, when possible;
- the final response lists files changed;
- the final response lists commands run and their result;
- limitations or unverified assumptions are stated clearly.

## Compacting instructions

When context grows, compact aggressively.

Preserve:

- current task goal;
- accepted plan;
- files read;
- files changed;
- important design decisions;
- commands run;
- test results;
- remaining problems.

Drop:

- long logs;
- repeated discussion;
- obsolete alternatives;
- full JSONL snippets;
- full traces;
- full dataset content.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
