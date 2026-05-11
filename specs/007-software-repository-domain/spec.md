# Feature Specification: Software Repository Domain (Placeholder)

**Feature Branch**: `chore/architecture-redesign-roadmap`
**Created**: 2026-05-11
**Status**: Placeholder (not ready for planning or implementation)
**Input**: Roadmap-level intent capture for adding a second domain — software repository artifacts — to CTXBench, on top of the contracts established by Specs 003, 004, 005 and first exercised by Spec 006.

## Overview

This spec is a **placeholder**. It records intent, dependencies, expected concepts, and open questions for adding a *software repository* domain to CTXBench. It does **not** define final tasks, final artifact schemas, repository tool signatures, or implementation steps. Those are deferred until the open questions below are resolved through a follow-on spec.

The motivation is to evaluate context provisioning strategies on instances that are software repository artifacts or snapshots, so that CTXBench is not validated only against the Lattes (curriculum) domain. A second domain is the canonical way to demonstrate that the dataset extension contracts (Spec 003), the core/adapter boundary (Spec 004), and the role × representation artifact model (Spec 005) are genuinely domain-neutral and not Lattes-shaped.

This spec must remain **lightweight** until it is promoted. Its job at this stage is to:

- Reserve roadmap slot 007 for the second-domain effort.
- Name the expected concepts so the team can reason about them.
- Surface the open questions that must be answered before this becomes implementable.
- Make it explicit that nothing in `ctxbench-cli` is to be modified for this domain until the placeholder is promoted.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reserve the second-domain slot (Priority: P1)

A maintainer scanning the roadmap can see that a second domain (software repository) is planned, depends on Specs 003/004/005/006, and is not yet ready for planning or implementation.

**Why this priority**: Without an explicit placeholder, the work risks being started ad hoc inside `ctxbench-cli` and violating the boundary that Specs 003 and 004 establish. The placeholder is the artifact that keeps that boundary visible while the design is still open.

**Independent Test**: The spec file exists at `specs/007-software-repository-domain/spec.md`, declares status *Placeholder*, names its dependencies, and lists the open questions that must be resolved before promotion.

**Acceptance Scenarios**:

1. **Given** a maintainer reading the roadmap, **When** they reach slot 007, **Then** they see a domain reservation with explicit *not ready* status and explicit dependencies on Specs 003, 004, 005, 006.
2. **Given** a contributor considering work in this area, **When** they read this spec, **Then** they understand that no code, schema, or strategy change in `ctxbench-cli` is authorized by this spec.

---

### User Story 2 - Open questions are visible and unresolved (Priority: P1)

A reviewer can see exactly which decisions are still open so the team does not silently pick answers in implementation.

**Why this priority**: A placeholder spec's value comes from making unresolved questions inspectable. Each open question is a fork the design has not taken yet.

**Independent Test**: The Open Questions section enumerates each fork (instance unit, task set, context vs evidence boundary, required tools, observable metrics, dataset licensing) and each question is *unanswered* rather than answered with a placeholder default.

**Acceptance Scenarios**:

1. **Given** a reviewer reading the Open Questions, **When** they look for a default answer to any question, **Then** they find none — only the question and its implications.
2. **Given** a future planning attempt, **When** the planner reaches an open question, **Then** the spec directs them to resolve it through promotion rather than guess.

---

### User Story 3 - Concept vocabulary is named in domain-neutral terms (Priority: P2)

When this spec is later promoted, the vocabulary it introduces (repository snapshot, source files as context, README/docs as context, code index, dependency metadata, ground-truth annotations, repository tools) maps cleanly onto the five roles from Spec 005 without introducing new roles.

**Why this priority**: Concept naming now reduces the chance that promotion will require redefining Spec 005's role model.

**Independent Test**: Every likely concept enumerated below is paired with the Spec 005 role it is expected to occupy, without inventing a new role.

**Acceptance Scenarios**:

1. **Given** the likely concepts list, **When** mapped against Spec 005's five roles (source, context, evidence, normalized/derived, metadata), **Then** every concept lands in exactly one role.
2. **Given** a concept that cannot land in one of the five roles, **When** discovered, **Then** the promotion process is required to either reclassify it or escalate to Spec 005 — not to add a sixth role here.

---

### Edge Cases

- **Instance granularity is unclear.** A repository can be addressed at multiple granularities (whole repo, commit, snapshot, package, module). Picking one is the first promotion-blocking decision; this spec does not pick.
- **Same payload, different role.** A README file may serve as *context* for some tasks and as *evidence* for others (e.g., "summarize the README" vs "did the model find the README"). Resolution belongs to Spec 005's multi-role payload rule, not to a new role.
- **Code index ambiguity.** A code index might be *context* (the strategy hands it to the model), *normalized/derived* (built deterministically from source), or both. The resolution mirrors Lattes parsed JSON in Spec 006 §FR-017.
- **Dependency metadata fit.** Dependency manifests (e.g., lockfiles) describe the instance and are not directly answered against, so they default to *metadata*; this expectation must be reconfirmed at promotion.
- **Licensing/privacy risk.** Some repositories cannot be redistributed. The dataset must be chosen with explicit license review; the placeholder must not commit to any specific corpus.
- **Repository size.** A whole-repo snapshot may exceed any reasonable context budget; the strategy/context selection rules (Spec 005 §strategy selection) determine which artifacts are eligible, not the dataset.
- **Direct import temptation.** A contributor may be tempted to add `ctxbench-cli/repo/...` code "to get started." This is forbidden — any repository-domain code lives in a separate dataset package, exactly as Lattes does after Spec 006.

## Requirements *(mandatory)*

These are **placeholder discipline requirements** — they constrain what this spec is and what its promotion must achieve. They are not implementation requirements. Concrete functional requirements (task set, artifact schemas, tool signatures, evaluation semantics) are deferred until promotion.

### Functional Requirements

#### Placeholder discipline

- **FR-001**: This spec MUST remain marked *Placeholder* until the Open Questions below are resolved and the spec is promoted by a follow-on revision.
- **FR-002**: This spec MUST NOT authorize any change to `ctxbench-cli` (code, schemas, strategies, CLI behavior, artifact contracts).
- **FR-003**: This spec MUST NOT authorize any provider-backed execution.
- **FR-004**: Promotion of this spec MUST resolve every Open Question below in writing before any planning task is created.
- **FR-005**: Promotion of this spec MUST NOT redefine artifacts, roles, terminology, distribution, or boundary contracts established by Specs 001, 002, 003, 004, 005; any genuine gap MUST be escalated to the owning spec, mirroring Spec 006 §FR-027.

#### Domain boundary

- **FR-006**: The software repository domain MUST be packaged as a separate dataset package (the same pattern as `ctxbench/lattes` after Spec 006); it MUST NOT be embedded in `ctxbench-cli`.
- **FR-007**: The software repository dataset package MUST integrate through the dataset extension contracts of Spec 003; it MUST NOT introduce its own extension mechanism.
- **FR-008**: `ctxbench-cli` MUST contain zero software-repository-specific data, code, or identifiers, both before and after promotion.

#### Role mapping (expected, not final)

- **FR-009**: Every likely concept named in this spec MUST map to one of the five roles defined by Spec 005 (source, context, evidence, normalized/derived, metadata); no new role is introduced here.
- **FR-010**: The repository snapshot is expected to map to *source* and possibly to *context* when handed to a strategy; the final decision is deferred to promotion.
- **FR-011**: Selected source files, README, and other documentation files are expected to map to *context*; the final selection rules are deferred to promotion.
- **FR-012**: A code index is expected to map to *context*, *normalized/derived*, or both (multi-role payload per Spec 005); the final decision is deferred to promotion.
- **FR-013**: Dependency metadata (manifests, lockfiles) is expected to map to *metadata*; the final decision is deferred to promotion.
- **FR-014**: Ground-truth annotations used for evaluation are expected to map to *evidence*; the final decision is deferred to promotion.

#### Terminology

- **FR-015**: All vocabulary in this spec and its promotion MUST conform to Spec 001 (task, trial, response, `taskId`, `trialId`); legacy terminology (`questionId`, `runId`, `answer`, `query`, `queries.jsonl`, `answers.jsonl`, `copa`) is forbidden.
- **FR-016**: Representation names introduced for repository artifacts MUST be domain-neutral at the contract surface (Spec 005); repository-specific terms appear only inside the dataset package.

#### Scope discipline

- **FR-017**: Promotion of this spec MUST NOT introduce new generic strategies. Dataset-specific presets are permitted only if they conform to Spec 003's comparability-metadata requirements.
- **FR-018**: Promotion of this spec MUST NOT introduce a plugin framework, dynamic remote code loading, or any execution mechanism beyond what Spec 003 already defines.
- **FR-019**: Promotion of this spec MUST NOT change model-provider behavior or provider adapters.
- **FR-020**: Promotion of this spec MUST NOT require provider-backed execution for verification (Constitution Principle X).

### Open Questions

These questions are **unanswered on purpose**. Promotion is blocked until they are answered.

- **OQ-001 — Instance unit.** Is a benchmark instance a whole repository, a specific commit, a snapshot at a point in time, a package, or a module? Each choice has different reproducibility, sizing, and evidence-attribution consequences.
- **OQ-002 — First task set.** What tasks are meaningful for the first version (e.g., locate-symbol, summarize-module, identify-dependency, explain-failure, find-test-for-function)? The task set determines which artifacts are *context* and which are *evidence*.
- **OQ-003 — Context vs evidence boundary.** For each candidate task, which artifacts are *context* (handed to the model by the strategy) and which are *evidence* (consulted by evaluation but not by the strategy)? Mis-assigning these violates Spec 004's strategy/evaluation separation.
- **OQ-004 — Required repository tools.** Which tools must be exposed through the dataset package contract (e.g., list files, read file, search symbol, inspect dependency, inspect README)? Tools determine what `local_function`, `local_mcp`, and `remote_mcp` strategies can do on this domain.
- **OQ-005 — Metric observability classification.** For each metric the domain reports, which is *reported*, *measured*, *derived*, *estimated*, or *unavailable* (per the project metric-provenance rule)? This must be answered before evaluation is designed.
- **OQ-006 — Dataset selection.** Which concrete repository corpus can be used without licensing or privacy issues? The corpus choice determines redistribution, snapshot policy, and update cadence.
- **OQ-007 — Reproducibility of snapshots.** How is a repository snapshot pinned and verified across runs (commit SHA, archived tarball hash, content-addressed store)? This must align with Spec 003's dataset identity and version handshake.
- **OQ-008 — Evidence provenance.** Where do ground-truth annotations come from (hand-authored, mined from history, synthesized), and how is their authority recorded? This affects evaluation trust and Constitution Principle VIII (traceability).

### Key Entities *(expected, not final)*

These entities are named so reviewers share a vocabulary. Their schemas are deferred to promotion.

- **Software Repository Dataset Package**: An external dataset package (sibling to `ctxbench/lattes`) that integrates with CTXBench through Spec 003's dataset extension contracts.
- **Repository Instance**: The unit of benchmarking, whose granularity (repo / commit / snapshot / package / module) is OQ-001.
- **Repository Snapshot**: A reproducibly addressable view of a repository at a specific state; expected role *source*, possibly also *context* when handed to a strategy.
- **Selected Source File**: A source file picked by the dataset package's context-artifact provider for a given task; expected role *context*.
- **Repository Documentation Artifact**: README, design notes, or other documentation files; expected role *context*, occasionally *evidence* for documentation-targeted tasks (multi-role payload).
- **Code Index**: A pre-computed structure over the snapshot (symbol table, file tree, embedding index, call graph, etc.); expected role *context* and/or *normalized/derived*, decided at promotion (OQ-003).
- **Dependency Metadata**: Manifests, lockfiles, or equivalents; expected role *metadata*.
- **Ground-Truth Annotation**: The reference answer used by evaluation (e.g., the file where a symbol is defined, the correct dependency name); expected role *evidence*.
- **Repository Tool**: A reader or operator exposed through the dataset package contract (e.g., list files, read file, search symbol, inspect dependency, inspect README), available to `local_function`, `local_mcp`, and `remote_mcp` strategies.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The roadmap contains an explicit, unambiguous reservation for the software repository domain at slot 007.
- **SC-002**: A reviewer can list every Open Question (OQ-001 through OQ-008) from this spec without consulting any other document.
- **SC-003**: A reviewer can map every Key Entity in this spec to exactly one of Spec 005's five roles (with at most one multi-role payload, code index, flagged explicitly).
- **SC-004**: No commit to `ctxbench-cli` introduces software-repository-specific data, code, or identifiers while this spec is in *Placeholder* status.
- **SC-005**: Promotion of this spec produces a revision in which every Open Question has a recorded answer and FR-001 through FR-020 are either satisfied or replaced by concrete functional requirements.

## Assumptions

- Specs 001, 002, 003, 004, 005, and 006 are stable enough at the time of promotion to host a second domain without redesign. If any of them is unstable, promotion is blocked until they stabilize.
- The first second-domain effort will reuse the dataset extension contracts validated by Spec 006 (Lattes); it does not require a new contract surface.
- The first second-domain effort will reuse the four generic strategies (`inline`, `local_function`, `local_mcp`, `remote_mcp`); domain-specific *presets* may be added under Spec 003's comparability-metadata rules but new generic strategies are out of scope.
- Repository tools, when added, are exposed through the dataset package, not through `ctxbench-cli`.
- Reproducibility (Constitution Principle VIII) applies unchanged: dataset identity and version are declared by the repository dataset package and recorded per run, exactly as Spec 003 requires.
- Provider-free verification (Constitution Principle X) applies unchanged: contract conformance can be demonstrated without provider-backed execution.
- Metric provenance (project CLAUDE.md rule) applies unchanged: every metric is classified as *reported*, *measured*, *derived*, *estimated*, or *unavailable*.

## Dependencies

- **Spec 001 — Command Model and Phase Renaming.** Provides the workflow, commands and phases the benchmark must conform to.
- **Spec 002 — Artifact Contracts.** Provides the canonical artifacts and the role they play in `ctxbench`.
- **Spec 003 — Dataset Distribution and Extension Contracts.** Provides the extension surface that the repository dataset package must conform to.
- **Spec 004 — Domain Architecture Boundaries.** Provides the core/adapter boundary that prevents repository-domain code from leaking into `ctxbench-cli`.
- **Spec 005 — Dataset Artifact Model.** Provides the five-role × representation model that every repository concept must map onto without introducing a new role.
- **Spec 006 — Lattes Dataset Extraction and Migration.** Provides the first proof that the contracts in 003/004/005 hold against a real dataset. The repository domain is the *second* proof; if Spec 006 reveals contract gaps, those must be resolved before this spec is promoted.

## In Scope

- Reserving roadmap slot 007 for the software repository domain.
- Recording intent, dependencies, expected concepts, and open questions.
- Establishing the placeholder discipline (FR-001–FR-005) and boundary discipline (FR-006–FR-008) that bind this spec until promotion.

## Out of Scope

- Implementation of the repository dataset package.
- Final task set for the domain.
- Final artifact schema (source, context, evidence, normalized/derived, metadata representations).
- Final repository tool signatures.
- Provider-backed execution and any verification that requires it.
- Any large plugin framework or dynamic remote code execution.
- Modifications to `ctxbench-cli` to accommodate this domain.
- Selection of a concrete corpus or dataset (deferred to OQ-006).

## Decisions deferred to promotion

- Instance granularity (OQ-001).
- First task set (OQ-002).
- Context-vs-evidence assignment per task (OQ-003).
- Required repository tools (OQ-004).
- Metric provenance classification (OQ-005).
- Concrete dataset corpus and licensing posture (OQ-006).
- Snapshot reproducibility mechanism (OQ-007).
- Ground-truth annotation provenance and authority recording (OQ-008).
- Whether a repository-domain preset is justified, and if so, its concrete contents (deferred under Spec 003's comparability-metadata rules).

## Future specs enabled by this one (after promotion)

- A concrete software-repository dataset package spec (sibling to `ctxbench/lattes`).
- A repository-domain preset spec, if presets are justified.
- A multi-domain comparability spec, once a second domain exists and cross-domain comparisons become meaningful.
- A repository-domain tool catalog spec, if the tool surface grows beyond what Spec 003 covers.
