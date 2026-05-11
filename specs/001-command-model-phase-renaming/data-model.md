# Phase 1 Data Model: Command Model and Phase Renaming

This is a rename specification, so the "data model" here is the canonical
mapping between legacy and target identifiers across every public surface
governed by the spec. No new entities are introduced; no field shapes
change beyond their names.

## Entity 1: Command

A named CLI entry point that researchers invoke to run a benchmark phase.

| Attribute | Constraint |
|-----------|-----------|
| name | Single canonical token; lowercase; no aliases. |
| phase | One of: plan, execute, eval, export, status. |
| exit code | 0 on success; non-zero on error. |

### Rename mapping

| Legacy | Target | Status |
|--------|--------|--------|
| `copa` (program) | `ctxbench` | Renamed; legacy not installed. |
| `copa query` | `ctxbench execute` | Renamed; legacy command-not-found. |
| `ctxbench query` | (none) | Prohibited token; rejected by argparse. |
| `ctxbench exec` | (none) | Prohibited abbreviation; rejected by argparse. |
| `copa plan` | `ctxbench plan` | Subcommand name preserved; prog renamed. |
| `copa eval` | `ctxbench eval` | Subcommand name preserved; prog renamed. |
| `copa export` | `ctxbench export` | Subcommand name preserved; prog renamed. |
| `copa status` | `ctxbench status` | Subcommand name preserved; prog renamed. |

## Entity 2: Selector

A command-line flag that filters trials.

| Attribute | Constraint |
|-----------|-----------|
| flag | Single canonical name; lowercase; double-dash form. |
| value type | Comma-separated list or single token. |
| exclusion form | `--not-<name>` (e.g., `--not-task`). |

### Rename mapping

| Legacy | Target | Status |
|--------|--------|--------|
| `--question` | `--task` | Renamed; legacy unrecognized. |
| `--not-question` | `--not-task` | Renamed; legacy unrecognized. |
| `--repeat` | `--repetition` | Renamed; legacy unrecognized. |
| `--not-repeat` | `--not-repetition` | Renamed; legacy unrecognized. |
| `--ids` | `--trial-id` | Renamed; legacy unrecognized. |
| `--ids-file` | `--trial-id-file` | Renamed; legacy unrecognized. |

(`--ids-file` is implied by the same `--ids → --trial-id` rename; treating
it as part of the selector contract for consistency.)

## Entity 3: Public Artifact File

A file written by a benchmark phase to the experiment output directory.

| Attribute | Constraint |
|-----------|-----------|
| name | Single canonical filename. |
| location | `outputs/<experimentId>/` |
| format | JSONL or JSON or CSV. |

### Rename mapping

| Legacy | Target | Producer phase | Class |
|--------|--------|----------------|-------|
| `queries.jsonl` | `trials.jsonl` | plan | canonical |
| `answers.jsonl` | `responses.jsonl` | execute | canonical |
| (unchanged) | `manifest.json` | plan | canonical |
| (unchanged) | `evals.jsonl` | eval | canonical |
| (unchanged) | `judge_votes.jsonl` | eval | canonical |
| (unchanged) | `evals-summary.json` | eval | derived |
| (unchanged) | `results.csv` | export | derived |

Trace directory rename (`traces/queries/` → `traces/executions/`) is
**out of scope** for this spec; owned by spec 002.

## Entity 4: Record Field

A field name within a record in a public artifact.

| Attribute | Constraint |
|-----------|-----------|
| name | camelCase with `Id` suffix where applicable. |
| presence | Appears in canonical and derived artifacts as listed. |

### Rename mapping

| Legacy field | Target field | Artifacts where it appears |
|--------------|--------------|----------------------------|
| `runId` | `trialId` | `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `manifest.json`, `evals-summary.json`, `results.csv` |
| `questionId` | `taskId` | `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `manifest.json`, `evals-summary.json`, `results.csv` |
| `answer` | `response` | `responses.jsonl`, `evals.jsonl` (where the evaluated answer is carried), `evals-summary.json`, `results.csv` |

### Validation rules

- After migration, *no public artifact record* contains a key matching
  any legacy field name. Verified by SC-003 (grep).
- Schema files under `src/schemas/` reference only target field names.

## Entity 5: Strategy Label

A string identifying a context-provisioning strategy.

| Attribute | Constraint |
|-----------|-----------|
| value | One of: `inline`, `local_function`, `local_mcp`, `remote_mcp`. |
| presence | Appears in plan files, `manifest.json`, `trials.jsonl`, status output, traces. |

### Rename mapping

| Legacy | Target | Status |
|--------|--------|--------|
| `mcp` | `remote_mcp` | Renamed; legacy rejected with `unknown strategy: mcp`. |
| `inline` | `inline` | Unchanged. |
| `local_function` | `local_function` | Unchanged. |
| `local_mcp` | `local_mcp` | Unchanged. |

### Validation rules

- Strategy resolution in `ai/engine.py` (or strategy registry) rejects
  `mcp` with a non-zero exit and the substring `unknown strategy: mcp`
  in stderr.
- `--strategy mcp` on the CLI is rejected at the strategy-resolution
  step (not at argparse-time) so the error message names the
  strategy, not the flag.

## Cross-entity invariants

1. **No-alias invariant.** For every legacy identifier listed above,
   no code path silently substitutes the target identifier on input.
   Legacy identifiers either produce a recognized error or are ignored
   when encountered as files on disk (FR-008 for artifact files).
2. **Coordinated-rename invariant.** A single change set updates
   writers, readers, schemas, docs, and tests together. There is no
   intermediate state where writers emit target names but readers
   still expect legacy names (or vice versa).
3. **Internal-vs-public boundary.** The Python module under
   `src/copa/` may continue to use `copa` in its package directory and
   internal symbol names. The CLI binary, command names, selectors,
   artifact file names, record field names, and strategy labels are
   public and must use target identifiers.

## State transitions

The migration itself is a one-shot transition:

```
legacy state ──(this change set)──► target state
```

No intermediate state is supported (no-alias invariant). Pre-existing
on-disk artifacts from legacy runs remain in place but are neither read
nor overwritten by post-migration code (FR-008).
