# Follow-ups

## T058 - Stale `run` / `experiment` command modules

Decision:
- Keep [`src/copa/commands/run.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/commands/run.py) and [`src/copa/commands/experiment.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/commands/experiment.py) unchanged in this migration slice.

Rationale:
- They are stale command paths outside the current public `ctxbench plan` / `ctxbench execute` / `ctxbench eval` / `ctxbench export` / `ctxbench status` workflow.
- Migrating their artifact-facing terminology now would broaden the change set into legacy command maintenance and test-fixture churn.
- The active spec explicitly allows documenting a removal or follow-up decision instead of migrating them in this task.

Recommended next step:
- Either remove these stale command paths once downstream references are gone, or migrate them in a dedicated cleanup slice with their own focused regression coverage.

## T067 - `outputs_analysis.ipynb` public artifact terminology audit

Decision:
- Keep [`outputs_analysis.ipynb`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/outputs_analysis.ipynb) unchanged in this migration slice.

Rationale:
- The notebook still contains public benchmark artifact fields such as `runId`, `questionId`, and `answer`.
- Updating a large analysis notebook would broaden this task beyond the requested post-migration audit and create noisy JSON churn.
- The active task explicitly allows recording a follow-up instead of forcing the migration here.

Recommended next step:
- Migrate notebook loaders, derived DataFrame columns, and rendered headings from `runId` / `questionId` / `answer` to `trialId` / `taskId` / `response` in a dedicated analysis-doc slice, then re-run the notebook audit.

## T068 - `docs/prompts/spec-kit/**` legacy public terminology audit

Decision:
- Keep the following prompt templates unchanged in this migration slice and track them as explicit follow-ups:
  - [`docs/prompts/spec-kit/strict/create-lightweight-spec.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/prompts/spec-kit/strict/create-lightweight-spec.md)
  - [`docs/prompts/spec-kit/strict/create-artifact-contracts-spec.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/prompts/spec-kit/strict/create-artifact-contracts-spec.md)
  - [`docs/prompts/spec-kit/command-model-spec.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/prompts/spec-kit/command-model-spec.md)

Rationale:
- The strict templates still instruct future specs to discuss legacy artifacts such as `queries.jsonl`, `answers.jsonl`, and `traces/queries/<runId>.json`.
- `command-model-spec.md` still names compatibility aliases during migration and points at the older feature directory name.
- These files are prompt-template assets rather than user-facing benchmark docs, so changing them here would be a separate documentation-maintenance slice.

Recommended next step:
- Update the strict prompt templates so artifact migration language matches the no-alias contract where appropriate.
- Either refresh `command-model-spec.md` to the current feature path and breaking-migration stance or mark it as a historical template with an explicit note.

## T069 - Post-migration grep audit is not yet clean

Decision:
- Keep [`specs/001-command-model-phase-renaming/baseline.after.txt`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/specs/001-command-model-phase-renaming/baseline.after.txt) as the recorded post-migration snapshot and leave `T069` open.

Rationale:
- The scoped grep still reports legacy matches outside the allowed buckets.
- After the post-migration classification audit (2026-05-11), the remaining matches fall into four distinct categories:

  **Permanently allowed — no new task required:**
  - Internal Python attribute names (`runId`, `questionId`, `answer`) on `RunSpec`, `RunResult`, `RunMetadata`, and `AIResult`. The public contract is enforced at the model boundary by validators that reject legacy field names on input and emit only target names on serialization. These internal Python names are not public artifact fields and do not need renaming.
  - `"runId"` / `"questionId"` strings in `event_logger` calls inside [`src/copa/benchmark/evaluation.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/benchmark/evaluation.py). These are phase-log metadata fields, not artifact output keys. They do not appear in `evals.jsonl`, `judge_votes.jsonl`, or any other public artifact.
  - [`tests/test_model_schemas.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_model_schemas.py) tests that exercise the internal model layer (constructing objects with internal attrs, asserting the public serialization rejects legacy names). These are correct as-is and require no change unless the internal field names are renamed.
  - All tests that cite legacy names only to assert their absence or to verify rejection (e.g., `assert "runId" not in row`). These are legacy-rejection tests and must remain.

  **Require a new task — see T070 and T071 below:**
  - Distribution and packaging metadata in `pyproject.toml` and `flake.nix`: in scope per the original plan, not completed. Tracked as T070.
  - Compatibility-reader fallbacks in active command modules: spec violation (`readers MUST NOT consume legacy names`). Tracked as T071.

Recommended next step:
- Close T069 once T070 and T071 are complete and a rerun of the `T001` grep scope produces only the permanently-allowed buckets documented above.

---

## T070 - Distribution and Nix packaging metadata still uses legacy name

Decision:
- Track as a new dedicated task.

Rationale:
- [`pyproject.toml:2`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/pyproject.toml) still declares `name = "copa"`.
- [`flake.nix:61–62`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/flake.nix) still uses `"copa-venv"` and `copa = [ "dev" ]` as the virtual-environment and distribution references.
- These were listed as in-scope deliverables in the original plan (§"Nix packaging migration") but were not completed before the migration slice was closed.
- They are small, low-risk changes bounded to two files.
- Note: `flake.nix:76` (`--add-flags "copa.cli"`) and `pyproject.toml:23` (`copa.cli:main`) reference the internal Python entry module, which is explicitly out of scope and must not change.

Recommended next step:
- In a focused commit, rename `name = "copa"` → `name = "ctxbench"` in `pyproject.toml`, and update the Nix venv/package references in `flake.nix` (lines 61–62) to match. Verify with `nix flake check` or the equivalent local build, then rerun the `T001` grep to confirm these lines no longer appear in the scoped output.

---

## T071 - Compatibility readers in active command modules violate the no-legacy-reads contract

Decision:
- Track as a new dedicated task.

Rationale:
- The spec classifies this change as **intentionally breaking**: "Readers MUST NOT consume legacy names; legacy artifacts and legacy CLI invocations result in clear errors."
- Four active command modules still contain `get("trialId", get("runId", ""))` fallback reads that silently accept artifacts written with the legacy `runId` field:
  - [`src/copa/commands/execute.py:34,47`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/commands/execute.py)
  - [`src/copa/commands/export.py:20`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/commands/export.py)
  - [`src/copa/commands/status.py:12`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/commands/status.py)
  - [`src/copa/commands/eval.py:36`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/commands/eval.py)
- These fallbacks mean the commands silently process legacy artifacts instead of surfacing a clear error. That undermines the no-alias contract and can mask artifact migrations that were not completed.

Recommended next step:
- Replace each `get("trialId", get("runId", ""))` with `get("trialId", "")` (no legacy fallback). Add or extend tests in the relevant test modules to confirm that a JSONL record using `runId` either raises an error or is skipped with a clear diagnostic, depending on the chosen error policy. Rerun the focused `pytest -k cli` and `pytest -k eval` suites to verify no regressions.
