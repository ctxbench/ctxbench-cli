# Feature Specification: Artifact Contracts

**Feature Branch**: `chore/architecture-redesign-roadmap` (shared branch for the artifact-roadmap group)
**Created**: 2026-05-10
**Status**: Draft (roadmap-level)

## Overview

This is a **roadmap-level** specification. It establishes the *intent*, *scope*, and *acceptance shape* of the ctxbench artifact contracts so that subsequent specifications (schemas, instrumentation, export tooling) can plug into a stable backbone. It does **not** define field-level schemas, file format versioning, or migration tooling — those are deferred to follow-on specifications.

The aim is to give researchers and future spec authors a single, stable reference for **which artifacts exist, what role they play, and how metric provenance is communicated** — without committing to implementation details that are not yet decided.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identify Canonical vs Derived Artifacts (Priority: P1)

A researcher reading the project documentation can determine, for every artifact produced by the benchmark, whether it is a **canonical** record (a primary source of truth for a phase) or a **derived** artifact (computed deterministically from canonical artifacts). They can also tell which phase produced it.

**Why this priority**: Without this classification, downstream tooling and reporting cannot tell which artifacts are authoritative and which can be regenerated. This blocks reproducibility analysis and incremental re-evaluation.

**Independent Test**: A researcher reads the artifact-contracts documentation and, for each artifact name in the canonical set, can answer: (a) which phase produces it, (b) whether it is canonical or derived, (c) whether it is per-trial or aggregate.

**Acceptance Scenarios**:

1. **Given** a researcher reads the artifact-contracts reference, **When** they look up `trials.jsonl`, **Then** the reference identifies it as an execution-phase canonical artifact.
2. **Given** a researcher reads the artifact-contracts reference, **When** they look up `evals-summary.json`, **Then** the reference identifies it as an evaluation-phase derived artifact.
3. **Given** a researcher reads the artifact-contracts reference, **When** they look up `results.csv`, **Then** the reference identifies it as an analysis-ready export derived from evaluation artifacts.

---

### User Story 2 - Understand Metric Provenance (Priority: P2)

A researcher inspecting a metric in any exported artifact can determine how that metric was obtained, using a single shared provenance vocabulary.

**Why this priority**: Mixing reported, measured, derived, and estimated values without labels invalidates cost and accuracy comparisons across strategies. The provenance taxonomy is the minimum contract that protects research conclusions.

**Independent Test**: For any metric appearing in a canonical or derived artifact, the artifact-contracts reference assigns exactly one provenance class from the agreed taxonomy.

**Acceptance Scenarios**:

1. **Given** a researcher reads the artifact-contracts reference, **When** they look up the metric provenance taxonomy, **Then** they find the five classes `reported`, `measured`, `derived`, `estimated`, `unavailable` with definitions.
2. **Given** a metric is labeled `estimated` in an artifact, **When** the researcher reads the reference, **Then** it is clear that estimated metrics MUST NOT be presented as reported or measured.
3. **Given** a metric is not available for a given provider or strategy, **When** the researcher inspects the artifact, **Then** the metric is labeled `unavailable` rather than recorded as zero.

---

### User Story 3 - Migrate from Legacy Artifacts Without Aliases (Priority: P3)

A researcher with prior-run artifacts named under legacy conventions reads the migration notes and learns that the benchmark neither produces nor reads legacy artifacts; the researcher is responsible for any local migration of their own historical files.

**Why this priority**: Without an explicit no-compatibility statement, downstream scripts may silently fail or read mixed-vintage artifacts. Clear migration documentation prevents corrupted analyses.

**Independent Test**: A researcher reads the migration notes and confirms that each legacy artifact name is mapped to its target replacement with an explicit "no alias" statement.

**Acceptance Scenarios**:

1. **Given** a researcher searches the migration notes for `queries.jsonl`, **When** the entry is found, **Then** it is mapped to `trials.jsonl` with an explicit no-alias statement.
2. **Given** a researcher searches the migration notes for `answers.jsonl`, **When** the entry is found, **Then** it is mapped to `responses.jsonl` with an explicit no-alias statement.
3. **Given** a researcher searches the migration notes for `traces/queries/<runId>.json`, **When** the entry is found, **Then** it is mapped to `traces/executions/<trialId>.json` with an explicit no-alias statement.

---

### Edge Cases

- What if a prior-run directory contains both legacy and target artifacts side-by-side? The benchmark reads only target artifacts; legacy files are ignored. The researcher is responsible for archiving or deleting them.
- What if a new artifact is added in a future specification? It MUST declare its phase, its class (canonical or derived), and its metric-provenance commitments before being adopted as part of the canonical set.
- What if a metric's provenance depends on the strategy or provider (e.g., reported for one provider, estimated for another)? The provenance label is recorded per record, not globally per metric.
- What if a trace file is missing for a given `trialId`? Its absence is treated as `unavailable` for any trace-derived metric; it is not silently substituted.

## Requirements *(mandatory)*

### Functional Requirements

#### Artifact Set

- **FR-001**: The artifact-contracts reference MUST enumerate the canonical artifact set, including at minimum: `manifest.json`, `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, `results.csv`, `traces/executions/<trialId>.json`, `traces/evals/<trialId>.json`.
- **FR-002**: Each artifact in the canonical set MUST be labeled with its producing phase (plan, execute, eval, export) and its class (canonical or derived).
- **FR-003**: The reference MUST distinguish the following artifact roles: **execution artifacts** (produced by `ctxbench execute`), **evaluation artifacts** (produced by `ctxbench eval`), **analysis-ready exports** (produced by `ctxbench export`), and **traces** (per-trial files under `traces/`).
- **FR-004**: `manifest.json` MUST be identified as a plan-phase canonical artifact that records the inputs sufficient to reproduce subsequent phases.

#### Derived vs Canonical

- **FR-005**: Canonical artifacts MUST be identified as the authoritative record of a phase; derived artifacts MUST be reproducible from canonical artifacts without re-invoking providers.
- **FR-006**: Analysis-ready exports (e.g., `results.csv`, `evals-summary.json`) MUST be classified as derived; regenerating them MUST NOT require re-running execution or evaluation.

#### Legacy Artifacts and Compatibility

- **FR-007**: The artifact-contracts reference MUST list the following legacy artifact names with their target replacements and an explicit no-alias policy: `queries.jsonl` → `trials.jsonl`, `answers.jsonl` → `responses.jsonl`, `traces/queries/<runId>.json` → `traces/executions/<trialId>.json`.
- **FR-008**: Writers MUST produce only target artifact names; legacy artifact names MUST NOT be written by any phase.
- **FR-009**: Readers MUST NOT consume legacy artifact names; encountering a legacy artifact in an input directory is not an error but is also not used.
- **FR-010**: Migration MUST be documented as the researcher's responsibility; no automated migration tooling is committed to in this specification.

#### Metric Provenance

- **FR-011**: The reference MUST define exactly five metric-provenance classes: `reported`, `measured`, `derived`, `estimated`, `unavailable`.
- **FR-012**: Every metric appearing in a canonical or derived artifact MUST be representable under exactly one provenance class per record.
- **FR-013**: `estimated` metrics MUST NOT be presented as `reported` or `measured`; `unavailable` MUST NOT be represented as a zero value unless zero is the observed value.
- **FR-014**: The provenance taxonomy MUST NOT be extended with confidence scores, sub-classes, or additional taxonomies in this specification; extensions are deferred to follow-on specs.

#### Scope Discipline

- **FR-015**: This specification MUST NOT define field-level schemas for any artifact.
- **FR-016**: This specification MUST NOT define file format versioning, validation tooling, or migration tooling; these are deferred to follow-on specifications.
- **FR-017**: This specification MUST NOT change dataset semantics, introduce new domains, or expand the set of strategies.
- **FR-018**: This specification MUST NOT prescribe how individual providers or strategies emit metrics; it only fixes the contract surface.

### Key Entities

- **Artifact**: A file persisted by a benchmark phase. Has a name, a producing phase, and a class.
- **Canonical Artifact**: An artifact that is the authoritative record of a phase and cannot be regenerated without re-invoking that phase.
- **Derived Artifact**: An artifact computed deterministically from one or more canonical artifacts.
- **Execution Artifact**: An artifact produced by the execution phase (e.g., `trials.jsonl`, `responses.jsonl`, `traces/executions/<trialId>.json`).
- **Evaluation Artifact**: An artifact produced by the evaluation phase (e.g., `evals.jsonl`, `judge_votes.jsonl`, `traces/evals/<trialId>.json`).
- **Analysis-Ready Export**: A derived artifact produced by the export phase for downstream analysis (e.g., `results.csv`, `evals-summary.json`).
- **Trace**: A per-trial record of provider interaction stored under `traces/executions/` or `traces/evals/`.
- **Metric Provenance**: A label drawn from the five-class taxonomy that describes how a metric value was obtained.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The artifact-contracts reference enumerates 100% of the target canonical artifact set and labels each with phase and class.
- **SC-002**: 100% of legacy artifact names listed in the assumptions are mapped to a target replacement with an explicit no-alias statement.
- **SC-003**: The metric-provenance taxonomy is defined with exactly five classes; no additional sub-classes or confidence dimensions are introduced.
- **SC-004**: Zero implementation-level details (file format versions, validation logic, schema fields) appear in this specification.
- **SC-005**: A future spec author can cite this document as the source of artifact classification and metric provenance vocabulary without needing to re-derive either.

## Scope

### In Scope

- Enumeration of the canonical artifact set by name.
- Classification of each artifact by phase (plan, execute, eval, export) and class (canonical, derived).
- Distinction between execution artifacts, evaluation artifacts, analysis-ready exports, and traces.
- Mapping of legacy artifact names to their target replacements.
- Reader and writer behavior toward legacy artifacts (no-compat policy).
- The metric provenance taxonomy: `reported`, `measured`, `derived`, `estimated`, `unavailable`.
- Migration documentation expectations.

### Out of Scope

- Field-level schemas for any artifact (deferred to follow-on schema specs).
- File format versioning policy.
- Validation tooling and conformance checking.
- Automated migration tooling for legacy artifacts.
- Dataset semantics, dataset identifiers, and domain-specific logic.
- New strategies, new providers, or new phases.
- Provider-specific instrumentation details.
- Confidence scores or extensions to the provenance taxonomy.
- Performance, latency, or storage targets for artifacts.

## Dependencies and Enables

### Depends On

- **Spec 001 — Command Model and Phase Renaming**: This spec adopts the target command and terminology vocabulary established in 001 (`execute`, `trials.jsonl`, `responses.jsonl`, `trialId`, `taskId`, `response`, `remote_mcp`). Any conflict between 001 and this spec is resolved by 001.

### Enables (Future Specs)

- **Per-artifact schema specs**: Field-level definitions for `manifest.json`, `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, `results.csv`, and trace files.
- **Metric instrumentation specs**: How each provenance class is captured per provider and per strategy.
- **Export tooling specs**: How analysis-ready exports are generated and validated.
- **Trace format specs**: Structure of per-trial trace files for executions and evaluations.

## Decisions Deferred to Planning

The following decisions are intentionally left open and MUST be resolved by follow-on specifications or by the planning phase of dependent work:

- Exact field schemas for each artifact.
- File format version markers and forward-compatibility policy.
- Whether traces are sharded, compressed, or stored as a single document per trial.
- The concrete set of metrics carried in each artifact and their provenance class per provider.
- Whether `manifest.json` carries strategy/provider details inline or by reference.
- Validation tooling: what enforces these contracts at write time and read time.
- Whether a CLI subcommand or external script handles legacy-artifact migration (assumption: external; can be reconsidered).
- How provenance labels are physically represented in records (e.g., per-field suffix, sidecar map, structured envelope).

## Affected Concepts, Contracts, and Documentation

- **Affected artifacts**: All artifacts currently produced by `ctxbench execute`, `ctxbench eval`, and `ctxbench export`.
- **Affected docs**: Any reference to legacy artifact names (`queries.jsonl`, `answers.jsonl`, `traces/queries/<runId>.json`) in CLI help, README, migration notes, and example scripts.
- **Affected internal contracts**: Writer paths that emit per-phase artifacts; reader paths in `eval` and `export` that consume execution artifacts; trace persistence paths.
- **Unaffected**: Dataset definitions, plan-construction logic that does not touch artifact naming, provider adapters internal to each strategy, and judge model selection logic.

## Assumptions

- The target command model and phase terminology defined in Spec 001 apply across all artifacts named here.
- Legacy artifacts (`queries.jsonl`, `answers.jsonl`, `traces/queries/<runId>.json`) are not migrated automatically; researchers handle their own historical archives.
- Dataset identifiers (e.g., `copa`) are not artifacts in the sense of this specification; they are dataset-level concerns and are out of scope.
- The five-class metric provenance taxonomy is sufficient for current research needs; extensions require a new accepted specification.
- No provider-backed commands are executed as part of authoring or validating this specification.
- This spec sits inside the early-roadmap group on the current branch and intentionally avoids implementation depth.
