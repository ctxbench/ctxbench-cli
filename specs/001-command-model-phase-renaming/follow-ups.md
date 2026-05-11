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
- The scoped grep still reports matches outside the narrow `T069` allowlist
  ("migration docs, explicitly historical docs, or `tests/test_legacy_rejection.py`").
- After the post-migration classification audit (2026-05-11), the remaining
  matches fall into five buckets:

  **Fix now**
  - Completed on 2026-05-11:
    - active reader fallbacks were removed from
      [`src/ctxbench/commands/execute.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/execute.py),
      [`src/ctxbench/commands/eval.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/eval.py),
      [`src/ctxbench/commands/export.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/export.py),
      and [`src/ctxbench/commands/status.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/status.py);
    - legacy request-metadata aliases were removed from
      [`src/ctxbench/benchmark/executor.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/executor.py),
      [`src/ctxbench/ai/models/base.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/models/base.py),
      and the dependent [`src/ctxbench/ai/models/mock.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/models/mock.py);
    - production-path grep hits were removed from
      [`tests/test_cli.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_cli.py)
      and [`tests/test_eval_status_regression.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_eval_status_regression.py).
  - No unresolved `fix now` bucket remains after this pass.

  **Allowed migration/historical**
  - The user-facing migration table in [`README.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/README.md).
  - Historical migration reference tables in:
    - [`docs/architecture/README.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/architecture/README.md)
    - [`docs/architecture/vocabulary.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/architecture/vocabulary.md)
    - [`docs/architecture/cli-architecture.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/architecture/cli-architecture.md)
  - [`tests/test_legacy_rejection.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_legacy_rejection.py), whose purpose is explicitly to verify rejection of legacy commands, flags, and strategy labels.

  **Allowed internal name**
  - Internal Python attribute names and internal-model validation wiring in:
    - [`src/ctxbench/benchmark/models.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/models.py)
    - [`src/ctxbench/benchmark/runspec_generator.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/runspec_generator.py)
    - [`src/ctxbench/benchmark/results.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/results.py)
    - [`src/ctxbench/benchmark/evaluation.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/evaluation.py)
    - [`src/ctxbench/benchmark/evaluation_batch.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/evaluation_batch.py)
    - [`src/ctxbench/benchmark/selectors.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/benchmark/selectors.py)
    - [`src/ctxbench/util/artifacts.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/util/artifacts.py)
    - [`src/ctxbench/commands/plan.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/plan.py)
    - internal-name portions of [`tests/test_model_schemas.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_model_schemas.py) and [`tests/test_ai.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/tests/test_ai.py)
    These uses are internal object attributes, internal constructor args, or
    assertions that the public serializers reject legacy names. They do not
    change the public artifact schema by themselves.

  **Allowed domain/protocol term**
  - MCP protocol/runtime/tooling references that are not strategy labels:
    - [`src/ctxbench/ai/runtime.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/runtime.py)
    - [`src/ctxbench/ai/trace.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/trace.py)
    - [`src/ctxbench/ai/models/openai.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/models/openai.py)
    - [`src/ctxbench/ai/models/claude.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/models/claude.py)
    - [`src/ctxbench/ai/models/gemini.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/models/gemini.py)
    - [`src/ctxbench/ai/strategies/mcp.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/strategies/mcp.py)
    - [`src/ctxbench/ai/strategies/local_mcp.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/strategies/local_mcp.py)
    - [`src/ctxbench/datasets/lattes/mcp_server.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/datasets/lattes/mcp_server.py)
    - [`src/schemas/runspec.schema.json`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/schemas/runspec.schema.json)
    - [`src/schemas/plan.schema.json`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/schemas/plan.schema.json)
    - [`docs/architecture/component.md`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/docs/architecture/component.md)
    These refer to the MCP protocol, transport names, URL paths, tool payload
    types, or module/component names, not to the deprecated public strategy
    label.
  - Domain-semantic `answer` language in README and AI/evaluation tests, where
    the text refers to the conceptual judged answer rather than the public
    artifact field name.

  **Defer to follow-up**
  - Stale modules outside the current public CLI surface:
    - [`src/ctxbench/commands/run.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/run.py)
    - [`src/ctxbench/commands/experiment.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/commands/experiment.py)
    These were already deferred under T058 and still carry legacy artifact
    terminology because they are not part of the active `ctxbench plan` /
    `execute` / `eval` / `export` / `status` path.
  - Secondary internal logging cleanup such as [`src/ctxbench/ai/rate_control.py`](/home/michel/repos/doutorado/ctxbench/ctxbench-cli/src/ctxbench/ai/rate_control.py), where `questionId` still appears in rate-limit diagnostics. This is not a public artifact contract issue, but it should be cleaned if the request-metadata follow-up is done.

Recommended next step:
- Treat `T069` as still open.
- If the goal is strict task completion under the current grep rule, either
  relocate the remaining non-rejection test references into
  `tests/test_legacy_rejection.py` / explicitly historical files, or narrow the
  grep-based task definition so allowed internal and protocol/domain uses do not
  keep the task open.
- Do not spend effort renaming the permanently-allowed internal or
  protocol/domain uses unless the specification is amended to require a deeper
  internal refactor.
