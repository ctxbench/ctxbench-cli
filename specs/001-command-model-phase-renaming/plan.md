# Implementation Plan: Command Model and Phase Renaming

**Branch**: `feat/command-model` | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-command-model-phase-renaming/spec.md`

## Summary

Migrate the public terminology of the CLI, public artifacts, and user-facing
documentation from the legacy `copa` vocabulary to the target `ctxbench`
vocabulary defined in `docs/architecture/README.md` §Migration summary.
The change is classified **intentionally breaking**: writers emit only target
names, readers reject legacy names, no aliases exist anywhere.

Technical approach: a coordinated rename across (a) the CLI entry point and
subcommand/selector wiring, (b) artifact writer paths, (c) artifact reader
paths in eval/export/status, (d) strategy label validation and provider
adapter checks for native remote MCP, (e) trace labels affected by strategy
names, and (f) user-facing docs and tests. Internal Python package/module
identifiers under `src/copa/` are out of scope and remain unchanged in this
work; the CLI entry re-exports `copa.cli:main` under the new script name
`ctxbench`.

The final delivered state is intentionally breaking and has no public aliases.
Implementation tasks may still be sequenced incrementally as long as each slice
preserves importability and ends with the no-alias public contract.

## Technical Context

**Language/Version**: Python 3.11–3.12 (per `pyproject.toml`).
**Primary Dependencies**: as declared in `pyproject.toml` and `flake.nix`;
this change adds no new runtime dependencies.
**Storage**: JSONL/JSON/CSV files on local disk (experiment output
directories). No database.
**Testing**: pytest with fixtures; no provider-backed tests are added or
required by this change.
**Target Platform**: Linux CLI; portable to macOS/Windows where Python is
available.
**Project Type**: cli (single project under `src/copa/`).
**Performance Goals**: N/A — this is a public-vocabulary rename; no
performance characteristics change.
**Constraints**: Intentionally breaking (no aliases). Writers and readers
must change in lockstep. Internal Python module/package names remain
unchanged (out of scope per spec FR-015 and Scope §). No provider-backed
commands are executed during validation.
**Scale/Scope**: ~50 source files reference legacy terms (per `rg src/`);
4 flat test files under `tests/`; README, architecture docs, prompt templates
as needed; `pyproject.toml`, `flake.nix`, and targeted schema/notebook audits.
All within the `ctxbench-cli` repository.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Lifecycle phases remain explicit and separated.** Spec preserves
  the five phases (plan, execute, eval, export, status); only the
  execution-phase command is renamed.
- [x] **Answer-generation and evaluation costs are not conflated.** No
  cost-tracking code paths change.
- [x] **New or changed metrics define value, unit, lifecycle phase, and
  provenance.** No metrics added or changed.
- [x] **Metric provenance distinguishes reported/measured/derived/
  estimated/unavailable.** No provenance taxonomy changes.
- [x] **Estimated metrics not presented as reported or measured.** N/A.
- [x] **Unavailable metrics represented as unavailable/null, not zero.**
  N/A.
- [x] **Metric comparisons do not mix provenance without labeling.** N/A.
- [x] **New metric metadata minimal and justified.** No metadata added.
- [x] **Canonical and derived artifacts identified.** Spec preserves the
  canonical set (`trials.jsonl`, `responses.jsonl`); only names change.
- [x] **Artifact/schema changes documented as compatible / breaking /
  transitional / experimental.** Spec §Change Classification declares
  **intentionally breaking**.
- [x] **Strategy comparability preserved.** `mcp → remote_mcp` removes an
  ambiguity (local vs remote MCP) per Principle VI; strategies are
  unchanged in number and behavior.
- [x] **Dataset/domain-specific behavior isolated.** Dataset identifiers
  (e.g., the `copa` dataset) are explicitly preserved (FR-015).
- [x] **Provider-specific behavior isolated from strategy orchestration.**
  Provider behavior is unchanged, but provider adapter label checks must be
  updated because native MCP adapters currently branch on the public `mcp`
  strategy label.
- [x] **Architectural boundaries preserved; cycles documented.** No
  cross-boundary dependencies introduced.
- [x] **Provider-backed execution not required for validation.** All
  verification is local: `--help` greps, fixture runs, focused pytest
  selections, and metadata inspection.
- [x] **Documentation impact identified.** Spec FR-012 enumerates the
  architecture docs that must be updated, and FR-013 requires a named
  user-facing Compatibility / Migration section in `README.md`.

**Gate result**: PASS. No violations; Complexity Tracking section empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-command-model-phase-renaming/
├── spec.md                      # Feature specification (already revised)
├── plan.md                      # This file
├── research.md                  # Phase 0 output
├── data-model.md                # Phase 1 output (rename mapping tables)
├── quickstart.md                # Phase 1 output (end-to-end verification)
├── contracts/                   # Phase 1 output
│   ├── cli-commands.md
│   ├── cli-selectors.md
│   ├── artifact-files.md
│   ├── record-fields.md
│   ├── strategy-labels.md
│   └── error-contracts.md
├── checklists/
│   └── requirements.md          # Spec checklist (already updated)
└── tasks.md                     # Phase 2 output (NOT created here)
```

### Source Code (repository root)

```text
ctxbench-cli/
├── pyproject.toml               # Script entry rename: copa → ctxbench
├── flake.nix                    # Nix CLI packaging: venv/package names, symlinkJoin name, bin/copa, add-flags/module wiring, apps.default.program
├── README.md                    # User-facing docs; add Compatibility / Migration section
├── docs/
│   └── architecture/
│       ├── README.md            # Remove read-side-tolerance note (FR-012)
│       ├── vocabulary.md        # Remove `questionId` alias entry (FR-012)
│       └── cli-architecture.md  # Remove selector alias table (FR-012)
├── src/copa/                    # Internal package — name UNCHANGED (out of scope)
│   ├── cli.py                   # prog name, subcommand wiring, selectors, help strings, user-facing errors
│   ├── commands/
│   │   ├── execute.py           # Canonical execution command module, renamed from query.py
│   │   ├── plan.py
│   │   ├── eval.py
│   │   ├── export.py
│   │   ├── status.py
│   │   ├── run.py               # Legacy/stale execution module; audit or remove from public path
│   │   └── experiment.py        # Legacy/stale expansion module; audit or remove from public path
│   ├── benchmark/
│   │   ├── models.py            # RunSpec/RunResult/RunMetadata/eval model field renames
│   │   ├── paths.py             # Artifact file-name constants
│   │   ├── selectors.py         # Selector field name → taskId
│   │   ├── executor.py          # Read/write target file names + fields
│   │   ├── evaluation.py        # Read trials.jsonl / responses.jsonl
│   │   ├── results.py           # Export uses target field names
│   │   └── …
│   ├── ai/
│   │   ├── engine.py            # Strategy registry: remote_mcp, not mcp
│   │   ├── trace.py             # Strategy span names/metric aggregation labels
│   │   ├── models/
│   │   │   ├── openai.py        # Native remote MCP branch checks
│   │   │   ├── claude.py        # Native remote MCP branch checks
│   │   │   └── gemini.py        # Native remote MCP branch checks
│   │   ├── strategies/
│   │   │   ├── mcp.py           # File can stay; strategy label registration uses remote_mcp
│   │   │   └── …
│   │   └── …
│   └── util/
│       └── artifacts.py         # File-name helpers
└── tests/
    ├── test_cli.py              # CLI invocation, artifact, selector, eval/export flows
    ├── test_ai.py               # engine/provider/strategy behavior
    ├── test_eval_status_regression.py
    └── test_lattes_sections.py
```

**Structure Decision**: Single CLI project. Source under `src/copa/`
remains in place (internal module names are out of scope). All file edits
are targeted; no package directory rename is required. The canonical public
CLI entry point script is renamed to `ctxbench` in both `pyproject.toml`
and `flake.nix`. The canonical execution command module is `execute.py`,
renamed from `query.py`. Stale modules such as `run.py` and `experiment.py`
are not part of the current parser surface, but they must be audited during
implementation because they still contain legacy artifact names and may affect
tests, imports, or documentation. Because this spec is intentionally breaking,
legacy public entry points such as `copa` and `query` are not installed or
exposed as aliases unless the specification is explicitly amended.

## Required Implementation Deliverables

### Nix packaging migration

`flake.nix` is in scope for this migration. The Nix workflow MUST expose
`ctxbench` as the canonical public CLI entry point and MUST NOT install
`copa` as a public executable.

The implementation MUST update every Nix location where the legacy CLI name or
legacy entry wiring is encoded, including:

- virtual environment or package names that still expose the legacy CLI name;
- `symlinkJoin` or equivalent package names;
- installed binary paths such as `bin/copa`;
- `add-flags` / wrapper arguments that currently point at legacy CLI wiring;
- the entry module or executable wiring used by the generated wrapper;
- `apps.default.program`.

The resulting Nix app/package behavior must match the Python packaging
behavior: both `nix run` / Nix app execution and editable Python installation
must expose `ctxbench` as the public command.

### CLI help text migration

CLI help text is a public command contract and is explicitly in scope.

The implementation MUST sweep user-facing CLI strings in `src/copa/cli.py` and
related command modules, including:

- command descriptions;
- `help=` arguments;
- metavar names;
- default path descriptions;
- selector descriptions;
- examples embedded in help output;
- user-facing error messages.

Canonical help output such as `ctxbench --help` and command-specific help
output MUST use target terminology, including `execute`, `trials.jsonl`,
`responses.jsonl`, `taskId`, and `trialId`.

Deprecated public terms such as `copa`, `query`, `queries.jsonl`,
`answers.jsonl`, `question id`, `run id`, `answer`, and ambiguous `mcp` MUST
NOT appear in canonical help output, except if an explicitly labeled
Compatibility / Migration section is intentionally shown to users.

### User-facing Compatibility / Migration documentation

The migration MUST add a named user-facing **Compatibility / Migration** section
to `README.md`.

`README.md` is the single required home for this migration notice in this spec. A separate `MIGRATION.md` MUST NOT be introduced by this change unless the specification is amended, to avoid duplicated or divergent user-facing migration content.

This deliverable is required by FR-013 and MUST list all deprecated public
terms and replacements required by the specification. The mandatory FR-013
migration table MUST cover at least these 12 required entries:

| Deprecated FR-013 term | Target |
|---|---|
| `copa` | `ctxbench` |
| `query` | `execute` |
| `exec` | prohibited abbreviation; use `execute` |
| `queries.jsonl` | `trials.jsonl` |
| `answers.jsonl` | `responses.jsonl` |
| `runId` | `trialId` |
| `questionId` | `taskId` |
| `answer` | `response` |
| `mcp` | `remote_mcp` when referring to the remote MCP strategy |
| `--question` | `--task` |
| `--repeat` | `--repetition` |
| `--ids` | `--trial-id` |

The documentation MAY also include helpful additional natural-language or plural
forms, but these additions MUST NOT replace the 12 required FR-013 entries:

| Additional legacy form | Target |
|---|---|
| `queries` | `trials` |
| `answers` | `responses` |
| `run id` | `trial id` |
| `question id` | `task id` |

Because this spec is intentionally breaking, the section MUST also state that
legacy names are documented for migration only and are not installed or accepted
as public aliases unless a later specification explicitly changes that decision.

### Canonical execution command module

The canonical execution command implementation is `execute.py`.

`src/copa/commands/query.py` MUST be renamed to
`src/copa/commands/execute.py`. The plan does not allow an undecided
"rename or keep" branch. Any future legacy `query` compatibility, if later
accepted by an amended specification, must be implemented as a thin wrapper that
delegates to the canonical `execute` command. This plan currently defines no
such alias.

### Record model and serializer migration

Field renaming MUST be handled as a set of explicit model and serializer
changes, not as one broad "dataclass rename" task.

The implementation MUST update all persisted public record producers and
consumers for the target field names:

- `RunSpec`, `RunResult`, `RunMetadata`, evaluation result models, and their
  `model_validate` / `to_persisted_artifact` paths;
- JSONL serializers in `benchmark/results.py`;
- selector matching in `benchmark/selectors.py`;
- execution metadata passed through `benchmark/executor.py`;
- eval aggregation and judge-vote records in `benchmark/evaluation.py` and
  `commands/eval.py`;
- CSV/detail export rows in `commands/export.py`;
- status tallies in `commands/status.py`;
- artifact identity helpers in `util/artifacts.py` and related callers.

Because this spec is intentionally breaking, compatibility parsing of
`runId`, `questionId`, and `answer` MUST be removed from public artifact
readers unless the specification is amended. Internal Python variable names may
remain legacy only when they are not serialized, displayed, or accepted as
public input.

### Strategy label and native remote MCP migration

The public remote MCP strategy label is `remote_mcp`. The bare `mcp` label is
deprecated and MUST NOT be accepted as a strategy factor or engine strategy
name.

This is not only a strategy registry rename. Current provider adapters branch
on `request.strategy_name == "mcp"` or reject non-`mcp` strategy names before
building native MCP payloads. The implementation MUST update native MCP paths
in OpenAI, Claude/Anthropic, and Gemini/Google adapters so behavior is
unchanged for `remote_mcp` and rejected for `mcp`.

Trace span names and metric aggregation logic that currently look for
`strategy.mcp.execute` MUST be updated consistently to the target label without
changing metric meanings or provenance.

### Explicitly out-of-scope trace directory rename

The trace directory rename `traces/queries/` → `traces/executions/` is out of
scope for this specification per FR-017. Implementation tasks MUST NOT rename
trace directories unless the specification is amended. If architecture docs or
contracts mention `traces/executions/`, update them to clearly distinguish
target future architecture from this feature's implemented scope.

### Incremental implementation sequence

The final public state has no aliases, but the work can be implemented and
reviewed incrementally. Tasks SHOULD be ordered so each slice remains
importable and testable:

1. Add or update target-contract tests and fixtures.
2. Rename CLI script, parser `prog`, and `query` command wiring to `execute`.
3. Rename artifact file names from `queries.jsonl` / `answers.jsonl` to
   `trials.jsonl` / `responses.jsonl`.
4. Rename persisted record fields and serializers from `runId` /
   `questionId` / `answer` to `trialId` / `taskId` / `response`.
5. Rename selector fields and CLI flags from `--question`, `--repeat`, and
   `--ids` to `--task`, `--repetition`, and `--trial-id`.
6. Rename the remote MCP strategy label from `mcp` to `remote_mcp`, including
   engine, provider adapter, and trace paths.
7. Update README, architecture docs, prompt templates, schemas, notebooks, and
   packaging validation.

## Validation

Validation must be provider-free and local.

Required validation includes:

- package metadata / script inspection showing `ctxbench` is the public CLI
  entry point and `copa` is not installed as a public entry point;
- Nix app/package inspection showing the exposed executable is `ctxbench`,
  when `nix` is available in the validation environment;
- focused CLI help tests for `ctxbench --help` and command-specific help;
- grep-style assertions that canonical help output does not expose deprecated
  public terms except in explicitly labeled migration documentation;
- tests or fixtures proving writers emit target artifact names;
- tests or fixtures proving readers use target artifact names under the
  intentionally breaking contract;
- tests proving legacy public artifacts and fields are rejected or ignored
  according to the contract:
  - `eval` reads `responses.jsonl`, not `answers.jsonl`;
  - `export` reads `responses.jsonl`, not `answers.jsonl`;
  - `status` counts `trials.jsonl` and `responses.jsonl`, not
    `queries.jsonl` and `answers.jsonl`;
  - public artifact readers reject `runId`, `questionId`, and `answer` where
    `trialId`, `taskId`, and `response` are required;
- strategy-label tests proving:
  - `remote_mcp` executes through the native remote MCP strategy path;
  - `mcp` is rejected in experiment factors and direct engine resolution;
  - `local_mcp` remains distinct and still uses local runtime wiring;
  - OpenAI, Claude/Anthropic, and Gemini/Google native MCP adapters build
    payloads for `remote_mcp`;
- documentation checks confirming the `README.md` Compatibility / Migration section
  exists and lists all 12 FR-013 deprecated terms and replacements, including
  `exec`, `--question`, `--repeat`, and `--ids`.

No validation step may call real model providers or run the full benchmark.
Pre-change inspection may use `python -m copa.cli --help` or parser-level
tests because the `ctxbench` script does not exist yet. Post-change validation
must inspect the installed/script metadata and use `ctxbench` as the public
command. Prefer focused pytest selections first (`-k cli`, `-k plan`,
`-k execute`, `-k eval`, `-k export`, `-k status`, `-k mcp`) before running
the broader suite.

## Known Risks and Follow-up Notes

These risks do not block this plan, but they MUST be visible to task generation,
review, and release-note preparation.

| Risk | Handling in this spec |
|---|---|
| Distribution package name remains `[project].name = "copa"` in `pyproject.toml`; `pip show ctxbench` will not work while the distribution name is unchanged. | This is allowed by the spec because internal/package identity is out of scope. The `README.md` Compatibility / Migration section MUST explicitly mention that the installed command is `ctxbench` while the Python distribution may still be named `copa` during this migration. |
| Internal package path `src/copa/` remains unchanged. Tracebacks, imports, and `python -m copa.cli` may still expose `copa`. | This is allowed by the spec. Document as an internal-name limitation and possible future cleanup, not as a public CLI contract. |
| Provider adapters currently branch on the legacy `mcp` strategy label for native MCP payload construction. | Tasks MUST include OpenAI, Claude/Anthropic, and Gemini/Google adapter updates and tests proving `remote_mcp` preserves native MCP behavior while `mcp` is rejected. |
| Trace span names and metric aggregation currently recognize `strategy.mcp.execute`. | Tasks MUST update trace labels and aggregation checks without changing metric definitions, units, or provenance. |
| Current source still contains stale `run.py` and `experiment.py` modules plus tests/docs using `runs.jsonl`, `results.jsonl`, and `evaluation.jsonl`. | Tasks MUST audit these modules and fixtures. If they are not part of the public parser surface, either update them to avoid stale public terminology or record an explicit removal/follow-up decision. |
| Current tests are flat files, not `tests/cli/` and `tests/benchmark/` packages. | Task generation MUST target the real files (`tests/test_cli.py`, `tests/test_ai.py`, `tests/test_eval_status_regression.py`, `tests/test_lattes_sections.py`) unless the test layout is explicitly refactored. |
| Trace directory rename `traces/queries/` → `traces/executions/` is out of scope for this feature, but some architecture docs already mention `traces/executions/`. | Implementation MUST NOT rename trace directories under this spec. Documentation changes MUST distinguish current implementation scope from future target architecture. |
| `flake.lock` may be invalidated by Nix packaging changes. | Tasks MUST include regenerating or validating `flake.lock` as needed after `flake.nix` changes, and verifying no stale Nix app/package references still expose `copa`. |
| Notebook analysis artifacts such as `outputs_analysis.ipynb` may read `runId`, `questionId`, or `answer` directly. | Tasks MUST include a lightweight audit of notebooks/analysis files for deprecated public fields. If notebooks are not migrated in this spec, the task MUST record an explicit follow-up. |
| `docs/prompts/spec-kit/**` may contain historical prompt templates with legacy terms. | Tasks MUST either update relevant prompt templates or label retained historical templates as historical / do not reuse if they preserve legacy terminology. |
| Schema files under `src/schemas/` may affect external dataset packages once dataset-extension specs land. | Tasks MUST include a targeted schema impact audit. Any broad cross-repository migration must be deferred to the dataset distribution/extension specs unless required for this CLI rename. |
| Contributors with local `copa`-shaped tooling, shell aliases, IDE configs, or CI shims will break after the intentionally breaking rename. | The `README.md` Compatibility / Migration section or release notes MUST surface this as expected migration impact. |
| User-facing migration content could diverge if both `README.md` and `MIGRATION.md` are edited independently. | This plan chooses `README.md` as the single required home for the Compatibility / Migration section. `MIGRATION.md` is out of scope for this spec unless the spec is amended. |


## Complexity Tracking

No constitution violations to track. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                             |
