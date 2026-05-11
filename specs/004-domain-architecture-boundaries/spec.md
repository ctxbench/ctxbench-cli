# Feature Specification: Domain Architecture Boundaries

**Feature Branch**: `chore/architecture-redesign-roadmap` (shared branch for the architecture-roadmap group)
**Created**: 2026-05-10
**Status**: Draft (roadmap-level)

## Overview

This is a **roadmap-level** specification. It establishes the *intent*, *scope*, and *boundary contracts* required to make the benchmark **domain-neutral**. Today the implementation assumes Lattes is the only domain; this specification fixes the architectural boundary that separates **benchmark core** from **dataset/domain adapters** so Lattes becomes one adapter implementation among many possible domains.

It does **not** implement any new domain (e.g., software repositories), it does **not** migrate Lattes artifacts, and it does **not** introduce a plugin framework. It defines the **responsibilities, dependency direction, and validation expectations** that prevent Lattes-specific concepts from leaking into generic code.

This specification operationalizes Constitution Principle VII (Boundary Isolation and Dependency Direction) for the dataset/domain boundary, and Principle XII (Simplicity and Research Sufficiency) by deferring everything that is not strictly required to fix the boundary.

**Relationship to Spec 003.** Spec 003 carries the seven boundary contracts defined here across the **external distribution boundary** between `ctxbench-cli` and externally distributed dataset packages. Spec 003 cites the FRs of this spec by number rather than restating them; this spec owns the responsibility definitions, and Spec 003 owns the distribution-level corollaries (dataset metadata, identity, version, fixtures, and comparability metadata for dataset-contributed strategies).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a Stable Description of Core vs Adapter Responsibilities (Priority: P1)

A researcher or future contributor reads the architecture documentation and can answer, for any benchmark concern, whether it belongs to the **benchmark core** or to a **dataset/domain adapter**. The description is concrete enough that an unrelated domain (e.g., a software-repository domain) could in principle be added by writing only an adapter, without modifying generic core code.

**Why this priority**: Without an explicit boundary, every new domain encourages ad-hoc edits to generic code, eroding research validity across domains. This story is the foundation for all subsequent work in the roadmap; it must be stable before any Lattes refactor or new-domain work begins.

**Independent Test**: A researcher reads this specification and the architecture docs derived from it and, for each of the seven boundary concerns enumerated in FR-005 through FR-011, can name (a) what the core requires from the adapter, (b) what the adapter must not require from the core.

**Acceptance Scenarios**:

1. **Given** a researcher reads the architecture docs, **When** they look up "instance loading", **Then** they find a description of what the core asks of the adapter and what the adapter returns, expressed only in generic vocabulary (`dataset`, `instance`, `instanceId`).
2. **Given** a researcher reads the architecture docs, **When** they look up "context artifact provider", **Then** they find a description in which Lattes-specific names (curriculum, HTML, blocks) do not appear in the core-facing contract.
3. **Given** a researcher reads the architecture docs, **When** they look up "evidence artifact provider", **Then** the role is distinct from the context artifact role and is described in generic terms.

---

### User Story 2 - Catalogue and Quarantine Lattes-Specific Leakage (Priority: P2)

A researcher reading this specification can identify the categories of Lattes-specific behavior that are currently embedded in generic code and confirm the rules that will be applied to relocate or quarantine that behavior. The spec does not perform the relocation; it defines what counts as leakage and where it must live instead.

**Why this priority**: Naming the leakage categories explicitly prevents future code review from treating "Lattes-flavored" generic code as acceptable. Without this, the Lattes refactor that follows risks being unbounded.

**Independent Test**: A reviewer reads the spec and can apply the leakage rules to any code path or doc reference, producing a binary verdict: belongs in core, belongs in adapter, or is currently misplaced.

**Acceptance Scenarios**:

1. **Given** a reviewer encounters a function in the generic core that references `curriculum`, **When** they apply the rules from this spec, **Then** the function is classified as leakage that must be relocated to a Lattes adapter.
2. **Given** a reviewer encounters a tool definition tied to "Lattes blocks", **When** they apply the rules from this spec, **Then** the tool is classified as a Lattes-adapter responsibility, not a generic tool provider responsibility.
3. **Given** a reviewer encounters a question-structure assumption (e.g., "questions always reference curriculum sections") in generic code, **When** they apply the rules from this spec, **Then** the assumption is classified as leakage of Lattes-specific task structure.

---

### User Story 3 - Validate the Boundary with a Provider-Free Fake Domain (Priority: P3)

A maintainer can demonstrate that the benchmark core is domain-neutral by running it end-to-end against a **fake domain** (a minimal in-repository adapter producing synthetic instances, tasks, context artifacts, evidence artifacts, and tools) without calling any real LLM provider. If the core requires Lattes-specific behavior, the fake domain run breaks; if the boundary is correct, the fake domain run succeeds.

**Why this priority**: Provider-free validation is the only sustainable way to keep the boundary honest over time. Without it, regressions reintroduce Lattes-specific assumptions silently. Constitution Principle X requires provider-free validation patterns.

**Independent Test**: A maintainer runs the fake-domain validation in CI or locally. The benchmark workflow (plan → execute → eval → export) completes against the fake domain. No real provider is invoked. The boundary contracts defined in FR-005 through FR-011 are exercised.

**Acceptance Scenarios**:

1. **Given** the fake domain is registered as a dataset/domain adapter, **When** `ctxbench plan` runs against it, **Then** trials are planned over fake instances and tasks without any Lattes-specific code being touched.
2. **Given** trials over the fake domain exist, **When** `ctxbench execute` runs in inline strategy, **Then** the execution engine reads context artifacts via the boundary contract, not via a Lattes-specific reader, and produces `responses.jsonl` without invoking a real provider.
3. **Given** responses over the fake domain exist, **When** `ctxbench eval` runs with a fake judge, **Then** the evaluation engine reads evidence artifacts via the boundary contract and writes evaluation artifacts in the generic vocabulary.
4. **Given** the fake-domain run is complete, **When** the maintainer inspects the produced artifacts, **Then** no Lattes-specific term (curriculum, HTML, parsed-curriculum, Lattes blocks) appears in any artifact.

---

### Edge Cases

- What if a generic component requires a small, generic capability that today exists only inside the Lattes adapter (e.g., reading a context artifact from disk)? The capability is generalized at the boundary; the Lattes adapter implements it under that contract. The capability MUST NOT be added to core under a Lattes-flavored name.
- What if a domain (current or future) cannot supply a particular boundary capability (e.g., no tool provider)? The boundary contract MUST permit the adapter to declare the capability unavailable; the core MUST handle this without falling back to Lattes-specific behavior.
- What if a Lattes-specific concept appears in CLI flags or selectors (e.g., a flag named after curriculum sections)? It is recorded as leakage to be relocated; the generic CLI MUST expose only generic selectors (dataset, instance, task, strategy, format, repetition).
- What if a researcher writes a one-off script that touches Lattes internals directly? Such scripts are out of scope for the boundary; only code shipped under the generic benchmark surface is subject to the boundary rules.
- What if a domain adapter wants to enrich a trial with domain-specific metadata? The adapter MAY attach domain-scoped metadata under a clearly namespaced field; the core MUST treat such metadata as opaque and MUST NOT interpret it.

## Requirements *(mandatory)*

### Functional Requirements

#### Benchmark Core Responsibilities

- **FR-001**: The benchmark core MUST own, and only own, the generic lifecycle: experiment loading, trial planning, trial execution orchestration, strategy orchestration, response writing, evaluation orchestration, evaluation writing, export, and status reporting.
- **FR-002**: The benchmark core MUST express its inputs and outputs exclusively in the generic vocabulary defined by the architecture: `dataset`, `instance`, `task`, `trial`, `response`, `evaluation`, `trace`, `result`. No Lattes-specific term may appear in core code paths, type signatures, log messages, or core-facing documentation.
- **FR-003**: The benchmark core MUST depend on dataset/domain adapters only through stable boundary contracts; the core MUST NOT import, reference, or branch on the identity of any specific domain (no `if domain == "lattes"` and no equivalent).
- **FR-004**: The benchmark core MUST function correctly with any adapter that satisfies the boundary contracts, including the fake domain defined by FR-019.

#### Dataset/Domain Adapter Responsibilities

- **FR-005**: A dataset/domain adapter MUST be the sole owner of domain-specific decoding, parsing, and representation choices. The adapter MAY embed arbitrary domain logic internally, provided its core-facing surface exposes only generic vocabulary.

#### Boundary Contracts

The following requirements name the seven boundary capabilities the core consumes from adapters. The spec fixes the **responsibilities** and the **direction of the dependency**; concrete interface signatures, names, and serialization formats are deferred to planning.

- **FR-006**: **Instance loading boundary**. The adapter MUST be able to enumerate the instances of a dataset, identified by `instanceId`, and to resolve an `instanceId` to whatever domain payload the adapter itself needs. The core MUST only consume `instanceId` and adapter-provided handles; it MUST NOT parse, traverse, or interpret the underlying domain payload.
- **FR-007**: **Task loading boundary**. The adapter MUST be able to enumerate tasks for an instance (or for a dataset, when tasks are dataset-scoped), identified by `taskId`. The core MUST treat task content as opaque except for fields the adapter explicitly promotes into the generic task surface (e.g., a prompt-ready statement). No Lattes-specific question structure may appear in the core task surface.
- **FR-008**: **Context artifact provider boundary**. The adapter MUST be able to provide, for a given `(instanceId, task, strategy, format)` combination, the context artifact that the strategy will use. The adapter is responsible for any domain-specific representation choice (HTML, parsed structure, summary, etc.). The core MUST consume the artifact through the generic context-artifact contract only.
- **FR-009**: **Evidence artifact provider boundary**. The adapter MUST be able to provide, for evaluation purposes, the evidence artifact a judge requires to assess responses for a given task or instance. The evidence-artifact role MUST be distinct from the context-artifact role: context is what the model under test sees; evidence is what the judge sees. An adapter MAY supply the same payload for both, but the boundary keeps the roles separate.
- **FR-010**: **Tool provider boundary**. The adapter MUST be able to expose domain-specific tools usable by `local_function`, `local_mcp`, and `remote_mcp` strategies. The core MUST consume tools through a generic tool-provider contract; the core MUST NOT hard-code tool names, schemas, or call semantics that are Lattes-specific.
- **FR-011**: **Evaluation evidence provider boundary**. The adapter MUST be able to provide, alongside the evidence artifact (FR-009), any auxiliary references or excerpts a judge needs to ground its assessment. The core MUST treat these references as opaque payload to be passed to the judge, not as content for the core to interpret.

#### Leakage Prevention

- **FR-012**: The following Lattes-specific concepts MUST NOT appear in core code, generic interfaces, generic documentation, or generic artifact field names: `curriculum`, `parsed curriculum`, `Lattes HTML`, `Lattes blocks`, and the Lattes-specific question structure (e.g., section-anchored question shape). Where these concepts exist today in generic code, they are classified as leakage to be relocated to a Lattes adapter.
- **FR-013**: Lattes-specific identifiers used as dataset identifiers (e.g., the dataset name itself) MAY remain in dataset-level configuration. They MUST NOT propagate into core behavior beyond opaque pass-through.
- **FR-014**: Generic CLI selectors (`--dataset`, `--instance`, `--task`, `--strategy`, `--format`, `--repetition`, `--trial-id`, `--ids-file`, `--status`, `--judge`, `--model`, `--provider`) MUST remain domain-neutral. Domain-specific CLI flags MUST NOT be added to the generic CLI; if a domain needs additional inputs, they belong in experiment configuration consumed by the adapter, not in the generic CLI surface.
- **FR-015**: Generic artifact field names MUST remain in the generic vocabulary (per Spec 001 and Spec 002). Adapter-supplied per-trial metadata MAY be carried under a clearly namespaced field, but the core MUST NOT interpret it.

#### Provider-Free Fake Domain Validation

- **FR-016**: The repository MUST host a **fake domain** adapter sufficient to exercise the boundary contracts FR-006 through FR-011 end-to-end.
- **FR-017**: The fake domain MUST be usable without invoking any real LLM provider. Where the workflow requires a model response or judge vote, a fake or scripted responder MUST stand in.
- **FR-018**: The fake domain MUST be exercised through the standard CLI (`ctxbench plan`, `ctxbench execute`, `ctxbench eval`, `ctxbench export`, `ctxbench status`) with no special branches or core code paths reserved for it.
- **FR-019**: A successful fake-domain run MUST produce all relevant target artifacts (from Spec 002) in the generic vocabulary, and MUST NOT produce any Lattes-specific term in any artifact.
- **FR-020**: The fake-domain validation MUST be the canonical proof that the boundary is correct; any change to the boundary contracts MUST be re-validated against the fake domain.

#### Scope Discipline

- **FR-021**: This specification MUST NOT implement the software-repository domain or any new domain other than the fake validation domain.
- **FR-022**: This specification MUST NOT migrate Lattes artifacts, refactor the existing Lattes implementation, or rename Lattes-internal concepts. It only defines what is *generic* and what is *adapter-local*.
- **FR-023**: This specification MUST NOT redesign artifact roles or representations beyond what is required to keep the boundary clean; artifact contracts remain governed by Spec 002.
- **FR-024**: This specification MUST NOT introduce a plugin framework, entry-point discovery system, dynamic loading mechanism, or configuration-driven adapter registry. Adapter registration is a planning concern.
- **FR-025**: This specification MUST NOT change CLI command names, lifecycle phase names, or generic terminology already established by Spec 001.

### Key Entities

- **Benchmark Core**: The set of generic components responsible for the lifecycle phases (plan, execute, eval, export, status), strategy orchestration, and artifact writing. Speaks only the generic vocabulary.
- **Dataset/Domain Adapter**: A module that implements the boundary contracts for one concrete domain (e.g., Lattes, software repositories, the fake domain). Owns all domain-specific decoding, parsing, and representation. Has no privileged knowledge of, or coupling to, other adapters or core internals.
- **Instance**: One unit of a dataset, identified by `instanceId`. The adapter owns its content; the core handles only the identifier and adapter-supplied handles.
- **Task**: A unit of work over an instance (or a dataset), identified by `taskId`. The adapter owns its content; the core consumes only the fields the adapter promotes to the generic task surface.
- **Context Artifact**: The representation of an instance that a strategy supplies to the model under test. The adapter produces it; the core consumes it through a generic contract.
- **Evidence Artifact**: The representation supplied to a judge for evaluation. Distinct in role from the context artifact, even when the underlying payload coincides.
- **Tool Provider**: An adapter capability that exposes domain-specific tools to strategies that use tools (`local_function`, `local_mcp`, `remote_mcp`). Tools are domain-local; the contract that exposes them is generic.
- **Evaluation Evidence Provider**: An adapter capability that supplies judges with the references, excerpts, or grounding payloads required for assessment.
- **Fake Domain**: An in-repository adapter implementation that exercises the boundary contracts using synthetic, provider-free data, used as the canonical proof that the core is domain-neutral.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the seven boundary concerns named in this specification (instance loading, task loading, context artifact, evidence artifact, tool provider, evaluation evidence provider, plus dataset/instance enumeration) are described with explicit core-facing responsibilities and adapter responsibilities.
- **SC-002**: 100% of the Lattes-specific concepts enumerated in FR-012 are listed as out-of-bounds for generic code, with their target location named (Lattes adapter).
- **SC-003**: A complete benchmark workflow against the fake domain runs end-to-end without invoking any real LLM provider and without exercising any Lattes-specific code path.
- **SC-004**: All artifacts produced by the fake-domain run use only generic vocabulary; zero Lattes-specific terms appear in produced artifacts.
- **SC-005**: A future contributor proposing a new domain can identify, from this specification alone, the seven boundary capabilities they must implement, without needing to read core code.

## Scope

### In Scope

- The responsibility split between benchmark core and dataset/domain adapter.
- The seven boundary contracts (instance, task, context artifact, evidence artifact, tool, evaluation evidence, plus enumeration).
- Identification of Lattes-specific leakage categories that must move to the Lattes adapter.
- The fake-domain validation pattern as the canonical boundary proof.
- Generic CLI surface stability (no domain-specific flags).
- Generic artifact vocabulary stability (no domain-specific field names in core artifacts).

### Out of Scope

- Implementing the software-repository domain or any other concrete new domain.
- Refactoring the existing Lattes implementation; relocating Lattes-specific code is follow-on work.
- Migrating Lattes artifacts, datasets, or fixtures.
- Redesigning artifact roles or representations beyond what the boundary requires (governed by Spec 002).
- A plugin framework, adapter registry, or dynamic discovery mechanism.
- Changing CLI command names, phase names, or generic terminology (governed by Spec 001).
- Concrete interface signatures, function names, file paths, package layout, or serialization formats — deferred to planning.
- Strategy implementations, provider adapters, judge model selection.

## Dependencies and Enables

### Depends On

- **Spec 001 — Command Model and Phase Renaming**: Adopts the target command and terminology vocabulary (`execute`, `trials.jsonl`, `responses.jsonl`, `trialId`, `taskId`, `response`, `remote_mcp`). Any conflict between Spec 001 and this spec is resolved by Spec 001.
- **Spec 002 — Artifact Contracts**: Adopts the canonical artifact set, the canonical/derived distinction, and the five-class metric provenance taxonomy. This spec does not redefine artifacts; it only governs which code is allowed to own their domain-specific contents.

### Enables (Future Specs)

- **Lattes adapter spec**: Relocates Lattes-specific code (curriculum parsing, HTML handling, Lattes block model, Lattes question structure) under the boundary contracts defined here.
- **Software-repository domain spec**: Adds a second concrete adapter, validating the boundary against a genuinely different domain.
- **Adapter registration and configuration spec**: How experiments select an adapter, how multiple adapters coexist, and whether discovery is configuration-driven or explicit.
- **Boundary-contract interface specs**: Per-boundary concrete interfaces (signatures, schemas, error semantics) for instance, task, context-artifact, evidence-artifact, tool, and evaluation-evidence providers.
- **Fake-domain test-pack spec**: The detailed contents of the fake domain, the scenarios it exercises, and the assertions it carries.

## Decisions Deferred to Planning

The following decisions are intentionally left open and MUST be resolved by follow-on specifications or by the planning phase of dependent work:

- Concrete interface signatures for each of the seven boundary contracts.
- Package and module layout: where adapter code physically lives and how it is imported by core.
- How experiments declare which adapter to use (configuration field, CLI flag at experiment level, manifest entry, etc.).
- The exact shape and contents of the fake domain (number of instances, tasks, tools, evidence types).
- The strategy-by-strategy behavior of the fake responder (inline, local_function, local_mcp, remote_mcp).
- Whether the Lattes adapter is a separate Python package, a sub-package of ctxbench, or a directory under the existing tree.
- Whether tool and evaluation-evidence providers are mandatory capabilities or optional capabilities with a documented "not supported" path.
- The exact error semantics when an adapter declines a capability (silent skip, explicit error, configuration warning, etc.).
- Whether adapter-supplied per-trial metadata uses a single opaque field, a namespaced map, or a structured envelope.
- The test runner and CI integration for the fake-domain validation.

## Affected Concepts, Contracts, and Documentation

- **Affected internal contracts**: The boundary between any module that currently consumes Lattes-specific representations and the generic execution/evaluation/export paths. Anywhere generic code today reaches into Lattes payloads must switch to a boundary-mediated interaction.
- **Affected docs**: The architecture documents under `docs/architecture/` (container, component, dynamic, vocabulary) gain explicit boundary descriptions; any generic-flavored doc currently using Lattes-specific examples is annotated to clarify that Lattes is one adapter, not the canonical case.
- **Affected CLI surface**: None directly. The generic CLI is reaffirmed as domain-neutral; no new flags are added by this spec.
- **Affected artifacts**: None directly. Artifact names and field names remain governed by Spec 002. This spec only constrains *who is allowed to own* the domain-specific portions of an artifact's contents.
- **Unaffected**: Provider adapters (OpenAI/Google/Anthropic), strategy orchestration logic that is already domain-neutral, judge selection, dataset identifiers, and dataset/experiment loading mechanics that are already generic.

## Assumptions

- The target command model and phase terminology (Spec 001) and the artifact contracts (Spec 002) apply across all domains, including the fake domain.
- The current implementation contains Lattes-specific code in places that this spec classifies as core; the existence of that leakage is the motivation for this spec but is not itself in scope to fix.
- Lattes will remain a supported domain after this spec lands; its functionality is preserved, only its location in the architecture changes (via follow-on work).
- The fake domain is acceptable as a permanent in-repository fixture used for validation and CI; it is not a research domain.
- No provider-backed commands are executed as part of authoring or validating this specification.
- This spec sits inside the early-roadmap group on the current branch and intentionally avoids implementation depth.
- The classification of a concept as "Lattes-specific" applies to the concept's role in the architecture, not to whether a string happens to mention Lattes; for example, a dataset identifier named `lattes` in configuration is acceptable, while a generic function named after a Lattes block is not.
