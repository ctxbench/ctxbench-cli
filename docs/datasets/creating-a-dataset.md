# Creating a Dataset

## Purpose

This guide describes the distribution-facing requirements for a dataset package used by
CTXBench. Spec 003 owns the external distribution contract. Spec 004 owns the internal
core-versus-adapter boundary and is the authoritative source for adapter responsibility
separation.

Reference:

- Spec 003: external dataset distribution, fetch, inspect, resolution, provenance
- Spec 004: internal boundary ownership for instance loading, task loading, context artifacts,
  evidence artifacts, tool providers, and evaluation evidence

## Minimum package layout

The current compatibility path for a local dataset root is:

```text
dataset-root/
  questions.json
  questions.instance.json
  context/
    <instanceId>/
      parsed.json
      blocks.json
      clean.html
```

The dataset root may be used directly by experiments through `dataset.root`, or it may be
distributed as a materialized package referenced by `dataset.id` and `dataset.version`.

## Mandatory extension points

The distribution envelope must provide the capabilities below.

1. Metadata: human-readable dataset metadata such as purpose, domain, intended uses,
   limitations, and pointers to license/citation information.
2. Identity: a stable dataset identity.
3. Version: a stable dataset version.
4. Origin: enough provenance for another researcher to obtain the same dataset.
5. Instance loading: enumerate and resolve dataset instances.
6. Task loading: enumerate and resolve dataset tasks.
7. Artifact resolution: locate the artifacts required by planning, execution, and evaluation.
8. Context artifact provider: supply the artifact a strategy uses for `(instanceId, taskId, strategy, format)`.
9. Evidence artifact provider: supply the evaluation evidence artifact used by the judge path.
10. Format-specific readers: keep format-specific decoding inside the dataset package.
11. Fixture coverage: expose at least one provider-free fixture suitable for conformance tests.

## Optional extension points

Optional capabilities may be exposed when the dataset supports them:

- tool provider
- evaluation helpers
- strategy descriptors

If an optional capability is unavailable, declare it unavailable instead of letting the benchmark
fall back to domain-specific assumptions.

## StrategyDescriptor requirements

When a dataset contributes strategy descriptors, each descriptor must provide all nine fields:

1. `name`
2. `classification`
3. `context_access_mode`
4. `inline_vs_operation`
5. `local_vs_remote`
6. `loop_ownership`
7. `metric_provenance`
8. `observability_limitations`
9. `comparability_implications`

These fields make dataset-contributed strategy behavior explicit and comparable in downstream
analysis.

## Identity and version guidance

Avoid identity/version conflicts:

- keep `datasetId` stable across repackaging of the same dataset line
- change `version` when task sets, instance bindings, or underlying payloads change
- do not publish two different contents under the same `datasetId` + requested version

The local cache treats conflicting provenance for the same `datasetId` + version as an error.

## Archive packaging guidance

Recommended archive forms:

- one top-level directory containing exactly one dataset package manifest
- or one dataset package directly at archive root

The fetch path validates:

- checksum presence via `--sha256` or `--sha256-url`
- checksum correctness before extraction
- archive extraction safety
- exact-one-manifest discovery
- requested identity/version match

Unsafe archive entries are rejected.

## Provider-free validation

Validate the dataset package without real provider calls:

```bash
ctxbench dataset inspect /path/to/dataset-root
```

Or, for a materialized cached dataset:

```bash
ctxbench dataset inspect dataset-id@version
```

What to check:

- identity and version are correct
- the package is conformant
- required capabilities are present
- missing mandatory capabilities are empty

For workflow-level validation, use the provider-free conformance path described in
[quickstart.md](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/specs/003-dataset-distribution/quickstart.md)
and keep fake responders/judges in test-only fixtures.

## Boundary ownership note

Spec 004 owns internal boundary rules. Dataset authors should not push domain-specific concepts
into benchmark-core code, CLI flags, or generic artifact fields. Domain-specific parsing,
representation, tools, and evidence formatting stay inside the dataset adapter/package.
