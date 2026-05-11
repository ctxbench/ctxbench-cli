# Feature Specification: Command Model and Phase Renaming

**Feature Branch**: `chore/architecture-redesign-roadmap`
**Created**: 2026-05-10
**Status**: Draft

## Overview

This specification defines the public-terminology migration from the legacy
`copa` vocabulary to the target `ctxbench` vocabulary established in
`docs/architecture/README.md` §Migration summary. It governs the names that
appear in CLI commands, CLI selectors, public artifact file names, public
record field names, strategy labels, and user-facing documentation.

This is **spec 001** in the roadmap group. Specs 002–006 already cite its
terminology as a prerequisite, so its contract must be stable, testable, and
free of compatibility aliases.

## Change Classification

Per the constitution's *Specification and Planning Governance* section, this
change is classified as **intentionally breaking**.

- Writers (planner, executor, evaluator, exporter, status reporter) MUST emit
  only target names.
- Readers MUST NOT consume legacy names; legacy artifacts and legacy CLI
  invocations result in clear errors.
- No compatibility aliases (commands, selectors, file names, field names, or
  strategy labels) exist in the post-migration state.
- Migration of pre-existing user artifacts is the researcher's responsibility;
  this change ships no migration tooling.

Existing references in the architecture documentation that imply read-side
tolerance for legacy artifacts (e.g., `docs/architecture/README.md` §Migration
summary closing note, `docs/architecture/vocabulary.md` §Compatibility alias,
`docs/architecture/cli-architecture.md` §Compatibility aliases) MUST be
updated in the same change set to match this classification.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Benchmark Execution Phase with Target Command (Priority: P1)

A researcher invokes the benchmark execution phase using `ctxbench execute` as
the canonical command. The command behaves identically to the prior `copa
query` command and produces output artifacts and field names that use target
terminology exclusively.

**Why this priority**: The renamed execution command is the most frequently used
benchmark entry point. Any ambiguity or breakage here directly blocks research
workflows and invalidates artifact records.

**Independent Test**: Run `ctxbench --help` and confirm `execute` is the
listed execution-phase command and `copa` / `query` / `exec` are not. Run the
execution phase against a fixture plan and confirm output artifacts use target
file names and target field names.

**Acceptance Scenarios**:

1. **Given** a researcher has a valid plan produced by `ctxbench plan`,
   **When** they run `ctxbench execute`,
   **Then** the execution phase completes and produces `trials.jsonl` and
   `responses.jsonl` in the experiment output directory; every record contains
   `trialId`, `taskId`, and `response` fields.
2. **Given** a researcher invokes `copa query`,
   **When** the command is dispatched,
   **Then** the shell reports `copa: command not found` (or the platform
   equivalent) because no `copa` entry point is installed.
3. **Given** a researcher invokes `ctxbench exec` or `ctxbench query`,
   **When** the command is parsed,
   **Then** the CLI exits with a non-zero status and stderr contains an
   `argparse`-style `invalid choice` message that names the offending token
   (`exec` or `query`).
4. **Given** a completed execution that used the remote MCP strategy,
   **When** the researcher inspects strategy labels in any output artifact or
   `ctxbench status` output,
   **Then** the label is `remote_mcp`; the bare label `mcp` does not appear.

---

### User Story 2 - Inspect Artifacts Using Target Terminology (Priority: P2)

A researcher reads output artifacts produced by any benchmark phase and
encounters only target field names and target file names. No legacy names
appear in any public artifact.

**Why this priority**: Consistent terminology in artifacts ensures research
reporting and downstream tooling are not confused by mixed naming. Artifacts
are the primary evidence record of benchmark runs.

**Independent Test**: Run the execution and evaluation phases against
fixtures, then search produced artifacts (`trials.jsonl`, `responses.jsonl`,
`evals.jsonl`, `judge_votes.jsonl`, `manifest.json`, `results.csv`,
`evals-summary.json`) for the deprecated-term list defined in FR-013; zero
occurrences MUST be found.

**Acceptance Scenarios**:

1. **Given** a completed execution phase,
   **When** the researcher inspects `trials.jsonl`,
   **Then** every record contains `trialId` and `taskId`; the strings `runId`
   and `questionId` do not appear in any record.
2. **Given** a completed execution phase,
   **When** the researcher inspects `responses.jsonl`,
   **Then** every record contains a `response` field; the string `answer` does
   not appear as a field name in any record.
3. **Given** a benchmark run that used the remote MCP strategy,
   **When** the researcher inspects `manifest.json`, `trials.jsonl`,
   `responses.jsonl`, or `ctxbench status` output,
   **Then** the strategy is labeled `remote_mcp` in every occurrence; the bare
   label `mcp` does not appear as a strategy value.
4. **Given** a researcher inspects the experiment output directory after a run,
   **When** they list its contents,
   **Then** `queries.jsonl` and `answers.jsonl` are not present; only target
   artifact names are produced.

---

### User Story 3 - Understand Compatibility Expectations (Priority: P3)

A researcher migrating from a prior version reads documentation that explicitly
states legacy names are unsupported and lists each deprecated term with its
target replacement.

**Why this priority**: Without an explicit no-compatibility statement,
researchers may write scripts against legacy names and encounter silent
failures or missing artifacts. Clear documentation prevents this.

**Independent Test**: Read the migration documentation and confirm each entry
in the deprecated-term list (FR-013) appears with its replacement and a
no-alias statement. Run `ctxbench --help` and each subcommand's `--help` and
confirm zero occurrences of any deprecated term.

**Acceptance Scenarios**:

1. **Given** a researcher reads the migration documentation,
   **When** they search for `runId`,
   **Then** the documentation maps `runId` to `trialId` and explicitly states
   no alias is provided.
2. **Given** a researcher reads `ctxbench execute --help`,
   **When** they search for `--question`, `--repeat`, or `--ids`,
   **Then** none of these flags appear; only `--task`, `--repetition`, and
   `--trial-id` are listed.
3. **Given** a researcher reads the strategy documentation,
   **When** they search for the bare `mcp` strategy label,
   **Then** the documentation maps `mcp` to `remote_mcp` with an explicit
   no-alias statement.
4. **Given** a researcher reads the compatibility section,
   **When** they look for any deprecated term in FR-013,
   **Then** each term is listed with its target replacement and a no-alias
   statement.

---

### User Story 4 - Tests Reflect Target Terminology (Priority: P4)

All benchmark tests use target command names, selector names, artifact names,
and field names exclusively. No test assertion, fixture, or helper references
legacy terminology as an expected value.

**Why this priority**: Tests serve as executable documentation. Legacy names
in tests create confusion and may mask regressions when output formats or
command names evolve further.

**Independent Test**: Run the benchmark test suite and search all test files
for the deprecated-term list (FR-013); zero occurrences MUST appear as expected
values, fixture field names, or helper constants. Any remaining occurrences
MUST be inside clearly labeled migration-test fixtures whose purpose is to
verify legacy names produce errors.

**Acceptance Scenarios**:

1. **Given** the test suite executes,
   **When** all tests pass,
   **Then** no production-path test file contains any deprecated term as an
   expected value or fixture field name.
2. **Given** a test for the execution phase,
   **When** the test inspects produced artifacts,
   **Then** it asserts on `trialId`, `taskId`, and `response`.
3. **Given** a test for strategy labeling,
   **When** the test checks strategy output,
   **Then** it asserts on `remote_mcp`, not `mcp`.
4. **Given** a test that verifies legacy-name rejection,
   **When** the test invokes `copa`, `ctxbench query`, `ctxbench exec`,
   `--question`, `--repeat`, or `--ids`,
   **Then** the test asserts the invocation fails with a recognizable error.

---

### Edge Cases

- A researcher invokes `copa` (the legacy program name): the shell reports
  command-not-found; the `ctxbench` entry point is the only installed CLI.
- A researcher invokes `ctxbench query` or `ctxbench exec`: the CLI exits
  non-zero with an `argparse` `invalid choice` error.
- A plan configuration references the `mcp` strategy label: `ctxbench plan`
  aborts with a non-zero exit and an `unknown strategy: mcp` error before
  producing any artifact. `ctxbench execute` produces the same error if a
  hand-crafted `trials.jsonl` carries the `mcp` label.
- An experiment output directory contains pre-existing `queries.jsonl` or
  `answers.jsonl` from a prior run: the benchmark neither reads nor overwrites
  them; the researcher is responsible for archiving or deleting them.
- A researcher passes `--question`, `--repeat`, or `--ids` to any subcommand:
  the CLI exits non-zero with an `unrecognized arguments` error naming the
  offending flag.
- Dataset identifiers (e.g., the `copa` dataset name) appear unchanged in
  dataset metadata; the rename does not touch dataset-level naming.
- A researcher provides `ctxbench execute` with the same selector values (now
  under target flag names) and the same experiment file as a prior `copa
  query` run: the command produces equivalent results under target artifact
  names and target field names.

## Requirements *(mandatory)*

### Functional Requirements

#### Commands

- **FR-001**: The CLI MUST be installed and invocable as `ctxbench`. The
  legacy program name `copa` MUST NOT be installed as an entry point or
  shell alias.
- **FR-002**: The CLI MUST register `ctxbench execute` as the canonical
  command for the benchmark execution phase.
- **FR-003**: The CLI MUST NOT register `ctxbench query`, `ctxbench exec`, or
  any other abbreviation as an alias, shorthand, or fallback for `ctxbench
  execute`.
- **FR-004**: The commands `ctxbench plan`, `ctxbench eval`, `ctxbench export`,
  and `ctxbench status` MUST be registered with these exact names.

#### CLI Selectors

- **FR-005**: The selectors `--task`, `--repetition`, and `--trial-id` MUST be
  the canonical names accepted by every subcommand that supports task-level,
  repetition-level, or trial-level filtering.
- **FR-006**: The selectors `--question`, `--repeat`, and `--ids` MUST NOT be
  registered as aliases or alternatives; invoking any of them MUST cause the
  CLI to exit non-zero with an `unrecognized arguments` error.

#### Artifact File Names

- **FR-007**: The execution phase MUST write artifacts named `trials.jsonl`
  and `responses.jsonl`. The file names `queries.jsonl` and `answers.jsonl`
  MUST NOT be produced by any phase.
- **FR-008**: No phase MUST read from `queries.jsonl` or `answers.jsonl`;
  encountering such a file in the input directory is not an error but is
  ignored.

#### Record Field Names

- **FR-009**: Every record in `trials.jsonl` MUST use `trialId` for the
  execution-record identifier and `taskId` for the task identifier. The field
  names `runId` and `questionId` MUST NOT appear as field names in any record
  in any public artifact (`manifest.json`, `trials.jsonl`, `responses.jsonl`,
  `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, `results.csv`).
- **FR-010**: Every record in `responses.jsonl` MUST use `response` for the
  model output field. The field name `answer` MUST NOT appear as a field name
  in any record in any public artifact.

#### Strategy Labels

- **FR-011**: The remote MCP strategy MUST be labeled `remote_mcp` in CLI
  output, plan files, status output, and artifact metadata. The bare label
  `mcp` MUST NOT be accepted as a strategy value; any plan file or hand-edited
  artifact containing it MUST cause the consuming command to exit non-zero
  with a clear `unknown strategy: mcp` error before producing further output.

#### Documentation Updates

- **FR-012**: The architecture documentation under `docs/architecture/` MUST
  be updated in the same change set to remove every entry that asserts a
  compatibility alias or read-side tolerance for legacy names. At minimum:
  - The "During migration, readers should support old artifacts" note in
    `docs/architecture/README.md` (§Migration summary) MUST be removed or
    relabeled as a historical note that no longer applies.
  - The `questionId` compatibility-alias entry in
    `docs/architecture/vocabulary.md` (§Task) MUST be removed.
  - The selector compatibility-alias table in
    `docs/architecture/cli-architecture.md` (§Common selectors) MUST be
    removed.
- **FR-013**: The user-facing documentation MUST include a compatibility
  section that lists each deprecated term with its target replacement and an
  explicit no-alias statement. The deprecated-term list is:
  `copa` → `ctxbench`,
  `query` → `execute`,
  `exec` (never a canonical name; reserved as a prohibited abbreviation),
  `queries.jsonl` → `trials.jsonl`,
  `answers.jsonl` → `responses.jsonl`,
  `runId` → `trialId`,
  `questionId` → `taskId`,
  `answer` → `response`,
  `--question` → `--task`,
  `--repeat` → `--repetition`,
  `--ids` → `--trial-id`,
  `mcp` (as a strategy label) → `remote_mcp`.

#### Tests

- **FR-014**: The test suite MUST NOT use deprecated terms from FR-013 as
  expected values, fixture field names, or helper constants on the production
  path. Tests that explicitly verify legacy-name rejection (US4 scenario 4)
  are exempt and MUST be clearly labeled as legacy-rejection tests.

#### Scope Discipline

- **FR-015**: Dataset semantics, dataset identifiers, dataset adapters, and
  domain-specific logic MUST NOT be changed by this rename. In particular,
  the dataset identifier `copa` (as the name of a dataset) is preserved.
- **FR-016**: Field-level schemas for canonical and derived artifacts beyond
  the field renames listed in FR-009 and FR-010 MUST NOT be redefined by
  this specification.
- **FR-017**: The rename of `traces/queries/<runId>.json` to
  `traces/executions/<trialId>.json` is OUT OF SCOPE for this specification
  and is owned by **spec 002 (Artifact Contracts)** §FR-007. Spec 001 makes
  no claim about trace directory paths.

### Key Entities

- **Command**: A named CLI entry point a researcher invokes to run a
  benchmark phase. Each command has a single canonical name; no aliases.
- **Selector**: A command-line flag a researcher uses to filter trials by
  attribute. Each selector has a single canonical name; no aliases.
- **Trial**: A single planned experimental execution for a given task.
  Identified by `trialId` and associated with a `taskId`.
- **Response**: The output produced by a model for a given trial. Stored
  under field name `response` in `responses.jsonl`.
- **Strategy**: A named context-provisioning approach. Valid labels:
  `inline`, `local_function`, `local_mcp`, `remote_mcp`. The bare label
  `mcp` is not a valid strategy name.
- **Artifact**: A file produced by a benchmark phase that persists results
  for downstream use. Canonical execution-phase artifacts: `trials.jsonl`,
  `responses.jsonl`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The CLI installs `ctxbench` as the only program entry point;
  invoking `copa` reports command-not-found. The five subcommands `plan`,
  `execute`, `eval`, `export`, `status` are registered; `query` and `exec`
  are not.
- **SC-002**: Invoking `ctxbench execute --help` lists `--task`,
  `--repetition`, and `--trial-id`. The strings `--question`, `--repeat`, and
  `--ids` do not appear in the help output of any subcommand.
- **SC-003**: After running a fixture experiment end-to-end (plan → execute →
  eval → export), grepping the experiment output directory for any
  deprecated term in FR-013 yields zero matches as a field name, file name,
  or strategy value.
- **SC-004**: Running `ctxbench --help` and each subcommand's `--help`
  produces zero occurrences of any deprecated term in FR-013.
- **SC-005**: The test suite passes with assertions referencing only target
  terminology on the production path; legacy-rejection tests pass by
  asserting non-zero exit and a recognizable error message for each legacy
  invocation listed in FR-013.
- **SC-006**: The compatibility section in user-facing documentation lists
  100% of the deprecated terms in FR-013 with their target replacements and
  no-alias statements, and the three architecture-doc compatibility entries
  identified in FR-012 are removed.

## Scope

### In Scope

- CLI program name (`copa` → `ctxbench`).
- CLI subcommand name for the execution phase (`query` → `execute`); names of
  the other four subcommands (`plan`, `eval`, `export`, `status`) are
  preserved.
- CLI selector names (`--question` → `--task`, `--repeat` → `--repetition`,
  `--ids` → `--trial-id`).
- Public artifact file names (`queries.jsonl` → `trials.jsonl`,
  `answers.jsonl` → `responses.jsonl`).
- Public record field names in canonical and derived artifacts (`runId` →
  `trialId`, `questionId` → `taskId`, `answer` → `response`).
- Strategy label for the remote MCP strategy (`mcp` → `remote_mcp`).
- User-facing documentation: README, architecture docs under
  `docs/architecture/`, CLI help text, migration notes.
- Test assertions, fixtures, and helper constants on the production path.

### Out of Scope

- Internal Python package/module names (e.g., `src/copa/...`), internal
  class names, internal variable names, and internal types. These are
  implementation details and are not part of the public terminology
  contract.
- Field-level schema definitions for any artifact beyond the field renames
  listed in FR-009 and FR-010.
- Trace directory rename `traces/queries/` → `traces/executions/`
  (owned by spec 002).
- Dataset identifiers and dataset-level naming (e.g., the `copa` dataset
  retains its identifier).
- Migration tooling that rewrites pre-existing on-disk legacy artifacts.
- File format versioning, validation tooling, or conformance checking.
- Provider adapter behavior, strategy implementation behavior, evaluation
  semantics, and metric provenance taxonomy (owned by spec 002).

## Dependencies and Enables

### Depends On

- **Constitution** (`.specify/memory/constitution.md` v1.2.0):
  - Principle I (Phase Separation) — preserves five named phases.
  - Principle V (Artifact Contracts) — breaking change requires explicit
    classification and migration note, both provided by this spec.
  - Principle VI (Strategy Comparability) — disambiguates `mcp` from
    `local_mcp` by mandating `remote_mcp`.
  - Principle XI (Documentation Fidelity) — requires doc updates in the
    same change set.
  - Principle XII (Simplicity and Research Sufficiency) — no aliases keeps
    the contract surface minimal.
- **Architecture documentation** (`docs/architecture/README.md`
  §Migration summary) — defines the source-of-truth current-to-target
  mapping.

### Enables (Future Specs)

- **Spec 002 (Artifact Contracts)** — adopts terminology from this spec and
  extends it to trace directory naming and metric provenance.
- **Spec 005 (Dataset Artifact Model)** — relies on stable `trial`, `task`,
  `response` vocabulary.
- **Spec 006 (Lattes Dataset Extraction)** — cites this spec for target
  terminology used by the externalized dataset package.

## Assumptions

- The legacy CLI is currently installed as `copa` with `copa query` as the
  execution-phase command and `queries.jsonl` / `answers.jsonl` as
  execution-phase artifacts; the current field names are `runId`,
  `questionId`, and `answer`; the remote MCP strategy is currently labeled
  `mcp`. Reference: `src/copa/cli.py`, `src/copa/benchmark/models.py`,
  `docs/architecture/README.md` §Migration summary.
- Pre-existing experiment output directories from prior runs may contain
  legacy artifacts; researchers are responsible for archiving or deleting
  them. No automated migration is provided.
- "Public terminology" covers exactly the items listed under In Scope above;
  any term not listed is either out of scope or governed by another
  specification.
- No provider-backed commands are executed to author or validate this
  specification.
