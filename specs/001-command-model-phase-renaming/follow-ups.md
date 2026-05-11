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
