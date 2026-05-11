# Spec: Artifact Contracts

**Branch**: `feat/artifact-contracts`
**Created**: 2026-05-10
**Status**: Draft (roadmap-level)

## Goal

Establish the canonical artifact set, artifact classification (canonical vs. derived), metric provenance taxonomy, and legacy no-alias policy as a stable reference backbone so that follow-on specifications (schemas, instrumentation, export tooling) can plug into consistent terminology without re-deriving it.

## Scope

- Enumerate the canonical artifact set by name, producing phase, and class.
- Classify artifact roles: execution artifacts, evaluation artifacts, analysis-ready exports, traces.
- Define the five-class metric provenance taxonomy.
- Map legacy artifact names to target replacements with an explicit no-alias policy.
- Document migration as the researcher's responsibility.

## Out of Scope

- Field-level schemas for any artifact.
- File format versioning and forward-compatibility policy.
- Validation or conformance tooling.
- Automated migration tooling.
- Dataset semantics and domain-specific logic.
- New strategies, providers, or phases.
- Provider-specific instrumentation details.
- Extensions to the provenance taxonomy (confidence scores, sub-classes).

## Requirements

### Artifact Set

- **FR-001**: The reference MUST enumerate the canonical artifact set, including at minimum: `manifest.json`, `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, `results.csv`, `traces/executions/<trialId>.json`, `traces/evals/<trialId>.json`.
- **FR-002**: Each artifact MUST be labeled with its producing phase (`plan`, `execute`, `eval`, `export`) and its class (`canonical` or `derived`).
- **FR-003**: The reference MUST distinguish four artifact roles: execution artifacts, evaluation artifacts, analysis-ready exports, and traces.
- **FR-004**: `manifest.json` MUST be identified as a plan-phase canonical artifact that records inputs sufficient to reproduce subsequent phases.

### Canonical vs. Derived

- **FR-005**: Canonical artifacts are the authoritative record of a phase; derived artifacts are reproducible from canonical artifacts without re-invoking providers.
- **FR-006**: Analysis-ready exports (`results.csv`, `evals-summary.json`) MUST be classified as derived; regenerating them MUST NOT require re-running execution or evaluation.

### Legacy Artifacts

- **FR-007**: The reference MUST list the following legacy names with their target replacements and an explicit no-alias statement: `queries.jsonl` → `trials.jsonl`, `answers.jsonl` → `responses.jsonl`, `traces/queries/<runId>.json` → `traces/executions/<trialId>.json`.
- **FR-008**: Writers MUST produce only target artifact names; legacy names MUST NOT be written by any phase.
- **FR-009**: Readers MUST NOT consume legacy artifact names; their presence in an input directory is not an error but is silently ignored.
- **FR-010**: Migration is the researcher's responsibility; no automated migration tooling is committed to in this specification.

### Metric Provenance

- **FR-011**: The reference MUST define exactly five provenance classes: `reported`, `measured`, `derived`, `estimated`, `unavailable`.
- **FR-012**: Every metric in a canonical or derived artifact MUST be representable under exactly one provenance class per record.
- **FR-013**: `estimated` MUST NOT be presented as `reported` or `measured`; `unavailable` MUST NOT be recorded as zero unless zero is the observed value.
- **FR-014**: The taxonomy MUST NOT be extended with sub-classes or confidence scores in this specification; extensions require a follow-on spec.

## Acceptance Scenarios

**Artifact classification**

```
Given the artifact-contracts reference,
When a researcher looks up trials.jsonl,
Then it is identified as an execution-phase canonical artifact.

Given the artifact-contracts reference,
When a researcher looks up evals-summary.json,
Then it is identified as an evaluation-phase derived artifact.

Given the artifact-contracts reference,
When a researcher looks up results.csv,
Then it is identified as an analysis-ready export derived from evaluation artifacts.
```

**Metric provenance**

```
Given the artifact-contracts reference,
When a researcher reads the provenance taxonomy,
Then exactly five classes are listed with definitions
and estimated is visibly distinct from reported and measured.

Given a metric that is not available for a given provider or strategy,
When the researcher inspects the artifact record,
Then the metric is labeled unavailable, not recorded as zero.
```

**Legacy no-alias**

```
Given a researcher searches the migration notes for queries.jsonl,
When the entry is found,
Then it is mapped to trials.jsonl with an explicit no-alias statement.

Given a researcher searches the migration notes for answers.jsonl,
When the entry is found,
Then it is mapped to responses.jsonl with an explicit no-alias statement.

Given a researcher searches the migration notes for traces/queries/<runId>.json,
When the entry is found,
Then it is mapped to traces/executions/<trialId>.json with an explicit no-alias statement.
```

**Edge cases**

- A directory containing both legacy and target files: benchmark reads only target files; researcher is responsible for archiving or removing legacy files.
- A new artifact added in a future spec: it MUST declare its phase, class, and metric-provenance commitments before joining the canonical set.
- Provenance depends on provider (reported for one, estimated for another): the label is recorded per record, not globally per metric.
- A trace file is absent for a given `trialId`: any trace-derived metric is labeled `unavailable`; no silent substitution.

## Impact

- **Artifacts**: All artifacts produced by `ctxbench execute`, `ctxbench eval`, and `ctxbench export`.
- **Docs**: References to legacy names (`queries.jsonl`, `answers.jsonl`, `traces/queries/<runId>.json`) in CLI help, README, migration notes, and example scripts.
- **Internal contracts**: Writer paths for per-phase artifacts; reader paths in `eval` and `export` that consume execution artifacts; trace persistence paths.
- **Unaffected**: Dataset definitions, plan-construction logic, provider adapter internals, judge model selection.

## Compatibility / Migration

| Legacy name | Target name | Policy |
|---|---|---|
| `queries.jsonl` | `trials.jsonl` | No alias; no auto-migration |
| `answers.jsonl` | `responses.jsonl` | No alias; no auto-migration |
| `traces/queries/<runId>.json` | `traces/executions/<trialId>.json` | No alias; no auto-migration |

Migration is the researcher's responsibility. The benchmark neither reads nor writes legacy names.

## Validation

- Inspect the artifact-contracts reference: all nine canonical artifacts enumerated with phase and class labels.
- Inspect the reference: exactly five provenance classes defined; no sub-classes.
- Inspect migration notes: all three legacy names mapped with explicit no-alias statements.
- Grep writer paths: no phase emits `queries.jsonl`, `answers.jsonl`, or `traces/queries/`.

## Dependencies

- **Spec 001 — Command Model and Phase Renaming**: this spec adopts the target vocabulary from 001 (`execute`, `trials.jsonl`, `responses.jsonl`, `trialId`, `taskId`). Conflicts are resolved by Spec 001.

### Enables (future specs)

- Per-artifact schema specs (field-level definitions for each canonical artifact).
- Metric instrumentation specs (provenance class capture per provider and strategy).
- Export tooling specs (generation and validation of analysis-ready exports).
- Trace format specs (structure of per-trial execution and evaluation traces).

## Risks

- No field-level schemas defined here; follow-on specs may introduce incompatible choices before the backbone is validated against actual artifact content.
- Provenance taxonomy is fixed at five classes; pressure to add a sixth before a follow-on spec is accepted may produce informal extensions that bypass this contract.

## Open Questions

The following decisions are intentionally deferred to follow-on specifications:

- Where does the artifact-contracts reference document live? (e.g., `docs/artifact-contracts.md`, README section — not specified here.)
- Exact field schemas for each artifact.
- File format version markers and forward-compatibility policy.
- Whether traces are sharded, compressed, or one document per trial.
- Concrete metric set per artifact and provenance class per provider.
- Whether `manifest.json` carries strategy/provider details inline or by reference.
- Validation tooling: what enforces these contracts at write and read time.
- How provenance labels are physically represented in records (per-field suffix, sidecar map, structured envelope).
- Whether any CLI subcommand handles legacy-artifact migration (assumption: external; open to reconsideration).
