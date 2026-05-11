# Phase 0 Research: Command Model and Phase Renaming

## Scope

The spec (`spec.md`) has no `[NEEDS CLARIFICATION]` markers and declares
its change classification, scope, and dependencies. The Phase 0 research
work is therefore limited to (a) confirming the *current state* the
implementation must rewrite, (b) recording the few implementation
decisions left open by the spec, and (c) capturing best-practice
references for the rename pattern.

## Inventory of legacy usage in the codebase

Confirmed via `rg` on the working tree at branch `feat/command-model`.

### CLI surface (program, subcommands, selectors)

- `src/copa/cli.py:152` — `argparse.ArgumentParser(prog="copa", …)`
- `src/copa/cli.py:175-198` — subcommand `query` registration and dispatch
- `src/copa/cli.py:33,61` — `--question` selector
- `src/copa/cli.py:45,73` — `--repeat` selector
- `src/copa/cli.py:77` — `--ids` selector
- `src/copa/commands/query.py` — execution-command handler
- `pyproject.toml:[project.scripts]` — `copa = "copa.cli:main"`

### Artifact writers

- `src/copa/benchmark/paths.py` — file-name constants for
  `queries.jsonl`, `answers.jsonl`, etc.
- `src/copa/benchmark/executor.py` — writes execution artifacts.
- `src/copa/benchmark/results.py` — writes export artifacts.
- `src/copa/util/artifacts.py` — file-name helpers.

### Artifact readers / consumers

- `src/copa/commands/eval.py:204-207` — reads `answers.jsonl`.
- `src/copa/commands/query.py:179-182` — reads `queries.jsonl`.
- `src/copa/commands/status.py` — reads both.
- `src/copa/commands/export.py` — reads both.

### Record field names

- `src/copa/benchmark/models.py:327, 342, 346, 379, 385, 403-405,
  453-499, 517-532, 565-616, 645-695` — `runId`, `questionId`, `answer`
  fields in dataclasses and JSON I/O.
- `src/schemas/runspec.schema.json`, `src/schemas/plan.schema.json` —
  JSON Schema references to legacy field names.

### Strategy labels

- `src/copa/ai/strategies/mcp.py` — strategy class for remote MCP.
- `src/copa/ai/strategies/local_mcp.py` — already named correctly.
- Strategy registry (likely under `ai/strategies/__init__.py` or a
  factory in `ai/engine.py`) — registers strategy label `mcp` for the
  remote MCP strategy.

### Tests

- 4 test files under `tests/` reference legacy terms (per `rg`). Exact
  list to enumerate in the tasks phase.

### Documentation

- `README.md`
- `docs/architecture/README.md` (migration summary + "readers should
  support old artifacts" sentence — must be removed per FR-012)
- `docs/architecture/vocabulary.md` (`questionId` compatibility alias —
  must be removed)
- `docs/architecture/cli-architecture.md` (selector alias table — must
  be removed)
- `docs/prompts/spec-kit/**` — historical prompt templates; treat as
  migration-historical and leave untouched unless they appear in
  user-facing surfaces.

## Decisions (resolving the implementation gaps the spec leaves open)

### D-1. Distribution name vs CLI script name

- **Decision**: Keep `[project] name = "copa"` in `pyproject.toml`.
  Rename only `[project.scripts]` from `copa = "copa.cli:main"` to
  `ctxbench = "copa.cli:main"`. Remove the old `copa` script entry.
- **Rationale**: The spec's Out of Scope list excludes "internal Python
  package/module names." The distribution name is package metadata, not
  the user-facing CLI program. Many real-world Python tools have a
  different distribution name from their console script. Renaming the
  distribution would force changes to `flake.nix`, `uv.lock`, CI
  caches, and external dependents; the spec does not require it.
- **Alternatives considered**: Rename distribution to `ctxbench` —
  rejected as scope creep with no spec mandate.

### D-2. Source package directory

- **Decision**: Keep `src/copa/` as-is. The internal package import
  path remains `import copa.cli`. Public entry is via the new
  `ctxbench` console script that targets `copa.cli:main`.
- **Rationale**: Spec Out of Scope explicitly lists "Internal Python
  package/module names (e.g., `src/copa/...`)." A package directory
  rename is a much larger refactor with import-path consequences across
  every test and module. The user-facing migration goal is satisfied
  by the script-name change alone.
- **Alternatives considered**: Rename `src/copa/` → `src/ctxbench/` —
  rejected per spec scope; can be tackled in a follow-up if desired.

### D-3. Command-file rename

- **Decision**: Rename `src/copa/commands/query.py` →
  `src/copa/commands/execute.py` *only if* the import sites can be
  updated in the same change set. Otherwise add a new
  `commands/execute.py` that re-exports the handler and remove the old
  file. The exported handler function is renamed from `query_command`
  to `execute_command`.
- **Rationale**: Module file names are partly internal but the
  function/handler name `query_command` shows up in tracebacks and
  developer-facing surfaces; renaming it to `execute_command` keeps
  the implementation consistent with the new CLI surface and avoids
  reader confusion in `cli.py`. This stays within "user-facing"
  developer ergonomics without crossing into a full package rename.
- **Alternatives considered**: Keep `query.py` and `query_command` —
  rejected because the spec's no-alias contract extends to developer-
  visible names that mirror the CLI surface.

### D-4. Subcommand registration helper

- **Decision**: Restructure `cli.py` `_add_selector_args` to register
  only target selectors (`--task`, `--repetition`, `--trial-id`). No
  alias registration. Removed exclusion flags follow the same pattern
  (`--not-task`, `--not-repetition`).
- **Rationale**: Spec FR-006 forbids aliases. argparse will
  automatically reject unknown flags with `unrecognized arguments`,
  satisfying the edge case requirement.

### D-5. Strategy-label rejection error format

- **Decision**: On encountering strategy label `mcp` in a plan file or
  hand-edited artifact, raise an error whose `str(...)` contains
  `unknown strategy: mcp` and exit non-zero. The error is raised at
  the earliest point of strategy resolution (likely in
  `ai/engine.py` or `ai/strategies/__init__.py`).
- **Rationale**: Matches spec edge case wording and gives tests a
  predictable substring to assert on.

### D-6. Test-fixture handling

- **Decision**: Migrate all production-path fixtures to target field
  names and target file names in the same change set. Keep one
  small fixture set under `tests/legacy/` (or marked
  `@pytest.mark.legacy_rejection`) that exercises legacy invocations
  to verify rejection (US4 scenario 4 / FR-014 exemption).
- **Rationale**: FR-014 exempts legacy-rejection tests but requires
  production-path tests to be clean.

### D-7. Schema files

- **Decision**: Update JSON Schema files under `src/schemas/` to
  reference target field names (`trialId`, `taskId`, `response`).
  These are public contract documents and fall under "public terminology."
- **Rationale**: Schemas validate artifacts whose field names are
  changing; out-of-date schemas would either reject valid artifacts
  or accept invalid ones.

### D-8. Manifest field renames

- **Decision**: Apply field renames to `manifest.json` content too if
  any current key uses `runId`, `questionId`, or `answer`. Spec
  FR-009/FR-010 explicitly enumerate `manifest.json` as a covered
  artifact.
- **Rationale**: Spec FR-009 lists `manifest.json` in the no-legacy-
  fields scope.

## Open questions deferred to tasks phase

- Exact enumeration of the 4 test files and the lines that need to
  change — deferred to `/speckit.tasks` since enumeration is a
  task-generation activity, not a design decision.
- Whether to update Jupyter notebook `outputs_analysis.ipynb` —
  considered downstream user content; touch only if it imports
  artifact field names directly.

## Best-practices references (rename patterns)

- **Python argparse**: removing a subcommand simply un-registers it;
  argparse's default error is `argument command: invalid choice: 'X'
  (choose from …)`, which matches the spec's testable acceptance
  scenario format.
- **Console script renames in `pyproject.toml`**: removing the old
  entry under `[project.scripts]` and adding the new one is sufficient;
  `pip install -e .` (or `uv pip install -e .`) regenerates the
  binstub. No code change in the package needed.
- **JSON Schema field renames**: replace `"runId"` with `"trialId"`
  (etc.) in `properties`, `required`, and any `$id`/`title` strings
  that reference the old name. Increment `version` field if present.

## Constitution alignment summary

Principles touched and how:

- **I. Phase Separation** — preserved; only the execution-phase
  command label changes.
- **V. Artifact Contracts** — change classified as intentionally
  breaking; FR-013 provides the migration note required by the
  principle.
- **VI. Strategy Comparability** — disambiguates `mcp` (was used for
  remote MCP) from `local_mcp`; both remain comparable strategies.
- **XI. Documentation Fidelity** — FR-012 enforces same-change-set
  doc updates.
- **XII. Simplicity** — single coordinated rename; no aliases, no
  compatibility shims, no migration tooling.

Phase 0 complete. No outstanding `[NEEDS CLARIFICATION]` markers.
