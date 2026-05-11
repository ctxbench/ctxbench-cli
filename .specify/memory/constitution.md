# ContextBench Constitution

## Core Principles

### I. Phase Separation

Benchmark lifecycle phases MUST remain conceptually distinct.

At minimum, the benchmark MUST distinguish:

- experiment planning;
- answer generation;
- answer evaluation;
- result export;
- progress/status inspection.

Command names, artifact names, and implementation details may evolve, but phase
responsibilities MUST remain explicit, documented, and migration-safe.

Answer-generation costs and evaluation costs MUST be tracked, stored, and reported
separately. No analysis may merge these costs without explicit labeling.

### II. Evaluation Cost Isolation

Judge model usage is evaluation infrastructure, not answer-generation behavior.

Token usage, latency, traces, failures, and metadata produced by evaluation or judge models
MUST NOT be counted as answer-generation cost. Any accounting that conflates answer
generation and evaluation is a data-integrity violation.

When reporting cost or performance, distinguish the lifecycle phase that produced the
measurement and the component responsible for it.

### III. Metric Provenance and Interpretation

All benchmark metrics MUST preserve enough provenance information to support correct
interpretation.

A metric directly reported by an external provider, SDK, API, or controlled runtime MUST be
marked as reported. A metric directly measured by benchmark-controlled instrumentation MUST
be marked as measured. A metric computed deterministically from reported or measured values
MUST be marked as derived. A metric approximated through heuristics, tokenizers, assumptions,
or incomplete information MUST be marked as estimated. A metric that cannot be obtained or
responsibly estimated MUST be marked as unavailable.

Estimated metrics MUST NOT be presented as reported or measured values. Unavailable metrics
MUST NOT be represented as zero unless zero is a valid observed value.

Metric records, exports, and analyses SHOULD preserve, when relevant:

- value;
- unit;
- lifecycle phase;
- provenance;
- source or method.

Additional confidence fields, scoring systems, or detailed metadata SHOULD NOT be introduced
unless required by an accepted specification.

### IV. Vote Preservation and Recomputable Aggregation

Individual judge votes are primary evaluation evidence and MUST be preserved.

Aggregate outcomes, including majority and unanimous outcomes, MUST be reproducible from
the preserved individual votes without re-running any model. If an aggregate result cannot
be recomputed from stored evidence, the evaluation is incomplete.

Evaluation artifacts MUST preserve enough information to reconstruct:

- the evaluated answer;
- the question;
- the relevant context or context references used by judges;
- the judge identity/configuration;
- individual criterion ratings;
- aggregate outcomes;
- judge errors or missing votes.

### V. Artifact Contracts

Benchmark artifacts are research contracts.

The benchmark MUST clearly distinguish canonical artifacts from derived artifacts. Canonical
artifacts are the source of truth for reproducing a run, evaluation, or analysis. Derived
artifacts exist for convenience and MUST be reproducible from canonical artifacts.

Artifact names and formats may evolve, but their responsibilities, schemas, and migration
implications MUST be documented. Breaking changes MUST be explicit, versioned, and covered
by a migration note or compatibility decision.

No public artifact schema, dataset schema, CLI behavior, or output contract may change
silently.

### VI. Strategy Comparability

Context-provisioning strategies MUST remain comparable under a shared experimental model.

Strategies may differ in how context is exposed to the model, but differences that can
affect interpretation MUST be treated as experimental variables and documented.

At minimum, strategy documentation and traces SHOULD make clear:

- who controls the model/tool loop;
- whether context is provided inline or through operations/tools;
- whether tool execution is local or remote;
- which context representation is used;
- which metrics are directly observable;
- which metrics are unavailable, estimated, derived, or provider-side only.

Intentional asymmetries between strategies MUST be documented before results are compared.

### VII. Boundary Isolation and Dependency Direction

The benchmark MUST preserve clear architectural boundaries.

Generic benchmark components MUST NOT contain dataset-specific assumptions. Dataset-specific
behavior belongs in dataset adapters, readers, tools, fixtures, or dataset-specific packages.

Provider-specific behavior MUST remain isolated in provider adapters. Provider adapters may
expose model capabilities, but they MUST NOT own benchmark strategy decisions.

Strategy orchestration MUST remain separate from provider adaptation and dataset-specific
logic. Strategy code owns context-provisioning behavior, model/tool loop orchestration, trace
collection, and strategy-level metrics.

Dependencies between major architectural components MUST follow an explicit direction.
Circular dependencies between major components are prohibited unless documented as temporary
migration exceptions with rationale, scope, and removal plan.

New cross-boundary dependencies MUST be introduced through stable interfaces, contracts, or
adapters rather than direct coupling to implementation details.

### VIII. Reproducibility and Traceability

Reproducibility and traceability are first-class research requirements.

Every benchmark run SHOULD produce artifacts sufficient to reproduce aggregate results
without re-running model inference. When this is not possible, the limitation MUST be
explicitly documented.

Every design decision that reduces traceability, observability, metric provenance, or
recomputability MUST be justified. The benchmark MUST prefer transparent, inspectable, and
reproducible workflows over opaque convenience.

The benchmark ecosystem MAY span multiple repositories, packages, datasets, services,
experiment configurations, and analysis environments. Cross-repository dependencies that
affect reproducibility, artifact contracts, dataset semantics, metric interpretation,
evaluation behavior, or result regeneration MUST be versioned, documented, and traceable.

### IX. Safe and Economical Artifact Inspection

Large benchmark artifacts MUST be inspected through targeted, economical methods.

Agents and contributors MUST NOT load large structured outputs, traces, source documents,
parsed datasets, or large exports fully into model context unless explicitly instructed to
do so.

Acceptable inspection patterns include:

- small samples;
- targeted filters;
- text search;
- structured queries;
- aggregation scripts;
- purpose-built inspection utilities.

Manual inspection should focus on evidence extraction and aggregation, not full-context
dumping.

### X. Explicit Confirmation for Expensive Execution

Commands or workflows that may call real model providers MUST NOT be executed without
explicit user confirmation.

Any automated workflow that could consume provider tokens, create provider-side jobs, or
incur external cost MUST pause and surface the action to the user before proceeding.

Tests MUST use fixtures, mocks, local examples, or provider-free validation unless a
provider-backed execution is explicitly requested.

### XI. Documentation Fidelity

Documentation MUST describe the current implementation accurately.

Examples, reproducibility instructions, command references, artifact descriptions, metric
definitions, and analysis guidance MUST match the implemented workflow. Obsolete behavior
may be documented only in clearly labeled migration or historical notes.

When command names, artifact names, strategy names, metric definitions, or workflow phases
change, documentation MUST be updated in the same change set or explicitly tracked as
follow-up work.

### XII. Simplicity and Research Sufficiency

The benchmark MUST prefer the simplest design that preserves research validity,
reproducibility, traceability, and extensibility for known use cases.

New abstractions, metadata fields, schemas, layers, or configuration mechanisms MUST be
justified by current benchmark needs, accepted specifications, or demonstrated variation
across supported domains, providers, strategies, or artifacts.

The project MUST NOT introduce speculative generality, complex taxonomies, or metadata
structures only because they may be useful in the future.

When a simpler representation is sufficient to preserve interpretation and reproducibility,
the simpler representation MUST be preferred.

When changing existing designs, plans SHOULD actively look for opportunities to reduce
complexity, remove obsolete compatibility paths, collapse unnecessary abstractions, or
simplify metadata, as long as research validity, reproducibility, traceability, and migration
expectations are preserved.

## Research Constraints

These constraints govern how benchmark results are collected, reported, and interpreted.

- Cost, performance, and quality figures from different strategies MUST be computed under
  comparable measurement conditions before comparison.
- Metrics MUST be interpreted together with their provenance, unit, source, lifecycle phase,
  and collection method.
- New metrics or changes to existing metric semantics MUST define provenance, unit, source,
collection method, and phase when relevant.
- Estimated or derived metrics MAY be useful for analysis, but they MUST be labeled as such
  and MUST NOT be presented as authoritative provider-reported values.
- Accuracy and quality figures MUST distinguish individual judge votes, aggregate outcomes,
  majority outcomes, and unanimous outcomes.
- Operation overhead MUST be attributed to the strategy and execution path that generated it.
- Observability limitations, especially for remote or provider-controlled execution, MUST be
  documented alongside results.
- Benchmark results MUST NOT overstate claims. Findings apply to the specific datasets,
  model versions, provider configurations, questions, and context-provisioning strategies
  tested.
- Analysis-ready exports MUST be treated as derived artifacts unless explicitly defined as
  canonical by a versioned artifact contract.

## Development Constraints

These constraints govern how the codebase is maintained.

- Use the smallest verification command that reasonably validates the change.
- Do not call real model providers in automated tests.
- Do not run the full benchmark pipeline unless explicitly requested.
- Do not perform opportunistic refactors.
- Changes MUST be scoped to the requested task or the active specification.
- Public contracts MUST be changed only through explicit specifications, tests, and
  documentation updates.
- Provider adapters, strategy orchestrators, dataset adapters, evaluators, and exporters
  MUST remain independently testable where practical.
- New abstractions MUST be justified by current benchmark needs, not speculative future use.
- New metrics or changes to existing metric semantics MUST define provenance,
  unit, source, collection method, and phase.

## Specification and Planning Governance

Specification-driven development artifacts are part of the research record.

Feature specifications SHOULD define what must change and why, without prematurely fixing
implementation details. Implementation plans SHOULD translate accepted specifications into
technical decisions, affected files, tests, contracts, migration steps, and validation
commands.

Plans MUST include a Constitution Check that verifies compliance with applicable principles
before implementation begins. The check MUST be revisited when the plan changes materially.

For changes affecting artifact contracts, evaluation semantics, strategy behavior, metric
definitions, metric provenance, dataset boundaries, provider behavior, or CLI workflow, the
specification MUST state whether the change is:

- backward compatible;
- intentionally breaking;
- transitional with aliases or migration support;
- documentation-only;
- experimental or exploratory.

## Governance

This constitution supersedes informal practices for the ContextBench project. It is the
authoritative reference for design decisions, code reviews, specifications, implementation
plans, and documentation.

### Amendment Procedure

1. Propose the amendment with rationale and identify affected principles.
2. Classify the version bump:
   - MAJOR: principle removal, incompatible redefinition, or governance model change;
   - MINOR: new principle, new governance section, or material expansion;
   - PATCH: clarification, wording improvement, typo fix, or non-semantic refinement.
3. Update this file and the version metadata.
4. Update dependent templates, agent guidance, specifications, or documentation when
   affected.
5. Record the change in Git history with a clear commit message.

### Compliance Review

All non-trivial specifications and implementation plans MUST be reviewed for compliance with
this constitution. Any exception MUST be documented with rationale and scope.

### Runtime Guidance

Agent-specific runtime guidance may live in files such as `AGENTS.md`, `CLAUDE.md`, or
agent-specific skills. Those files may define operational behavior for tools, but they MUST
NOT override the research and architecture principles in this constitution.

**Version**: 1.2.0 | **Ratified**: 2026-05-08 | **Last Amended**: 2026-05-09
