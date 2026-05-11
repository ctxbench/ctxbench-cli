# Contract: CLI Commands

## Program

The CLI is installed under the single console-script name `ctxbench`.

- **Source of installation**: `pyproject.toml` → `[project.scripts]` →
  `ctxbench = "copa.cli:main"`.
- **Argparse `prog`**: `ArgumentParser(prog="ctxbench", …)` in
  `src/copa/cli.py`.
- **Help line**: `ctxbench --help` prints `usage: ctxbench …` (literal
  `ctxbench`, not `copa`).
- **Legacy program**: `copa` is not present in `[project.scripts]`. A
  shell `copa` invocation returns `command not found` (or the platform
  equivalent) after `pip install` / `uv pip install`.

## Subcommands

Exactly five subcommands are registered:

| Subcommand | Help summary (short) |
|------------|----------------------|
| `plan` | Expand an experiment into `trials.jsonl`. |
| `execute` | Submit trials to models and collect responses. |
| `eval` | Evaluate responses using judge models. |
| `export` | Build analysis-ready exports. |
| `status` | Report progress and per-trial state. |

### Negative contract

- The token `query` MUST NOT appear as a subcommand or alias.
- The token `exec` MUST NOT appear as a subcommand or alias.
- Invoking either produces a non-zero exit and stderr containing the
  argparse `invalid choice` form, e.g.:

  ```
  usage: ctxbench [-h] {plan,execute,eval,export,status} ...
  ctxbench: error: argument command: invalid choice: 'query' (choose from 'plan', 'execute', 'eval', 'export', 'status')
  ```

## Exit codes

| Condition | Exit code |
|-----------|-----------|
| Success | 0 |
| argparse parse error (unknown subcommand or selector) | 2 |
| Command-level error (e.g., unknown strategy, missing input) | 1 |

(Exit codes follow standard argparse + Python conventions; this contract
fixes only the *kind* of code, not new codes.)

## Help-output cleanliness (SC-004)

`ctxbench --help` and each subcommand's `--help` MUST contain zero
occurrences of any deprecated term from spec FR-013. This includes
short help summaries and long option descriptions.

## Verification

Local (no provider calls):

```
ctxbench --help                                # contains 'plan,execute,eval,export,status'
ctxbench query                                 # exits 2; stderr contains 'invalid choice'
ctxbench exec                                  # exits 2; stderr contains 'invalid choice'
which copa                                     # returns nothing on PATH
```
