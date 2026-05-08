<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE] → 1.0.0
Constitution created from template for ContextBench/COPA project.

Principles added (12 total):
  I.   Cost Phase Separation
  II.  Judge Cost Isolation
  III. Vote Preservation
  IV.  Reproducible Aggregation
  V.   Schema Stability
  VI.  Strategy Comparability
  VII. Dataset Isolation
  VIII.Provider Isolation
  IX.  Artifact Safety
  X.   Confirmation Before Execution
  XI.  CLI Documentation Fidelity
  XII. Reproducibility as Research Requirement

Sections added:
  - Core Principles (12 principles)
  - Research Constraints
  - Development Constraints
  - Governance

Templates reviewed:
  - .specify/templates/plan-template.md       ✅ Constitution Check section present; gates derived from this constitution
  - .specify/templates/spec-template.md       ✅ User story structure compatible; no changes required
  - .specify/templates/tasks-template.md      ✅ Task organization compatible; no changes required

Follow-up TODOs:
  - None. All fields resolved.
-->

# ContextBench/COPA Constitution

## Core Principles

### I. Cost Phase Separation

Query-phase token costs and evaluation-phase token costs MUST be tracked, stored, and
reported separately at all times. No aggregation that merges these two phases is permitted
without explicit labeling.

When reporting cost, distinguish: input tokens, output tokens, total tokens, cached tokens
(when available), reasoning tokens (when available), and tool-call overhead (when observable).
Each figure MUST be attributed to either the query phase or the evaluation phase, never combined.

### II. Judge Cost Isolation

Judge token usage MUST NEVER be counted as answer-generation cost. Judge model calls are
evaluation infrastructure, not benchmark answers. Any token accounting that conflates judge
usage with answer-generation usage is a data integrity violation.

Evaluation traces and query traces MUST remain in separate artifact files. Mixing them
invalidates cost comparisons across strategies.

### III. Vote Preservation

Individual judge votes MUST be preserved in `judge_votes.jsonl` or equivalent per-vote
artifact. Summary outcomes (majority, unanimous) MUST be derived from, and traceable to,
the preserved votes. Votes MUST NOT be discarded or overwritten after aggregation.

### IV. Reproducible Aggregation

Aggregate evaluation outcomes (correctness, completeness, majority, unanimous) MUST be
fully reproducible from the preserved judge votes without re-running any model. If aggregate
results cannot be recomputed from stored votes, the evaluation run is considered incomplete.

### V. Schema Stability

All generated artifact schemas (`answers.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, trace
files, export files) MUST be stable across benchmark runs. Breaking schema changes MUST be
versioned explicitly (e.g., via a `schema_version` field) and documented before deployment.
Artifact consumers MUST NOT be silently broken by schema changes.

### VI. Strategy Comparability

The four context provisioning strategies — `inline`, `local_function`, `local_mcp`, and
`mcp` — MUST be implemented under a common orchestration interface so that results are
directly comparable. Strategy implementations MUST NOT differ in prompt construction,
tool availability semantics, or trace collection in ways that would confound comparisons.
Any intentional differences MUST be documented as experimental variables.

### VII. Dataset Isolation

Dataset-specific logic (e.g., Lattes-specific parsing, field extraction, question formatting)
MUST NOT leak into generic COPA benchmark components. Dataset adapters own dataset-specific
behavior. Generic components (strategy orchestrators, model adapters, evaluators) MUST NOT
contain dataset-specific conditionals or assumptions.

### VIII. Provider Isolation

Provider-specific logic MUST be isolated in provider adapters. Provider adapters MUST NOT
own benchmark strategy decisions. Strategy orchestrators MUST NOT contain provider-specific
branching. New provider support is added by implementing the adapter interface, not by
modifying strategy code.

### IX. Artifact Safety

Large benchmark artifacts (`answers.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, trace files,
large HTML or JSON dataset files) MUST be inspected through targeted queries rather than
loaded fully into model context. Acceptable inspection patterns: `head`, `jq` filters,
`rg` searches, and small aggregation scripts. Loading full artifacts into context without
an explicit user override is prohibited.

### X. Confirmation Before Execution

Provider-backed commands (`copa query`, `copa eval`) MUST NOT be executed without explicit
user confirmation. These commands consume real tokens and incur real costs. Any automated
workflow that would trigger these commands MUST pause and surface the action to the user
before proceeding.

### XI. CLI Documentation Fidelity

All documentation, reproducibility instructions, and example commands MUST use the current
CLI workflow: `copa plan`, `copa query`, `copa eval`, `copa export`, and `copa status`.
Obsolete command names MUST NOT appear in current documentation. Migration notes are the
only acceptable exception, and MUST be clearly labeled as such.

### XII. Reproducibility as Research Requirement

Reproducibility and traceability are first-class research requirements, not optional
engineering concerns. Every benchmark run MUST produce artifacts sufficient to reproduce
the aggregate results without re-running model inference. Every design decision that
reduces traceability MUST be explicitly justified and documented.

## Research Constraints

These constraints govern how benchmark results are collected, reported, and interpreted
to preserve scientific validity.

- Cost figures from different strategies MUST be computed under identical measurement
  conditions (same phase, same token accounting method) before comparison.
- Accuracy figures MUST distinguish individual judge votes, majority outcome, and unanimous
  outcome. Collapsing these without labeling is prohibited.
- Tool-call overhead MUST be attributed to the strategy that generated it, not to the
  underlying provider.
- For remote MCP strategy runs, observability limitations (e.g., provider-side-only usage
  metrics, non-separable network vs. model duration) MUST be documented alongside results.
- Benchmark results MUST NOT overstate claims. Results apply to the specific dataset,
  model versions, and strategy configurations tested.

## Development Constraints

These constraints govern how the codebase is maintained to preserve research integrity
over time.

- Use the smallest verification command that makes sense. Run targeted test scopes
  (`pytest -k cli`, `pytest -k eval`, etc.) rather than the full suite unless necessary.
- Do not call real LLM providers in tests. Use fixtures, mocks, and small local examples.
- Do not run the full benchmark pipeline unless explicitly requested.
- Do not perform opportunistic refactors. Changes MUST be scoped to the requested task.
- Do not change public artifact schemas, dataset schemas, CLI behavior, or output artifact
  names without an explicit request and a version bump per Principle V.
- Provider adapters and strategy orchestrators MUST remain independently testable.

## Governance

This constitution supersedes all other informal practices for the ContextBench/COPA project.
It is the authoritative reference for design decisions, code reviews, and documentation.

**Amendment procedure**:
1. Propose the amendment with a rationale that references the affected principle(s).
2. Assess the version bump type: MAJOR (principle removal or redefinition), MINOR (new
   principle or material expansion), PATCH (clarification, wording, non-semantic fix).
3. Update this file, increment the version, and set `Last Amended` to today's date.
4. Propagate changes to dependent templates (plan, spec, tasks) if affected.
5. Record the change in a Sync Impact Report comment at the top of this file.

**Compliance review**: All feature plans MUST include a Constitution Check section that
verifies compliance with the applicable principles before implementation begins. The check
MUST be re-verified after Phase 1 design is complete.

**Runtime guidance**: See `CLAUDE.md` for the authoritative runtime guidance file used
during development sessions.

**Version**: 1.0.0 | **Ratified**: 2026-05-08 | **Last Amended**: 2026-05-08
