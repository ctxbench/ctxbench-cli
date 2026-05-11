# Feature Specification: Dataset Artifact Model

**Feature Branch**: `chore/architecture-redesign-roadmap` (working branch; this spec does not own a branch)
**Created**: 2026-05-11
**Status**: Draft
**Input**: Define a domain-neutral dataset artifact model so artifacts are identified by **semantic role** and **representation**, not by Lattes-specific filenames.

## Overview

This roadmap-level specification defines a small, domain-neutral vocabulary for the artifacts a dataset package contributes to the benchmark: every artifact is described by a **role** (what the artifact is *for*) and a **representation** (what shape its payload takes), independently of any physical filename, dataset, or domain.

It exists because Specs 003 and 004 explicitly **defer** the artifact role/representation model: Spec 003 §FR-037 and Spec 004 §FR-023 fence off "redesigning artifact roles or representations beyond what the boundary requires." This spec fills that gap with the minimum vocabulary needed to keep `ctxbench-cli` domain-neutral, to let `ctxbench/lattes` describe its existing files (raw HTML, cleaned HTML, parsed JSON, blocks JSON) without leaking those names into the core, and to let a future software-repository dataset describe its artifacts in the same vocabulary.

It does **not** implement any domain, it does **not** migrate Lattes data or files, it does **not** change provider adapters, it does **not** introduce a generic plugin or artifact-taxonomy framework, and it does **not** redefine the artifact contracts themselves (canonical vs derived, identity, version), which remain governed by Spec 002.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Strategies select context artifacts by role, not by filename (Priority: P1)

A researcher composes a strategy that needs "whatever the dataset considers the model-facing representation of an instance." Today the strategy must know that the file is `curriculum.cleaned.html`. After this spec, the strategy asks for **role = context artifact** and an acceptable **representation** (e.g., structured object or text-with-markup) without naming any Lattes file.

**Why this priority**: This is the practical payoff of the spec. Without it, every strategy stays coupled to Lattes filenames and the core cannot be reused across datasets.

**Independent Test**: A reader of the strategy code or strategy descriptor can identify which dataset artifact a strategy will receive without consulting any Lattes-specific filename, and the same descriptor remains valid when the dataset is swapped to a non-Lattes one that exposes the same role.

**Acceptance Scenarios**:

1. **Given** a strategy declares "needs a context artifact in a structured representation," **When** it runs against the Lattes dataset, **Then** the dataset adapter resolves that request to its parsed-JSON payload without the strategy referencing the filename.
2. **Given** the same strategy declaration, **When** it runs against a hypothetical software-repository dataset, **Then** the dataset adapter resolves the request to that domain's structured context artifact (e.g., a code index or selected files manifest) without code changes in the strategy.
3. **Given** a strategy declares "needs a context artifact in a text-with-markup representation," **When** it runs against Lattes, **Then** the dataset adapter resolves the request to its cleaned-HTML payload, never to the raw source HTML.

---

### User Story 2 - Evaluation selects evidence artifacts by role, not by filename (Priority: P1)

A researcher running `ctxbench eval` needs the dataset's authoritative payload for the judge. Today eval reaches into `blocks.json` directly. After this spec, eval asks for **role = evidence artifact** and the dataset adapter returns the appropriate payload — `blocks.json` for Lattes, ground-truth annotations for a code-repository dataset — without eval naming any file.

**Why this priority**: Without this, the judge code is permanently coupled to Lattes filenames, blocking both reuse and a clean evaluation contract.

**Independent Test**: A reader of the evaluation code can confirm it only asks for "the evidence artifact for this task" via the dataset adapter, with no Lattes-specific filename appearing in the eval path.

**Acceptance Scenarios**:

1. **Given** a trial response exists and the dataset is Lattes, **When** eval requests the evidence artifact for the response's task, **Then** the dataset adapter returns the blocks-JSON payload.
2. **Given** the same eval request on a non-Lattes dataset, **When** the adapter returns ground-truth annotations as the evidence artifact, **Then** eval proceeds without code changes.
3. **Given** a dataset where context and evidence share an underlying payload, **When** eval asks for the evidence artifact and a strategy asks for the context artifact, **Then** both succeed and the **role** of each request is recorded distinctly, preserving the role separation from Spec 004.

---

### User Story 3 - The same physical file can carry multiple roles without confusion (Priority: P2)

In Lattes today, parsed JSON sometimes acts as the model-facing context artifact and sometimes as a normalized intermediate. After this spec, the dataset adapter declares — explicitly — which roles a given payload can play, and the core can choose between them by role at request time.

**Why this priority**: Resolves the long-standing ambiguity in Lattes between "parsed JSON as context" and "parsed JSON as normalized form." It is a P2 because it is needed to migrate Lattes cleanly, but P1 stories are usable before the ambiguity is resolved.

**Independent Test**: For any Lattes payload that today plays more than one role, the dataset adapter's role declarations enumerate every role that payload may serve, and core requests by role return the same payload deterministically.

**Acceptance Scenarios**:

1. **Given** the parsed-JSON payload is declared as both *normalized* and *context*, **When** a strategy requests a context artifact in a structured representation, **Then** the parsed JSON is returned.
2. **Given** the same parsed-JSON payload, **When** an upstream step requests the normalized representation of the instance, **Then** the parsed JSON is returned and the role recorded is *normalized*, not *context*.
3. **Given** a request whose role/representation pair matches no declared role of any available payload, **When** the adapter cannot resolve it, **Then** the failure names the requested role and representation and does **not** silently fall back to a different role.

---

### User Story 4 - A future software-repository dataset fits the same model unchanged (Priority: P2)

A researcher prototyping a software-repository dataset must be able to map their inputs (repo snapshot, source files, README, code index, ground-truth labels) to the same five roles defined here, without inventing new role categories and without changes to `ctxbench-cli`.

**Why this priority**: Confirms the model is genuinely domain-neutral. A model that only fits Lattes would defeat the purpose.

**Independent Test**: The spec's role/representation vocabulary describes the software-repository examples in this document (snapshot, source files, README, code index, ground-truth annotations) without inventing a new role or a Lattes-named representation.

**Acceptance Scenarios**:

1. **Given** the software-repository examples in this spec, **When** they are mapped to roles, **Then** each example maps to exactly one of: source, context, evidence, normalized/derived, metadata — with no role left undefined and no example forcing a new role.
2. **Given** a software-repository "code index" payload, **When** the dataset adapter declares it as a context artifact in a structured representation, **Then** any strategy asking for that role/representation pair resolves to the code index without referring to Lattes.

---

### Edge Cases

- **Same physical payload, multiple roles**: The adapter declares all roles a payload can play. Requests are matched by role, and the role is recorded on the request, not on the file.
- **No payload satisfies a requested role/representation pair**: The adapter raises a deterministic resolution error naming the requested role and representation. The core does **not** silently substitute a different role or representation.
- **Filename collision across datasets** (e.g., two datasets both use `data.json`): Roles and representations are declared by the dataset adapter; filenames are not part of the contract and must not be used to disambiguate.
- **A representation has no obvious analogue across domains** (e.g., a Lattes-only quirky markup): The adapter is free to use a domain-appropriate representation, but the representation **name** must be domain-neutral (e.g., "text-with-markup," not "lattes-curriculum-html").
- **Metadata artifact mistaken for a payload**: A metadata artifact (identity, version, provenance) MUST NOT be returned in response to a request for a context, evidence, source, or normalized role.
- **Multiple normalized intermediates for the same instance**: Permitted. The adapter distinguishes them by representation. The core requests a specific representation; it does not enumerate intermediates.

## Requirements *(mandatory)*

### Functional Requirements

#### Vocabulary

- **FR-001**: A **dataset artifact** is a payload that a dataset package contributes to the benchmark for a given instance or task. Every dataset artifact MUST be describable by exactly two domain-neutral attributes: a **role** and a **representation**.
- **FR-002**: An **artifact role** is a semantic category describing *what the artifact is for*. The model defines exactly five roles: **source**, **context**, **evidence**, **normalized/derived**, and **metadata**. No additional roles are introduced by this spec.
- **FR-003**: An **artifact representation** is a domain-neutral descriptor of the *shape* of the payload (e.g., raw markup, text-with-markup, structured object, plain text, tabular, blob, index). Representation names MUST NOT carry dataset-specific terminology.
- **FR-004**: A given payload MAY be associated with multiple roles simultaneously (e.g., parsed JSON declared as both *normalized* and *context*). A given role MAY be served by multiple representations, and a given representation MAY serve multiple roles. The dataset adapter declares which (role, representation) pairs each payload satisfies.
- **FR-005**: **Physical filename is not part of the contract.** Dataset packages MAY use any physical file layout. The benchmark core MUST address artifacts only via (role, representation) — never by filename, file extension, or directory path.

#### Role definitions

- **FR-006**: **Source artifact** — the raw externally provided input from which other artifacts may be derived. Source artifacts are typically **not** the artifact a strategy or judge consumes directly. Examples: Lattes raw HTML; a software-repository snapshot archive.
- **FR-007**: **Context artifact** — the representation a strategy presents to the model under test as its view of the instance. The core requests context artifacts during execution. Examples: Lattes cleaned/minified HTML; Lattes parsed JSON when used as model-facing context; a software-repository README; a curated set of source files; a code index when used as model-facing context.
- **FR-008**: **Evidence artifact** — the representation a judge consumes to evaluate a response. The core requests evidence artifacts during evaluation. Examples: Lattes blocks JSON; ground-truth annotations for a software-repository dataset.
- **FR-009**: **Normalized / derived artifact** — a payload produced deterministically from a source artifact, intended as a stable intermediate. A normalized artifact MAY additionally be declared as a context or evidence artifact when the dataset adapter chooses to expose it in that role. Example: Lattes parsed JSON, which is both the normalized form of the curriculum and (optionally) a context artifact.
- **FR-010**: **Metadata artifact** — a payload that describes other artifacts or the dataset itself (identity, version, provenance, manifest of available roles/representations). Metadata MUST NOT be returned in response to a request for a context, evidence, source, or normalized role.

#### Role distinctions and selection

- **FR-011**: **Context and evidence are role-distinct even when payloads coincide.** When the same underlying payload is declared as both a context artifact and an evidence artifact, the role on the request determines which contract applies. This preserves Spec 004 §FR-009.
- **FR-012**: **Strategies select context artifacts by role and representation.** A strategy MUST declare the (role, representation) pair it needs (where the role is necessarily *context*). The dataset adapter resolves that pair to a payload. Strategies MUST NOT name filenames, formats-as-filenames, or any dataset-specific identifier when selecting artifacts.
- **FR-013**: **Evaluation selects evidence artifacts by role.** The evaluation phase MUST request artifacts as *evidence*, optionally constrained by representation. The dataset adapter resolves that request to a payload. Evaluation MUST NOT name filenames.
- **FR-014**: **Resolution failure is explicit.** If no payload satisfies a requested (role, representation) pair, the dataset adapter MUST raise a deterministic resolution error naming the requested role and representation. The core MUST NOT silently substitute a different role, a different representation, or a default file.
- **FR-015**: **Role recording.** Every artifact access MUST record the role under which the access occurred. When the same payload is accessed under different roles (e.g., parsed JSON as *normalized* in one step and as *context* in another), the recorded role MUST reflect the requesting role, not a single canonical role of the payload.

#### Domain mapping examples (descriptive, not prescriptive)

- **FR-016**: The model MUST be sufficient to describe the existing Lattes artifacts as follows: raw HTML → *source*; cleaned/minified HTML → *context* (representation: text-with-markup); parsed JSON → *normalized/derived* and *context* (representation: structured object); blocks JSON → *evidence* (representation: structured object). The Lattes adapter is responsible for the declaration; this spec does not migrate the files.
- **FR-017**: The model MUST be sufficient to describe a future software-repository dataset as follows: repo snapshot → *source*; selected source files or README → *context*; code index → *context* (when model-facing) or *normalized/derived* (when intermediate); ground-truth annotations → *evidence*. No new role is required to express these mappings.

#### Relation to existing specs

- **FR-018**: This spec governs the **role × representation** model. The **artifact contracts** (canonical vs derived classification, identity, version, provenance, schema) remain governed by Spec 002.
- **FR-019**: This spec is consumed by Spec 003's mandatory dataset-package extension points (context-artifact provider, evidence-artifact provider, artifact location/resolution) and by Spec 004's internal boundary contracts (context-artifact and evidence-artifact provider boundaries). It refines and unblocks the deferral noted in Spec 003 §FR-037 and Spec 004 §FR-023.
- **FR-020**: The vocabulary defined here MUST be reflected in `docs/architecture/vocabulary.md` (terms: dataset artifact, artifact role, artifact representation, source/context/evidence/normalized/metadata roles). This spec does not alter unrelated vocabulary entries.

#### Scope discipline

- **FR-021**: This spec MUST NOT implement any domain (Lattes migration, software-repository domain, or other).
- **FR-022**: This spec MUST NOT migrate Lattes data, rename Lattes files, or change Lattes adapter behavior; it only defines the vocabulary the adapter will eventually use.
- **FR-023**: This spec MUST NOT modify provider adapters, model-provider behavior, or judge-provider behavior.
- **FR-024**: This spec MUST NOT introduce additional roles, sub-roles, or an artifact-taxonomy framework beyond the five roles enumerated in FR-002.
- **FR-025**: This spec MUST NOT introduce a plugin framework, registry mechanism, or dynamic resolution scheme; resolution is the dataset adapter's responsibility, declared statically by that adapter.
- **FR-026**: This spec MUST NOT change CLI commands, phase names, or public terminology established by Spec 001.
- **FR-027**: This spec MUST NOT redefine the artifact contracts (identity, version, canonical vs derived); those remain governed by Spec 002.

### Key Entities

- **Dataset Artifact**: A payload contributed by a dataset package, addressed only by (role, representation).
- **Artifact Role**: One of five domain-neutral categories — source, context, evidence, normalized/derived, metadata — describing what the artifact is for.
- **Artifact Representation**: A domain-neutral descriptor of the payload's shape (e.g., raw markup, text-with-markup, structured object, plain text, tabular, blob, index).
- **Source Artifact**: Raw externally provided input from which other artifacts may be derived.
- **Context Artifact**: Representation presented to the model under test by a strategy.
- **Evidence Artifact**: Representation consumed by the judge during evaluation.
- **Normalized / Derived Artifact**: Deterministically derived intermediate; may additionally serve as a context or evidence artifact when declared so.
- **Metadata Artifact**: Payload describing other artifacts or the dataset itself; never returned for context/evidence/source/normalized requests.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of artifact references in strategy descriptors and in evaluation requests are expressed as (role, representation) pairs, with **zero** references to Lattes-specific filenames in the strategy and evaluation surfaces.
- **SC-002**: Every existing Lattes artifact (raw HTML, cleaned HTML, parsed JSON, blocks JSON) is mappable to a (role, representation) pair drawn from this spec without inventing a new role and without a Lattes-specific representation name.
- **SC-003**: Every software-repository artifact named in this spec (snapshot, source files, README, code index, ground-truth annotations) is mappable to a (role, representation) pair drawn from this spec without inventing a new role.
- **SC-004**: A reviewer reading any strategy descriptor or evaluation entry point can determine which dataset artifact will be requested **without** opening any dataset-specific file or referring to any dataset's source tree.
- **SC-005**: When no payload satisfies a requested (role, representation) pair, the resolution failure is deterministic and names the requested role and representation; the failure is reproducible across runs.
- **SC-006**: The vocabulary defined here is reflected in `docs/architecture/vocabulary.md` and is referenced by Specs 003 and 004 without contradiction.

## Assumptions

- Spec 001's target terminology is in force (`execute`, `trials.jsonl`, `responses.jsonl`, `trialId`, `taskId`, `response`).
- Spec 002 has defined the artifact contracts (identity, version, canonical vs derived) on top of which the role/representation model is layered.
- Spec 003 defines the dataset packaging boundary and the mandatory/optional extension points; this spec is the vocabulary those extension points exchange.
- Spec 004 defines the internal core/adapter boundary, including the role separation between context and evidence artifacts; this spec extends that separation into a full five-role model.
- `ctxbench/lattes` will be the first dataset to declare its payloads in this vocabulary, but the declaration work itself is not part of this spec.
- A future software-repository dataset is expected; this spec is validated by being sufficient to describe it, not by implementing it.

## Dependencies

- **Spec 001 — Command Model and Phase Renaming**: Provides target terminology.
- **Spec 002 — Artifact Contracts**: Provides the underlying artifact-contract surface (identity, version, canonical vs derived) on which roles and representations are layered.
- **Spec 003 — Dataset Distribution**: Defines the dataset package's mandatory and optional extension points; this spec defines the vocabulary they exchange. Resolves the deferral noted in Spec 003 §FR-037.
- **Spec 004 — Domain Architecture Boundaries**: Defines the internal core/adapter boundary including the context/evidence role distinction. Resolves the deferral noted in Spec 004 §FR-023.

## Enables (future specs)

- **Lattes role/representation declaration spec** — concretely declares each existing Lattes payload under the role/representation vocabulary.
- **Software-repository dataset spec** — first non-Lattes dataset to consume the model end-to-end.
- **Strategy descriptor schema spec** — how strategies declare their required (role, representation) pairs.
- **Evaluation artifact-request spec** — how the evaluation phase requests evidence artifacts.

## Affected concepts, artifacts, and docs

- `docs/architecture/vocabulary.md` — add: dataset artifact, artifact role, artifact representation, source/context/evidence/normalized/metadata roles.
- Strategy descriptors / strategy registration surface (definition-only here; schema deferred to a follow-on spec).
- Evaluation phase entry points (definition-only here; schema deferred to a follow-on spec).
- Dataset package extension points referenced from Spec 003 (context-artifact provider, evidence-artifact provider, artifact location/resolution).

## In scope

- Defining the five artifact roles.
- Defining the role/representation pair as the canonical artifact handle.
- Distinguishing physical filename from semantic identity.
- Reaffirming the context vs evidence role separation from Spec 004.
- Specifying how strategies select context artifacts and how evaluation selects evidence artifacts.
- Sufficiency mapping for the Lattes and software-repository examples.

## Out of scope

- Implementing the software-repository domain.
- Migrating Lattes data, renaming Lattes files, or changing Lattes adapter behavior.
- Modifying provider adapters or judge behavior.
- A large or extensible artifact taxonomy (more than the five roles).
- A plugin or dynamic resolution framework.
- Redefining artifact contracts (identity, version, canonical vs derived) — governed by Spec 002.
- Changing CLI commands or public terminology — governed by Spec 001.

## Decisions deferred to planning or follow-on specs

- The concrete schema for a strategy descriptor's (role, representation) declaration.
- The concrete schema for evaluation's artifact request.
- The closed list of representation names (a representation vocabulary is allowed to grow incrementally; this spec only requires names to be domain-neutral).
- How adapters publish a manifest of (role, representation) pairs they support.
- Caching, lifecycle, and on-disk layout of derived artifacts inside a dataset package.
- Interaction between role/representation resolution and dataset versioning (which version of a payload satisfies a request).
- Whether the metadata role decomposes further in later specs (this spec keeps it as a single role).
