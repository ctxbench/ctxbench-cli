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
- The scoped grep still reports legacy matches outside the allowed buckets of migration docs, explicitly historical docs, and `tests/test_legacy_rejection.py`.
- Remaining scoped matches are concentrated in deferred internal/public-boundary surfaces, including:
  - package and wrapper metadata in [`pyproject.toml`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/pyproject.toml) and [`flake.nix`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/flake.nix)
  - schema and model regression tests in [`tests/test_model_schemas.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_model_schemas.py)
  - internal compatibility readers and serializers under [`src/copa/`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/copa/)
  - production-path tests that still assert absence of legacy names by mentioning those strings directly
- Clearing those matches would require a broader cleanup than this audit-only slice.

Recommended next step:
- Finish the remaining internal compatibility cleanup and schema/test migration, then rerun the exact `T001` grep scope and re-evaluate `baseline.after.txt` against the allowed buckets.
