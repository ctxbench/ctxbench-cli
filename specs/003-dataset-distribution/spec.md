# Feature Specification: Dataset Distribution

**Feature Branch**: `chore/architecture-redesign-roadmap` (shared branch for the architecture-roadmap group)
**Created**: 2026-05-11
**Status**: Draft (roadmap-level)

## Overview

This is a **roadmap-level** specification. It establishes the *intent*, *scope*, and *contract surface* required for concrete datasets to live **outside** the `ctxbench-cli` repository — in separate dataset repositories or packages — and to integrate with the benchmark through a small, stable, explicit contract.

Today the implementation embeds Lattes-specific data and behavior directly inside `ctxbench-cli`. This specification fixes that by:

- defining the **dataset package contract** the benchmark consumes from external datasets;
- defining what remains in `ctxbench-cli` and what must move to dataset repositories/packages;
- defining how experiments **reference** external datasets and how **identity** and **version** are recorded for reproducibility;
- treating the `ctxbench/lattes` repository as the **first conformance target** and reference implementation, while keeping the contract definition independent of whatever Lattes currently does.

It does **not** implement any new domain (e.g., software repositories), it does **not** finalize the artifact role/representation model, it does **not** introduce a generic plugin framework or dynamic remote code execution, and it does **not** migrate Lattes data. It defines the **packaging boundary** between the benchmark tool and concrete datasets.

This specification operationalizes Constitution Principle VII (Boundary Isolation and Dependency Direction) at the **distribution boundary**, Principle VIII (Reproducibility and Traceability) by requiring dataset identity and version in artifacts, Principle X (Explicit Confirmation for Expensive Execution) by requiring provider-free validation, and Principle XII (Simplicity and Research Sufficiency) by deferring everything not strictly required to host an external dataset package.

**Relationship to Spec 004.** Specs 003 and 004 are an authored-together pair. Spec 004 owns the seven internal core/adapter boundary contracts (instance loading, task loading, context-artifact provider, evidence-artifact provider, tool provider, evaluation-evidence provider, plus dataset/instance enumeration). This spec does not redefine those contracts; it carries them across the **distribution boundary** between `ctxbench-cli` and externally distributed dataset packages, and adds only the distribution-specific responsibilities the external package must satisfy: dataset metadata, identity, version, fixture coverage, and comparability metadata for dataset-contributed strategies. Where a mandatory extension point below maps to a Spec 004 boundary contract, this spec cites the corresponding Spec 004 FR rather than restating the responsibility.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan an Experiment Against an Externally Distributed Dataset (Priority: P1)

A researcher writes an experiment that references the `ctxbench/lattes` dataset package — which lives outside the `ctxbench-cli` repository — and runs `ctxbench plan` to produce planned trials. The planning step resolves instances and tasks through the dataset package contract; no Lattes-specific code is imported from `ctxbench-cli`.

**Why this priority**: This is the foundational researcher experience. If experiments cannot reference an externally distributed dataset, every other goal of this spec is unreachable. It is also the most user-visible payoff of the distribution boundary.

**Independent Test**: A researcher writes a minimal experiment configuration that names `ctxbench/lattes` as the dataset, runs `ctxbench plan`, and observes planned trials referencing Lattes instances and tasks. The `ctxbench-cli` repository does not need to contain any Lattes source files, payloads, or imports for the run to succeed.

**Acceptance Scenarios**:

1. **Given** an experiment configuration that references the `ctxbench/lattes` dataset by its dataset identity, **When** the researcher runs `ctxbench plan`, **Then** the dataset's instances and tasks are enumerated through the dataset package contract and the resulting `trials.jsonl` contains the planned trials in the generic vocabulary.
2. **Given** a researcher inspects the planning manifest, **When** they read the recorded dataset reference, **Then** the manifest names the dataset's identity and version sufficient for another researcher to obtain the same dataset package.
3. **Given** the `ctxbench-cli` repository contains no Lattes-specific source files or payloads, **When** the researcher runs `ctxbench plan` against the externally distributed `ctxbench/lattes` package, **Then** the planning phase still completes successfully.

---

### User Story 2 - Reproduce a Run from Recorded Dataset Identity and Version (Priority: P2)

A second researcher takes the artifacts produced by another researcher's run, reads the dataset identity and version recorded in those artifacts, and uses that information to obtain the same dataset package and re-execute or re-evaluate the trials. The recorded identity and version are sufficient to disambiguate which dataset and which revision were used.

**Why this priority**: Reproducibility is a first-class research requirement (Constitution Principle VIII). A dataset distributed externally must still be uniquely identifiable from the artifacts it produced, or the benchmark loses its scientific value.

**Independent Test**: A reviewer reads `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, the planning manifest, and any export, and from those alone can name (a) the dataset repository or package, (b) its version, and (c) the dataset's identity. No additional out-of-band knowledge is required.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** a reviewer inspects the planning manifest, **Then** the manifest records the dataset identity, the dataset version, and the dataset repository or package origin.
2. **Given** a completed run, **When** a reviewer inspects the exported result artifacts, **Then** the dataset identity and version travel with the exported records or with their accompanying manifest, with no loss of provenance.
3. **Given** a reviewer obtains the recorded dataset package at the recorded version, **When** they re-plan the same experiment, **Then** the planned trials are recomputable in the sense defined by Constitution Principle VIII (no required re-run of model inference for provenance reconstruction).

---

### User Story 3 - Validate the Distribution Contract Against `ctxbench/lattes` Without Provider Calls (Priority: P3)

A maintainer demonstrates that the dataset package contract is correct by exercising it against `ctxbench/lattes` end-to-end through the standard CLI, using provider-free fixtures or a fake responder. The full planning, execution, evaluation, and export workflow completes without invoking any real LLM provider; the Lattes package is the conformance target, not a special case.

**Why this priority**: Without provider-free validation, the contract is unverifiable (Constitution Principle X). Using `ctxbench/lattes` as the conformance target proves that the contract is general enough to host a real dataset while still being checkable in CI without external cost.

**Independent Test**: A maintainer runs the validation workflow that points at the `ctxbench/lattes` package, with provider calls replaced by fixtures or a fake responder. The workflow completes; the resulting artifacts use the generic vocabulary; no provider tokens are consumed; the Lattes-specific contract behavior is exercised through the dataset package interface, not through Lattes-private imports.

**Acceptance Scenarios**:

1. **Given** the `ctxbench/lattes` package satisfies the dataset package contract, **When** the maintainer runs `ctxbench plan` → `ctxbench execute` → `ctxbench eval` → `ctxbench export` against it with provider-free fixtures, **Then** the workflow completes end-to-end and produces the canonical artifacts in the generic vocabulary.
2. **Given** the validation workflow runs in CI, **When** a contract field is added, removed, or renamed in `ctxbench-cli` without a corresponding update in `ctxbench/lattes`, **Then** the validation surfaces the divergence rather than silently passing.
3. **Given** `ctxbench/lattes` exposes both context artifacts and evidence artifacts, **When** the workflow runs, **Then** the context artifacts are obtained through the dataset's context-artifact provider and the evidence artifacts are obtained through the dataset's evidence-artifact provider, with no `ctxbench-cli` code reaching into Lattes internals.

---

### User Story 4 - Datasets Contribute Optional Extensions With Comparability Metadata (Priority: P4)

A dataset package optionally contributes domain-specific tools, evaluation helpers, strategy presets, or experimental strategy descriptors. When the dataset proposes a strategy (canonical, dataset-specific, or experimental), the proposal carries the metadata required for strategy comparability so that results across strategies remain interpretable.

**Why this priority**: Optional extension points unlock dataset-specific research, but they can silently break strategy comparability (Constitution Principle VI) if datasets ship strategies without describing their semantics. Requiring comparability metadata on dataset-proposed strategies prevents this regression.

**Independent Test**: A reviewer inspects a dataset package that contributes a strategy descriptor and confirms that every comparability field required by this specification is present and inspectable. A dataset package that omits a required field is rejected at load time or flagged as non-conformant.

**Acceptance Scenarios**:

1. **Given** a dataset package contributes a tool provider, **When** a strategy that uses tools runs against that dataset, **Then** the tool provider is consumed through the dataset package contract and the contribution is recorded in the trial trace as dataset-supplied.
2. **Given** a dataset package contributes an experimental strategy descriptor, **When** the descriptor omits any required comparability field (name, classification, context access mode, inline-vs-operation, local-vs-remote, loop ownership, metric provenance for the strategy's metrics, observability limitations, comparability implications), **Then** the descriptor is treated as non-conformant.
3. **Given** a dataset package contributes evaluation helpers, **When** an evaluator uses them, **Then** the helpers are consumed as opt-in dataset behavior and their contribution is recorded in the evaluation trace as dataset-supplied.

---

### Edge Cases

- What if a dataset package supplies only the mandatory extension points and none of the optional ones? The contract is satisfied; the benchmark must function with the minimum set, and strategies or evaluators that require optional capabilities must surface a clear "capability unavailable" path rather than fall back to embedded behavior.
- What if a dataset package supplies a custom format-specific reader for an artifact type that is also handled by a built-in reader inside `ctxbench-cli`? The dataset-supplied reader applies for that dataset; `ctxbench-cli` MUST NOT silently override it.
- What if a dataset's identity or version is missing from the package metadata? The dataset MUST be treated as non-conformant; experiments referencing it MUST fail the planning step with an explicit error rather than recording partial provenance.
- What if two dataset packages declare the same dataset identity? Such a collision is the dataset author's responsibility; the benchmark MUST refuse to resolve an ambiguous reference rather than pick one silently.
- What if a researcher has a one-off script that reads Lattes files directly from disk, bypassing the dataset package contract? Such scripts are out of scope for this spec; only the supported benchmark surface is subject to the distribution rules.
- What if a dataset package contains experimental fields not described by this contract? Such fields MAY exist inside the dataset, but they MUST NOT be exposed to `ctxbench-cli` except as opaque metadata under a clearly namespaced field.

## Requirements *(mandatory)*

### Functional Requirements

#### Core vs External Distribution

- **FR-001**: `ctxbench-cli` MUST support datasets distributed by external repositories or external packages. The benchmark MUST function with datasets that physically live outside this repository.
- **FR-002**: `ctxbench-cli` MUST NOT require any concrete dataset to live inside its own repository. The generic benchmark code MUST be installable, runnable, and testable in the absence of any concrete dataset payload, given only a dataset package that satisfies the contract.
- **FR-003**: The code-level rule that prevents `ctxbench-cli` from importing, referencing, or branching on dataset-specific modules, identifiers, or concepts is governed by Spec 004 §FR-003 (no domain branching) and §FR-012 (Lattes leakage prevention) and is not restated here. This spec extends that boundary to **repository contents and packaging**: existing dataset-specific assets currently embedded inside the `ctxbench-cli` repository (Lattes data, fixtures, readers, parsing code, artifact mappings, evidence providers, tool definitions) are classified as **distribution debt** and are subject to relocation under FR-004.
- **FR-004**: Lattes-specific readers, artifact mappings, fixtures, evidence providers, and tool definitions belong in the `ctxbench/lattes` repository (or behind a Lattes-specific adapter boundary derived from Spec 004). They MUST NOT remain in `ctxbench-cli` after the migration enabled by this spec.

#### Dataset Package Contract — Mandatory Extension Points

The dataset package contract is the set of capabilities a dataset MUST expose to be usable by the benchmark. The following extension points are mandatory; concrete signatures, schemas, error semantics, and packaging mechanics are deferred to planning.

FR-005 through FR-007 and FR-014 are **distribution-specific** responsibilities (metadata, identity, version, fixtures) that have no counterpart in Spec 004. FR-008, FR-009, FR-011, FR-012, and FR-013 carry **Spec 004 boundary contracts** across the distribution boundary and are stated by reference, not by restatement; the responsibility itself is owned by the cited Spec 004 FR. FR-010 (artifact location) is distribution-specific in that file layout is internal to the dataset package, but the artifact is consumed across the boundaries cited in FR-011 and FR-012.

- **FR-005**: **Dataset metadata**. The dataset package MUST expose human-readable metadata sufficient to describe the dataset's purpose, domain area, intended uses, and known limitations.
- **FR-006**: **Dataset identity**. The dataset package MUST expose a stable, unique identity that distinguishes it from every other dataset reachable by the benchmark. The identity MUST be recordable in artifacts (per FR-018) and resolvable to a dataset package origin.
- **FR-007**: **Dataset version**. The dataset package MUST expose a version that uniquely identifies the dataset's revision. Two runs against the same dataset identity at the same version MUST be reproducible in the sense defined by Constitution Principle VIII.
- **FR-008**: **Instance loading**. The dataset package MUST expose the instance-loading capability defined by Spec 004 §FR-006 across the distribution boundary. The responsibility itself is not restated here.
- **FR-009**: **Task loading**. The dataset package MUST expose the task-loading capability defined by Spec 004 §FR-007 across the distribution boundary. The responsibility itself is not restated here.
- **FR-010**: **Artifact location and resolution**. The dataset package MUST expose the means to locate and resolve dataset artifacts the benchmark needs (raw payloads, parsed structures, derived forms). File layout, directory structure, and filename convention are internal concerns of the dataset package; consumption across the boundary is governed by FR-011 and FR-012 below.
- **FR-011**: **Context artifact provider**. The dataset package MUST expose the context-artifact provider boundary defined by Spec 004 §FR-008 across the distribution boundary. The responsibility itself, and the context/evidence role separation, are not restated here.
- **FR-012**: **Evidence artifact provider**. The dataset package MUST expose the evidence-artifact provider boundary defined by Spec 004 §FR-009 across the distribution boundary. The responsibility itself, and the context/evidence role separation, are not restated here.
- **FR-013**: **Format-specific readers**. The dataset package MUST expose, or compose internally, the readers required for whatever payload formats the dataset uses. The companion rule that the benchmark core MUST NOT embed dataset-specific readers is governed by Spec 004 §FR-005 (adapter ownership of domain-specific decoding) and is not restated here; this requirement only fixes that the readers live inside the dataset package.
- **FR-014**: **Fixtures or examples for provider-free tests**. The dataset package MUST expose at least one fixture or example sufficient to exercise the mandatory extension points end-to-end without invoking any real LLM provider. This fixture MUST be the canonical evidence that the package satisfies the contract.

#### Dataset Package Contract — Optional Extension Points

The following extension points are optional; their absence MUST be handled by the benchmark without falling back to dataset-specific embedded behavior.

- **FR-015**: **Tool provider (optional)**. A dataset package MAY expose a tool provider that contributes domain-specific tools to strategies that consume tools (`local_function`, `local_mcp`, `remote_mcp`). When present, tools MUST be consumed through the Spec 004 tool-provider boundary.
- **FR-016**: **Evaluation helpers (optional)**. A dataset package MAY expose evaluation helpers used by judges for grounding, comparison, or auxiliary scoring. When present, the helpers cross the boundary through Spec 004 §FR-011's evaluation-evidence provider; their use MUST be recorded in evaluation traces as dataset-supplied.
- **FR-017**: **Strategy presets and experimental strategy descriptors (optional)**. A dataset package MAY contribute canonical-strategy presets (preset configurations of strategies already defined by `ctxbench-cli`), dataset-specific strategies (strategies meaningful only against this dataset), or experimental strategy descriptors (strategies proposed for research evaluation). Every dataset-contributed strategy MUST carry the comparability metadata defined in FR-024.

#### Dataset Identity, Version, and Provenance in Artifacts

- **FR-018**: Every benchmark run MUST record, in artifacts the run produces, enough information to identify the dataset package origin, the dataset identity, and the dataset version used. The exact carrier (planning manifest, per-trial fields, accompanying provenance file) is deferred to planning, but the information MUST travel with the run.
- **FR-019**: Dataset identity and version recorded at planning time MUST be preserved unchanged through execution, evaluation, and export. No phase may silently overwrite or coerce these fields.
- **FR-020**: Where exports omit individual trial provenance (e.g., aggregate results), the dataset identity and version MUST still be reachable from the export, either inline or through an accompanying manifest.

#### Experiment Reference and Discovery

- **FR-021**: Experiment configurations MUST be able to reference an external dataset package using a stable, declarative identity that does not require dynamic remote code execution to resolve.
- **FR-022**: Dataset-provided behavior MUST be explicit and inspectable: a researcher MUST be able to determine, before running the benchmark, which extension points a dataset package exposes, which it omits, and which optional extensions it contributes.
- **FR-023**: The mechanism for discovering or configuring dataset packages (configuration field, installation convention, manifest entry, explicit registration call, etc.) is deferred to planning, BUT the mechanism MUST NOT rely on dynamic remote code execution, opaque auto-discovery, or any mechanism that hides which dataset is being loaded from the researcher.

#### Strategy Comparability for Dataset-Contributed Strategies

- **FR-024**: When a dataset package contributes a strategy preset, dataset-specific strategy, or experimental strategy descriptor, the contribution MUST carry the following metadata fields, at minimum:
  - **strategy name** — the identifier under which the strategy is exposed;
  - **classification** — canonical (a preset of an existing `ctxbench-cli` strategy), dataset-specific (meaningful only for this dataset), or experimental (proposed for research);
  - **context access mode** — how context is exposed to the model under test;
  - **inline-vs-operation** — whether context is provided inline in the prompt or through operations/tools;
  - **local-vs-remote** — whether tool/operation execution is local or remote;
  - **loop ownership** — who controls the model/tool loop (benchmark, provider, dataset-supplied component);
  - **metric provenance per strategy-specific metric** — for each metric the strategy reports, its provenance class (reported, measured, derived, estimated, unavailable) per Constitution Principle III;
  - **observability limitations** — which signals are unobservable, provider-side only, or partially observable;
  - **comparability implications** — explicit notes on how, if at all, results from this strategy may be compared with canonical strategies.

  A dataset-contributed strategy missing any of these fields MUST be treated as non-conformant.

#### `ctxbench/lattes` as First Conformance Target

- **FR-025**: This specification MUST treat the `ctxbench/lattes` repository as the first dataset package against which the contract is validated. `ctxbench/lattes` is the **reference implementation**; it is not the contract definition.
- **FR-026**: Any divergence between the contract defined here and the current behavior of `ctxbench/lattes` MUST be resolved by changing `ctxbench/lattes` to satisfy the contract, not by widening the contract to accommodate `ctxbench/lattes`. Genuine contract gaps revealed by Lattes MUST be addressed by amending this specification or its successors, not by tacit accommodation.
- **FR-027**: The provider-free validation pattern from Spec 004 MUST be re-runnable against `ctxbench/lattes` once the contract is implemented. The Lattes conformance run is the canonical proof that this distribution contract is correct in practice.

#### Lattes Migration Expectations

- **FR-028**: Lattes-specific data, fixtures, readers, artifact mappings, tools, and evidence providers currently embedded in `ctxbench-cli` MUST migrate to the `ctxbench/lattes` repository (or to a Lattes-specific adapter boundary derived from Spec 004) as the implementation of this distribution contract proceeds. This specification names the migration; it does not perform it.
- **FR-029**: Migration MUST preserve the canonical artifact contracts from Spec 002. No artifact name, field name, schema, or provenance class introduced by Spec 002 may change as a side effect of the Lattes migration.
- **FR-030**: Migration MUST NOT silently change experiment semantics. Where the migration changes how a Lattes-specific behavior is reached (e.g., a tool invocation now resolves through the tool-provider boundary), the change MUST be documented but the observable benchmark behavior MUST remain equivalent.

#### Scope Discipline

- **FR-031**: This specification MUST NOT implement the software-repository domain or any new domain other than what is required to validate the contract.
- **FR-032**: This specification MUST NOT fully migrate Lattes data, refactor Lattes internals, or finalize Lattes-internal naming. It defines what is *generic*, what is *dataset-package-local*, and what is *migration debt*.
- **FR-033**: This specification MUST NOT design a large generic plugin framework, dynamic loader, entry-point discovery system, or runtime-extensible registry beyond the minimum required to reference an external dataset package.
- **FR-034**: This specification MUST NOT introduce dynamic remote code execution to load datasets, strategies, tools, or readers.
- **FR-035**: This specification MUST NOT require provider-backed execution to author, validate, or maintain the contract.
- **FR-036**: This specification MUST NOT change model provider adapters except where required by the dataset extension contract (and no such requirement is anticipated within this spec's scope).
- **FR-037**: This specification MUST NOT finalize the dataset artifact role or representation model beyond what is required to define the mandatory and optional extension points; deeper redesign of artifact roles remains governed by Spec 002.
- **FR-038**: This specification MUST NOT change CLI command names, lifecycle phase names, or the generic vocabulary established by Spec 001.

### Key Entities

- **Domain**: A subject area to which a dataset belongs (e.g., academic curricula, source-code repositories, PDF documents). The benchmark core MUST NOT branch on domain identity; domains are descriptive metadata, not control flow.
- **Dataset**: A versioned collection of instances and tasks within a domain, satisfying the dataset package contract.
- **Dataset Repository**: A version-controlled code repository that hosts one or more datasets (e.g., `ctxbench/lattes`). The unit of source-control distribution.
- **Dataset Package**: An installable or referenceable artifact that exposes one or more datasets through the dataset package contract. The unit of consumption by `ctxbench-cli`.
- **Dataset Extension**: A capability a dataset package contributes — mandatory (e.g., context artifact provider) or optional (e.g., tool provider, strategy descriptor).
- **Dataset Adapter**: The code that satisfies the boundary contracts defined by Spec 004. A dataset package's mandatory extension points collectively act as its adapter.
- **Dataset Artifact**: A domain payload exposed by the dataset (raw, parsed, or derived). Its location and format are internal to the dataset package; the benchmark core consumes it only through the boundary contracts.
- **Context Artifact**: Defined by Spec 004 §FR-008. Here it is the payload produced by the dataset package's context-artifact provider across the distribution boundary.
- **Evidence Artifact**: Defined by Spec 004 §FR-009. Here it is the payload produced by the dataset package's evidence-artifact provider across the distribution boundary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the mandatory extension points in the dataset package contract (FR-005 through FR-014) are described with explicit responsibilities at the package side and clearly delimited expectations at the `ctxbench-cli` side.
- **SC-002**: `ctxbench-cli` builds, installs, and runs (in a provider-free configuration) without any Lattes-specific source file or payload present in its repository.
- **SC-003**: Every artifact produced by a run records the dataset identity, dataset version, and dataset package origin sufficient for an independent reviewer to obtain the same dataset.
- **SC-004**: `ctxbench/lattes` is exercisable end-to-end through `ctxbench plan` → `ctxbench execute` → `ctxbench eval` → `ctxbench export` using only the contract defined here and the provider-free validation pattern from Spec 004.
- **SC-005**: A dataset-contributed strategy that omits any field listed in FR-024 is detected as non-conformant; zero dataset-contributed strategies bypass the comparability requirements.
- **SC-006**: A future contributor implementing a second dataset package (e.g., software repositories) can do so by reading this specification and the documents it depends on, without needing to read `ctxbench-cli` core code or `ctxbench/lattes` internals.

## Scope

### In Scope

- The distribution boundary between `ctxbench-cli` and external dataset repositories/packages.
- The dataset package contract: mandatory and optional extension points.
- Dataset identity, version, and provenance recording in artifacts.
- The mechanism by which experiments reference external datasets (intent only; concrete mechanics deferred to planning).
- Comparability metadata requirements for dataset-contributed strategies.
- `ctxbench/lattes` as the first conformance target and reference implementation.
- High-level migration expectations for Lattes-specific code and data currently embedded in `ctxbench-cli`.

### Out of Scope

- Implementing the software-repository domain or any other concrete second domain.
- Fully migrating Lattes data, fixtures, or artifacts (the migration is named, not executed).
- Designing a large generic plugin framework, dynamic loader, or runtime-extensible registry.
- Dynamic remote code execution for datasets, strategies, tools, or readers.
- Provider-backed execution for contract authoring or validation.
- Changes to model provider adapters (none required by this spec).
- Finalizing the dataset artifact role/representation model beyond extension responsibilities (governed by Spec 002).
- Changing CLI command names, phase names, or generic vocabulary (governed by Spec 001).
- Concrete interface signatures, schemas, packaging formats, file layouts, or installation mechanics — deferred to planning.

## Dependencies and Enables

### Depends On

- **Spec 001 — Command Model and Phase Renaming**: Inherits the target command and terminology vocabulary; any conflict is resolved by Spec 001.
- **Spec 002 — Artifact Contracts**: Inherits the canonical/derived artifact distinction and the metric-provenance taxonomy. Dataset identity and version must travel within the artifact contracts defined there; this spec does not redefine those artifacts.
- **Spec 004 — Domain Architecture Boundaries**: Inherits the seven internal boundary contracts (instance, task, context artifact, evidence artifact, tool, evaluation evidence, plus enumeration). This spec defines how those internal boundaries are satisfied by an *externally distributed* dataset package; it does not redefine the boundaries themselves.

### Enables (Future Specs)

- **Lattes adapter / package conformance spec**: Concrete implementation of the dataset package contract by `ctxbench/lattes`, including the migration of Lattes-specific code out of `ctxbench-cli`.
- **Software-repository dataset spec**: A second dataset package validating the contract against a genuinely different domain.
- **Dataset package contract interface spec**: Per-extension-point concrete interfaces (signatures, schemas, error semantics) for the mandatory and optional extension points.
- **Experiment reference and resolution spec**: The concrete mechanism by which experiments name an external dataset and the benchmark resolves the reference.
- **Dataset provenance carrier spec**: The precise carrier for dataset identity and version inside the artifact set (manifest field, per-trial field, accompanying file).
- **Dataset-contributed strategy registry spec**: How dataset-contributed strategies are listed, namespaced, and reported alongside `ctxbench-cli` canonical strategies for comparison.

## Decisions Deferred to Planning

The following decisions are intentionally left open and MUST be resolved by follow-on specifications or by the planning phase of dependent work:

- The concrete shape of the dataset package contract surface (function signatures, class APIs, protocol classes, registration calls, configuration schemas, or a combination).
- The packaging mechanics for dataset packages: installable Python distribution, git submodule, path-based reference, manifest-pointed location, or any combination.
- The exact carrier of dataset identity and version inside artifacts (planning manifest field, per-trial JSONL field, accompanying provenance file, or all of the above).
- The format of dataset-contributed strategy metadata (descriptor file, in-package function, configuration block).
- The error semantics for missing mandatory extension points (load-time failure, planning-time failure, explicit decline path).
- The treatment of multiple datasets exposed by a single repository or package.
- The treatment of multiple versions of the same dataset coexisting in one environment.
- The CI integration for the `ctxbench/lattes` conformance run.
- Whether dataset packages may declare a minimum or maximum `ctxbench-cli` version compatibility.
- The precise interaction between dataset-supplied readers and any built-in `ctxbench-cli` readers (override, compose, refuse).
- Whether dataset-contributed evaluation helpers can affect aggregation semantics or only per-vote grounding.

## Affected Concepts, Contracts, and Documentation

- **Affected contracts**: The dataset package contract is new; its surface is defined at the responsibility level by this spec. Internal benchmark boundary contracts remain governed by Spec 004; artifact contracts remain governed by Spec 002.
- **Affected docs**: The architecture documents under `docs/architecture/` will gain a section describing the distribution boundary and the dataset package contract. The vocabulary doc will gain entries for *dataset repository*, *dataset package*, and *dataset extension*. Any current documentation that conflates `ctxbench-cli` with Lattes will be revised to treat Lattes as the first external dataset package.
- **Affected CLI surface**: None directly. CLI command names and generic flags remain governed by Spec 001. Any experiment-configuration field used to reference an external dataset is a configuration concern, not a CLI flag added by this spec.
- **Affected artifacts**: Artifact names and schemas remain governed by Spec 002. This spec adds the *requirement* that dataset identity and version travel within those artifacts; the exact field placement is deferred.
- **Unaffected**: Provider adapters, judge selection, strategy orchestration that is already domain-neutral, lifecycle phase names, generic vocabulary, the metric-provenance taxonomy.

## Assumptions

- The target command model and phase terminology (Spec 001), the artifact contracts (Spec 002), and the internal domain boundaries (Spec 004) apply across all datasets, including externally distributed ones.
- The `ctxbench/lattes` repository exists, is intended to host Lattes-specific code and data, and is the natural first conformance target. Its current contents may not yet satisfy this contract; bringing it into conformance is the work enabled by this spec, not work performed by this spec.
- A dataset package's identity and version are stable enough to be recorded as provenance; if a dataset package cannot supply stable identity or version, it is non-conformant.
- Datasets are not required to ship strategies. Strategies remain primarily owned by `ctxbench-cli`; dataset contributions in this area are opt-in and subject to the comparability requirements of FR-024.
- Provider-backed execution is not required to validate this contract; the fake-domain pattern from Spec 004 and the `ctxbench/lattes` conformance run together constitute the validation surface.
- The benchmark ecosystem may span multiple repositories without compromising reproducibility, provided dataset identity and version travel with artifacts.
- This spec sits inside the early-roadmap group on the current branch and intentionally avoids implementation depth. It is a contract definition, not an implementation plan.
- A string that happens to mention "lattes" in a dataset identity, a dataset package name, or a configuration field is acceptable; what is prohibited is *generic code* that branches on or imports Lattes-specific behavior.
