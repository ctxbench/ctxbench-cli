# Contract: Strategy Labels

## Canonical strategy labels

Exactly four labels are valid for the `strategy` field in plan files,
artifacts, and the `--strategy` CLI flag:

| Label | Meaning |
|-------|---------|
| `inline` | Context is inserted directly into the prompt. |
| `local_function` | Local function-call tools, orchestrated by the benchmark. |
| `local_mcp` | Local MCP runtime, orchestrated by the benchmark. |
| `remote_mcp` | Remote MCP server used as a context provider. |

## Negative contract

The bare label `mcp` MUST NOT be accepted anywhere:

- In experiment JSON `strategy` field.
- In `manifest.json` `strategy` field.
- In `trials.jsonl` per-record `strategy` field.
- As the value of `--strategy` on any CLI subcommand.

## Rejection behavior

When `mcp` is encountered as a strategy label, the consuming command MUST:

1. Exit with non-zero status (recommended: exit code 1).
2. Print to stderr a single line that contains the substring
   `unknown strategy: mcp`. The full line MAY include context, e.g.:

   ```
   ctxbench plan: error: unknown strategy: mcp (valid: inline, local_function, local_mcp, remote_mcp)
   ```

3. NOT produce or partially produce any output artifact for the
   offending invocation. If `ctxbench plan` is rejecting, no
   `trials.jsonl` is written. If `ctxbench execute` is rejecting, no
   `responses.jsonl` is appended to.

The rejection MUST occur at the strategy-resolution step (e.g., in
`ai/engine.py` or the strategy registry), not via argparse `choices=`,
so the error message names the strategy rather than the flag.

## Verification

```
echo '{"experimentId":"x","strategies":["mcp"], …}' > bad-experiment.json
ctxbench plan bad-experiment.json
# Expected: exit 1; stderr contains 'unknown strategy: mcp'
ls outputs/x/ 2>/dev/null                  # No trials.jsonl produced
```
