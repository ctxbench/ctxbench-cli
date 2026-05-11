---
name: design-change
description: "Design a safe implementation plan for changes to ctxbench architecture, evaluation, strategy behavior, MCP integration, metrics, schemas, or experiment workflow."
---

# Design Change

## Purpose

Use this skill before implementing a non-trivial change in ctxbench.

The goal is to produce a safe, minimal, research-aware design that protects reproducibility, output schemas, token accounting, and strategy comparability.

## Trigger examples

Use this skill when the user asks:

- "how should I implement this?"
- "design this change"
- "refactor this part"
- "change the evaluation"
- "add a strategy"
- "add a metric"
- "change token accounting"
- "support a new model/provider"
- "support a new dataset"
- "change MCP behavior"
- "specify this for implementation"

## Required procedure

1. Restate the requested change in one paragraph.

2. Classify the change:

   - CLI;
   - experiment schema;
   - planning;
   - trial execution;
   - strategy orchestration;
   - model provider adapter;
   - local function tool layer;
   - local MCP runtime;
   - remote MCP integration;
   - tracing;
   - metrics;
   - evaluation;
   - export;
   - dataset provider;
   - documentation.

3. Identify invariants that must be preserved.

   Common invariants:

   - execution-phase costs remain separate from evaluation-phase costs;
   - individual judge votes remain available;
   - aggregate evaluation remains reproducible from judge votes;
   - strategies remain comparable;
   - format handling remains explicit;
   - dataset-specific logic does not leak into generic benchmark logic;
   - provider-specific logic stays inside provider adapters;
   - generated artifact schemas are stable or versioned;
   - old experiments remain interpretable;
   - refactors preserve research semantics and artifact interpretation;
   - simplification opportunities are considered before adding abstractions;
   - obsolete compatibility paths are removed only when migration rules allow it.

4. Propose the smallest design.

Before proposing new abstractions, check whether the change can be implemented by simplifying
or reusing the existing design.

Prefer to:
- remove obsolete compatibility paths when migration rules allow it;
- collapse unnecessary layers;
- avoid new registries, factories, plugins, or metadata fields unless justified by the spec;
- keep domain abstractions minimal until at least two real domains require the variation;
- preserve research contracts over architectural elegance.

Refactoring should reduce accidental complexity while preserving research semantics,
artifact contracts, metric interpretation, reproducibility, and migration expectations.
Do not refactor opportunistically outside the active specification.

5. Identify files likely to change.

6. Define tests.

7. Define migration or compatibility implications.

8. Only after the design is accepted should implementation begin.

## Design checklist

### For refactoring changes

Check:

- What complexity is being removed?
- Which concepts, names, layers, or compatibility paths become simpler?
- Which research semantics must remain unchanged?
- Are artifact contracts preserved or explicitly migrated?
- Are metric meanings and provenance preserved?
- Are lifecycle phases still explicit and separated?
- Are domain/provider/strategy boundaries clearer after the change?
- Is the refactor covered by focused tests?

### For evaluation changes

Check:

- correctness vs completeness;
- majority vs unanimous;
- judge-level rows;
- aggregate rows;
- judge errors;
- evaluation traces;
- context blocks used by judges;
- judge token usage;
- separation from answer-generation usage.

### For strategy changes

Check:

- inline behavior;
- local function behavior;
- local MCP behavior;
- remote MCP behavior;
- format normalization;
- tool-call loop;
- step limits;
- error handling;
- trace collection;
- model/provider capabilities.

### For metrics changes

Check:

- input tokens;
- output tokens;
- total tokens;
- cached input tokens;
- cache read tokens;
- cache creation tokens;
- reasoning tokens;
- tool schema overhead;
- tool result tokens;
- duration of trials and tasks;
- tool calls;
- retries anda failures;
- provider-specific accounting differences.

### For export changes

Check:

- flat CSV compatibility;
- preserving raw JSONL artifacts;
- one row per run vs one row per judge vote;
- column naming stability;
- missing values;
- backward compatibility with notebooks.

### For dataset changes

Check:

- instance IDs;
- task IDs;
- context blocks;
- ground truth;
- raw vs cleaned vs parsed artifacts;
- whether evaluations must be regenerated.

## Constraints

- Do not implement during the design step unless the user explicitly asks for implementation.
- Do not propose broad rewrites when a narrow change is enough.
- Do not hide breaking changes.
- Do not change public schemas without naming the migration strategy.
- Do not assume provider behavior is identical across OpenAI, Anthropic, and Google.

### Simplicity check

Check:

- Can this change be implemented by simplifying the current design?
- Is any new abstraction required by a current spec or real domain variation?
- Can an existing layer, field, schema, or compatibility path be removed?
- Does the simpler design still preserve reproducibility, traceability, artifact contracts,
  metric provenance, and migration expectations?

### Simplicity check

Check:

- Can this change be implemented by simplifying the current design?
- Is any new abstraction required by a current spec or real domain variation?
- Can an existing layer, field, schema, or compatibility path be removed?
- Does the simpler design still preserve reproducibility, traceability, artifact contracts,
  metric provenance, and migration expectations?
## Output format

Return:

```text
Requested change
- ...

Change category
- ...

Invariants to preserve
- ...

Proposed design
- ...

Files likely to change
- ...

Schema/artifact impact
- ...

Testing plan
- ...

Migration/documentation impact
- ...

Risks
- ...

Open questions
- ...
```

If implementation is requested immediately, implement only after this design is summarized.
