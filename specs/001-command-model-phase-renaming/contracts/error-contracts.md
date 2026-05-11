# Contract: Error Messages and Exit Codes

This contract fixes the *observable* error behaviors that acceptance
scenarios and tests rely on. Internal exception types are not part of
the contract.

## Legacy command invocation

| Invocation | Exit code | Stderr contains | Producer |
|------------|-----------|-----------------|----------|
| `copa` (any form) | shell-defined (e.g., 127) | `command not found` (shell) | OS shell, after script removal from `[project.scripts]`. |
| `ctxbench query …` | 2 | `argument command: invalid choice: 'query'` | argparse default error. |
| `ctxbench exec …` | 2 | `argument command: invalid choice: 'exec'` | argparse default error. |

## Legacy selector flags

| Invocation | Exit code | Stderr contains | Producer |
|------------|-----------|-----------------|----------|
| `ctxbench <cmd> --question …` | 2 | `unrecognized arguments: --question` | argparse default error. |
| `ctxbench <cmd> --repeat …` | 2 | `unrecognized arguments: --repeat` | argparse default error. |
| `ctxbench <cmd> --ids …` | 2 | `unrecognized arguments: --ids` | argparse default error. |
| `ctxbench <cmd> --ids-file …` | 2 | `unrecognized arguments: --ids-file` | argparse default error. |

## Legacy strategy label

| Invocation | Exit code | Stderr contains | Producer |
|------------|-----------|-----------------|----------|
| `ctxbench plan <exp.json>` where `<exp.json>` contains `"strategy": "mcp"` | 1 | `unknown strategy: mcp` | Strategy-resolution code in `ai/engine.py` or strategy registry. |
| `ctxbench execute` when `trials.jsonl` carries strategy `mcp` | 1 | `unknown strategy: mcp` | Same. |
| `ctxbench eval` when `responses.jsonl` carries strategy `mcp` | 1 | `unknown strategy: mcp` | Same (where eval inspects strategy). |
| `ctxbench --strategy mcp` (any subcommand accepting the flag) | 1 | `unknown strategy: mcp` | Same (NOT argparse `choices=`). |

## Legacy artifact file on disk (no-op behavior, not an error)

A pre-existing `queries.jsonl` or `answers.jsonl` in the output
directory is NOT an error. The corresponding phase:

- Does not read it.
- Does not overwrite it.
- Produces its own target-named artifact alongside (`trials.jsonl`,
  `responses.jsonl`).
- Optionally emits an informational stderr line, but this is not part
  of the contract.

## Stability guarantees

- The substrings listed under "Stderr contains" are part of the
  contract and tests may assert on them.
- The exact wording around those substrings (e.g., the leading
  `ctxbench:` or `usage:` lines) is not part of the contract.
- Exit codes 0/1/2 are part of the contract; other non-zero codes from
  third-party dependencies are not constrained.
