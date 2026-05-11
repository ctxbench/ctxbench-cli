# Contract: CLI Selectors

## Canonical selectors

Every subcommand that accepts trial-filtering flags registers exactly the
following names (and no aliases):

| Flag | Value form | Semantics |
|------|-----------|-----------|
| `--task` | `ID[,ID...]`, repeatable | Filter by task identifier. |
| `--repetition` | `N[,N...]`, repeatable | Filter by repetition index. |
| `--trial-id` | `ID[,ID...]` or `-` (stdin) | Filter by explicit trial IDs. |
| `--trial-id-file` | `PATH` | Filter by trial IDs from a file. |
| `--model` | `ID[,ID...]`, repeatable | Filter by model. |
| `--provider` | `NAME[,NAME...]`, repeatable | Filter by provider. |
| `--instance` | `ID[,ID...]`, repeatable | Filter by instance. |
| `--strategy` | `NAME[,NAME...]`, repeatable | Filter by strategy. |
| `--format` | `NAME[,NAME...]`, repeatable | Filter by context format. |
| `--status` | `STATUS[,STATUS...]`, repeatable | Filter by run status (eval/status only). |
| `--judge` | `ID`, repeatable | Select judges (eval only). |

Each selector also has a `--not-<name>` exclusion form, following the
same renaming rule (e.g., `--not-task`, `--not-repetition`).

## Negative contract

The following flags MUST NOT be registered on any subcommand:

| Forbidden flag | Replacement |
|----------------|-------------|
| `--question` | `--task` |
| `--not-question` | `--not-task` |
| `--repeat` | `--repetition` |
| `--not-repeat` | `--not-repetition` |
| `--ids` | `--trial-id` |
| `--ids-file` | `--trial-id-file` |

Invoking any forbidden flag produces a non-zero exit and stderr
containing argparse's `unrecognized arguments` message, e.g.:

```
ctxbench execute: error: unrecognized arguments: --question Q1
```

## Verification

```
ctxbench execute --help                        # zero occurrences of '--question', '--repeat', '--ids'
ctxbench execute --question Q1                 # exits 2; 'unrecognized arguments'
ctxbench execute --repeat 0                    # exits 2; 'unrecognized arguments'
ctxbench execute --ids T1                      # exits 2; 'unrecognized arguments'
```
