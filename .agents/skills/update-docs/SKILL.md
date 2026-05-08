---
name: update-docs
description: "Update README, reproducibility notes, experiment documentation, or paper-supporting documentation so it matches the actual ContextBench/COPA implementation and CLI."
---

# Update Docs

## Purpose

Use this skill when updating documentation for ContextBench/COPA, especially README files, reproducibility instructions, experiment descriptions, artifact descriptions, or paper-supporting docs.

The goal is to keep documentation aligned with the actual implementation and avoid obsolete commands or misleading claims.

## Trigger examples

Use this skill when the user asks:

- "update the README"
- "make this reproducible"
- "document the experiment"
- "write usage instructions"
- "prepare docs after submission"
- "explain how to reproduce"
- "update docs from the current CLI"
- "fix documentation drift"

## Required procedure

1. Inspect the relevant implementation before editing docs.

   Use targeted searches:

   ```bash
   rg "subparsers|add_parser|def .*plan|def .*query|def .*eval|def .*export|def .*status" src tests
   rg "answers.jsonl|evals.jsonl|judge_votes.jsonl|queries.jsonl|manifest.json|results.csv" src tests docs README.md
   ```

2. Confirm current CLI commands.

   Current expected workflow:

   ```text
   copa plan
   copa query
   copa eval
   copa export
   copa status
   ```

3. Confirm generated artifacts before documenting them.

   Typical workflow:

   ```text
   experiment JSON
     -> copa plan
     -> queries.jsonl + manifest.json
     -> copa query
     -> answers.jsonl + query traces
     -> copa eval
     -> evals.jsonl + judge_votes.jsonl + eval traces
     -> copa export
     -> results.csv
   ```

4. Avoid documenting obsolete command names.

   Do not use old names such as:

   - `copa experiment expand`
   - `copa run`

   unless explicitly writing migration notes.

5. Keep reproducibility instructions concrete.

   Include:

   - prerequisites;
   - environment variables;
   - dataset location;
   - experiment file;
   - commands;
   - expected outputs;
   - analysis entry point;
   - known limitations.

6. Keep research claims conservative.

   Distinguish:

   - what the benchmark measures;
   - what a particular experiment observed;
   - what cannot be generalized from one run.

## Documentation checklist

Check whether docs explain:

- repository purpose;
- benchmark workflow;
- dataset organization;
- experiment configuration;
- strategies;
- formats;
- answer models;
- judge models;
- output artifacts;
- cost metrics;
- performance metrics;
- quality metrics;
- judge agreement;
- trace files;
- how to resume/check status;
- how to export analysis-ready results;
- how to avoid expensive provider calls accidentally.

## Reproducibility checklist

A reproducible doc section should include:

- exact command sequence;
- input files;
- output files;
- environment variables;
- expected artifact counts when known;
- how to verify completion;
- how to inspect failures;
- how to regenerate exports without rerunning providers;
- how to run tests or smoke checks.

## Constraints

- Do not overstate benchmark conclusions.
- Do not imply that remote MCP is always better or worse.
- Do not mix query-phase and evaluation-phase cost explanations.
- Do not claim a run is complete unless artifacts support it.
- Do not document generated files that the current implementation does not create.
- Do not include secrets or provider keys.

## Suggested structure for README

```text
# Project name

## Purpose

## Repository contents

## Benchmark workflow

## Dataset organization

## Experiment configuration

## Running the benchmark

### Plan

### Query

### Evaluate

### Export

### Status

## Output artifacts

## Analysis

## Reproducibility notes

## Limitations
```

## Output format

When editing docs, return:

```text
Documentation updated
- ...

Implementation facts checked
- ...

Files changed
- ...

Commands referenced
- ...

Possible follow-up docs
- ...
```

If documentation cannot be safely updated because implementation is unclear, inspect the relevant source files first and report the uncertainty.
