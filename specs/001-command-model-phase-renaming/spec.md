# Feature Specification: Command Model and Phase Renaming

**Feature Branch**: `chore/architecture-redesign-roadmap`
**Created**: 2026-05-10
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Benchmark Execution Phase with Target Command (Priority: P1)

A researcher invokes the benchmark execution phase using `ctxbench execute` as the canonical command. The command behaves identically to the prior execution command and produces output artifacts and field names consistent with target terminology.

**Why this priority**: The renamed execution command is the most frequently used benchmark entry point. Any ambiguity or breakage here directly blocks research workflows and invalidates artifact records.

**Independent Test**: Can be fully tested by running `ctxbench execute --help` to confirm the command is registered, and by running the execution phase against a fixture dataset and inspecting output artifacts for target field names and file names.

**Acceptance Scenarios**:

1. **Given** a researcher has a valid plan, **When** they run `ctxbench execute`, **Then** the execution phase completes and produces `trials.jsonl` and `responses.jsonl` with records containing `trialId`, `taskId`, and `response` fields.
2. **Given** a researcher runs `ctxbench exec`, **When** the command is invoked, **Then** the CLI reports an unrecognized command error; no legacy alias exists.
3. **Given** a completed execution, **When** the researcher checks the `remote_mcp` strategy results, **Then** the strategy is labeled `remote_mcp` in all output and artifact metadata; the label `mcp` does not appear.

---

### User Story 2 - Inspect Artifacts Using Target Terminology (Priority: P2)

A researcher reads output artifacts produced by any benchmark phase and encounters only target field names and file names. No legacy names appear in any public artifact.

**Why this priority**: Consistent terminology in artifacts ensures that research reporting and downstream tooling are not confused by mixed naming. Artifacts are the primary evidence record of benchmark runs.

**Independent Test**: Can be fully tested by running the execution and evaluation phases against fixtures and then searching produced artifacts for legacy field names; none should be found.

**Acceptance Scenarios**:

1. **Given** a completed execution phase, **When** the researcher inspects `trials.jsonl`, **Then** every record contains `trialId` and `taskId` fields; `runId` and `questionId` do not appear.
2. **Given** a completed execution phase, **When** the researcher inspects `responses.jsonl`, **Then** every record contains a `response` field; `answer` does not appear.
3. **Given** a benchmark run that used the remote MCP strategy, **When** the researcher inspects any artifact or status output, **Then** the strategy is labeled `remote_mcp`; the label `mcp` does not appear.
4. **Given** a researcher searches the working directory for `queries.jsonl` or `answers.jsonl`, **When** no such files exist, **Then** the correct artifact names are `trials.jsonl` and `responses.jsonl`.

---

### User Story 3 - Understand Compatibility Expectations (Priority: P3)

A researcher migrating from a prior version reads documentation that explicitly states legacy names are not supported and no compatibility aliases are provided. The documentation maps each deprecated term to its replacement.

**Why this priority**: Without an explicit no-compatibility statement, researchers may write scripts against legacy names and encounter silent failures or missing artifacts. Clear documentation prevents this.

**Independent Test**: Can be fully tested by reading the migration documentation and confirming each deprecated term is listed with its replacement and a statement that no alias exists; and by running the CLI help and confirming no legacy command names appear.

**Acceptance Scenarios**:

1. **Given** a researcher reads the migration documentation, **When** they search for `runId`, **Then** the documentation maps it to `trialId` and explicitly states no backward-compatible alias is provided.
2. **Given** a researcher reads the CLI help, **When** they look for `exec`, **Then** the command does not appear; only `execute` is listed under the execution phase.
3. **Given** a researcher reads the strategy documentation, **When** they search for the `mcp` strategy label, **Then** the documentation maps it to `remote_mcp` with an explicit no-alias statement.
4. **Given** a researcher reads the compatibility section, **When** they look for any of the terms `copa`, `query`, `queries.jsonl`, `answers.jsonl`, `runId`, `questionId`, `answer`, `exec`, **Then** each term is listed as deprecated with its target replacement and no alias.

---

### User Story 4 - Tests Reflect Target Terminology (Priority: P4)

All benchmark tests use target command names, artifact names, and field names exclusively. No test fixture, assertion, or helper references legacy terminology.

**Why this priority**: Tests serve as executable documentation. Legacy names in tests create confusion and may mask regressions when output formats or command names are further refined.

**Independent Test**: Can be fully tested by running the benchmark test suite and searching all test files for legacy terms; no occurrences should appear in assertions, fixtures, or helper values.

**Acceptance Scenarios**:

1. **Given** the test suite is executed, **When** all tests pass, **Then** no test file contains `runId`, `questionId`, `answer`, `queries.jsonl`, `answers.jsonl`, or `ctxbench exec` as expected values or fixture field names.
2. **Given** a test for the execution phase, **When** the test inspects produced artifacts, **Then** it asserts on `trialId`, `taskId`, and `response` fields.
3. **Given** a test for strategy labeling, **When** the test checks strategy output, **Then** it asserts on `remote_mcp`, not `mcp`.

---

### Edge Cases

- What happens when a researcher has existing scripts that call `ctxbench exec`? The CLI returns an unrecognized command error; no silent fallback or redirect occurs.
- What happens when an existing artifact file named `queries.jsonl` or `answers.jsonl` is present from a prior run? The benchmark does not read from or produce those files; the researcher is responsible for preserving or discarding legacy artifacts.
- What happens when a plan configuration references the `mcp` strategy label? The label is treated as unrecognized; the researcher must update the plan to use `remote_mcp`.
- What happens when dataset-level identifiers (e.g., `copa`) are used? Dataset and domain naming is out of scope for this change; existing dataset identifiers are unchanged.
- What happens when a researcher provides `ctxbench execute` with the exact same arguments as the prior command? The command accepts the same argument interface and produces equivalent results under target artifact names.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI MUST register `ctxbench execute` as the canonical command for the benchmark execution phase.
- **FR-002**: The CLI MUST NOT register `ctxbench exec` as a command alias, shorthand, or fallback; the legacy spelling is removed with no replacement alias.
- **FR-003**: The `ctxbench plan`, `ctxbench eval`, `ctxbench export`, and `ctxbench status` commands MUST retain their existing names unchanged.
- **FR-004**: All public output artifacts produced by the execution phase MUST be named `trials.jsonl` and `responses.jsonl`; `queries.jsonl` and `answers.jsonl` MUST NOT be produced.
- **FR-005**: All records in `trials.jsonl` MUST use `trialId` as the execution record identifier field; `runId` MUST NOT appear in public artifact output.
- **FR-006**: All records in `trials.jsonl` MUST use `taskId` as the task identifier field; `questionId` MUST NOT appear in public artifact output.
- **FR-007**: All records in `responses.jsonl` MUST use `response` as the field name for the model's output; `answer` MUST NOT appear in public artifact output.
- **FR-008**: When referring to the remote MCP context strategy in CLI output, plan files, status output, and artifact metadata, the label MUST be `remote_mcp`; the label `mcp` MUST NOT be used to identify this strategy.
- **FR-009**: Documentation MUST include a compatibility section that explicitly states the following legacy names have no aliases: `copa`, `query`, `queries.jsonl`, `answers.jsonl`, `runId`, `questionId`, `answer`, `exec`.
- **FR-010**: The test suite MUST NOT contain assertions, fixtures, or helper references that use legacy field names, artifact file names, or command names as expected values.
- **FR-011**: Dataset semantics, dataset identifiers, and domain-specific logic MUST NOT be changed by this renaming.

### Key Entities

- **Command**: A named CLI entry point that a researcher invokes to run a benchmark phase. Each command has a single canonical name; no aliases.
- **Trial**: A single execution record representing one run of the benchmark for a given task. Identified by `trialId` and associated with a `taskId`.
- **Response**: The output produced by a model for a given trial. Stored under the field name `response` in `responses.jsonl`.
- **Strategy**: A named context provisioning approach. Valid labels: `inline`, `local_function`, `local_mcp`, `remote_mcp`. The label `mcp` is not a valid strategy name.
- **Artifact**: A file produced by a benchmark phase that persists results for downstream use. Canonical artifact names for the execution phase: `trials.jsonl`, `responses.jsonl`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five canonical commands (`ctxbench plan`, `ctxbench execute`, `ctxbench eval`, `ctxbench export`, `ctxbench status`) are registered and functional; zero legacy command aliases are registered.
- **SC-002**: 100% of public artifact records produced after migration use target field names; zero occurrences of `runId`, `questionId`, or `answer` appear in newly produced artifacts.
- **SC-003**: 100% of the test suite passes with assertions referencing target terminology; zero occurrences of the 8 deprecated legacy terms appear as expected values in test files.
- **SC-004**: Documentation covers all 8 deprecated terms with their target replacements and an explicit no-alias statement; all prior documentation references to legacy terminology are removed or annotated as migration context only.
- **SC-005**: A researcher can run a complete benchmark workflow using only the current CLI help and documentation without encountering any legacy or mixed terminology in command names, output, or artifacts.

## Assumptions

- The `ctxbench exec` command currently exists and will be removed; no transition alias is needed.
- Existing benchmark artifacts from prior runs that use legacy names are not automatically migrated; researchers with legacy artifacts are responsible for their own preservation or migration.
- The `mcp` label currently appears in plan and status output as the remote MCP strategy name and will be replaced by `remote_mcp` in all new artifacts and documentation.
- The scope of "public terminology" covers: CLI command names, artifact file names, field names in artifact records, strategy labels in plan and status output, and user-facing documentation. Internal implementation identifiers are not in scope for this specification.
- Dataset identifiers such as `copa` are preserved unchanged; only command-level, phase-level, artifact-level, and field-level terminology is in scope.
- The test suite currently contains references to legacy terminology that must be updated as part of this change.
