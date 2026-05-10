---
name: review-changes
description: "Review code, documentation, or experiment changes in ctxbench for reproducibility, schema stability, benchmark validity, token accounting, and research risks."
---

# Review Changes

## Purpose

Use this skill when reviewing a diff, branch, pull request, or local change in the ctxbench research repository.

The review must focus on research correctness, reproducibility, benchmark validity, and cost/observability risks.

## Trigger examples

Use this skill when the user asks:

- "review this change"
- "check this diff"
- "is this safe to merge?"
- "does this affect reproducibility?"
- "review the implementation"
- "check whether this breaks the benchmark"
- "evaluate this PR"

## Required procedure

1. Inspect the current change with the smallest useful command first.

   Recommended commands:

   ```bash
   git status --short
   git diff --stat
   git diff --name-only
   ```

2. Classify the changed areas:

   - CLI
   - planning
   - trial execution
   - strategy orchestration
   - local function tools
   - local MCP
   - remote MCP
   - model provider adapter
   - evaluation
   - judge votes
   - export
   - dataset
   - documentation
   - tests
   - packaging or dependency management

3. Check whether the change affects any research-critical contract:

   - experiment reproducibility
   - generated artifact names
   - generated artifact schemas
   - trial/evaluation separation
   - token accounting
   - timing metrics
   - tool-call traces
   - MCP observability
   - judge-vote aggregation
   - majority/unanimous outcomes
   - CLI compatibility
   - dataset integrity

4. Inspect only relevant file ranges.

   Avoid loading large artifacts into context. Do not open complete JSONL files, traces, curriculum HTML files, or parsed dataset files.

5. Identify the smallest relevant test set.

   Suggested searches:

   ```bash
   rg "def test_" tests
   rg "plan|exec|eval|export|status" tests
   ```

6. If safe and appropriate, run focused tests only.

   Examples:

   ```bash
   pytest -k cli
   pytest -k plan
   pytest -k exec
   pytest -k eval
   pytest -k export
   ```

## Constraints

- Do not run real provider-backed commands unless explicitly requested.
- Do not run full benchmark experiments unless explicitly requested.
- Do not change files during review unless the user explicitly asks for fixes.
- Do not propose broad refactoring unless necessary for correctness.
- Do not treat documentation-only changes as harmless; check whether commands and artifact names match the current implementation.

## Review checklist

Check:

- Does the change preserve the distinction between query-phase model usage and evaluation-phase judge usage?
- Does it keep answer-generation cost separate from judge/evaluation cost?
- Does it preserve individual judge votes?
- Does it preserve aggregate evaluation outputs?
- Does it change how `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, or `results.csv` are produced?
- Does it alter `trialId`, `taskId`, `instanceId`, `model`, `provider`, `strategy`, or `format` semantics?
- Does it affect inline, local function, local MCP, and remote MCP strategies consistently?
- Does it introduce hidden assumptions about the Lattes dataset?
- Does it create non-determinism that harms reproducibility?
- Does it increase token consumption or provider calls unnecessarily?

## Output format

Return:

```text
Summary
- ...

Changed areas
- ...

Research risks
- ...

Schema/artifact risks
- ...

Token/cost risks
- ...

Recommended tests
- ...

Documentation updates needed
- ...

Verdict
- Safe to merge / Needs changes / Needs clarification
```

If no tests were run, say so explicitly and explain why.
