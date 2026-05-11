# Quickstart: Verify the Command Model and Phase Renaming

This is the **end-to-end verification recipe** for spec 001. It uses no
provider-backed model calls; everything runs against fixtures or
synthetic inputs already present in the repository.

A reviewer should be able to follow this top-to-bottom and confirm
every SC in `spec.md` §Success Criteria.

## Prerequisites

- Working tree at the implementation branch (e.g., `feat/command-model`).
- `pip install -e .` or `uv pip install -e .` after edits to
  `pyproject.toml` to refresh the console script.
- A fixture experiment JSON file under `tests/` or
  `experiment.baseline.json` at repo root. (The repo already ships
  `experiment.baseline.json`.)

## Step 1 — CLI program is `ctxbench`, not `copa`  (SC-001)

```bash
which ctxbench                              # path printed
which copa                                  # nothing printed
ctxbench --help                             # usage line begins with 'ctxbench'
```

Expected: `ctxbench --help` prints a help block whose `usage:` line
starts with `ctxbench` and whose subcommand list is
`{plan,execute,eval,export,status}` in any order.

Then confirm legacy subcommand names are rejected:

```bash
ctxbench query --help            # exits 2; stderr contains 'invalid choice'
ctxbench exec --help             # exits 2; stderr contains 'invalid choice'
```

## Step 2 — Target selectors only  (SC-002)

```bash
ctxbench execute --help | grep -E -- '--task|--repetition|--trial-id'
# Expected: all three present.

ctxbench execute --help | grep -E -- '--question|--repeat|--ids' && echo FAIL || echo OK
# Expected: OK (zero matches).
```

Confirm legacy flags are rejected:

```bash
ctxbench execute --question Q1   # exits 2; stderr 'unrecognized arguments'
ctxbench execute --repeat 0      # exits 2; stderr 'unrecognized arguments'
ctxbench execute --ids T1        # exits 2; stderr 'unrecognized arguments'
```

## Step 3 — Plan emits `trials.jsonl` with target fields

Use a fixture experiment that does **not** require provider calls (e.g.,
the mock-model experiment under `tests/fixtures/` if available; otherwise
construct one that uses only the `mock` model). For this verification we
just need `ctxbench plan`, which is provider-free.

```bash
ctxbench plan experiment.baseline.json --output ./outputs/spec001-verify

ls outputs/spec001-verify/
# Expected to contain: manifest.json, trials.jsonl
# Expected NOT to contain: queries.jsonl

jq -r 'keys[]' outputs/spec001-verify/trials.jsonl | sort -u
# Expected to include: trialId, taskId, …
# Expected to exclude: runId, questionId
```

## Step 4 — Execute emits `responses.jsonl` with target fields

Run against a mock model so no provider is hit:

```bash
ctxbench execute        # picks up trials.jsonl from cwd or --output dir
# (use --model mock or whatever the mock identifier is in the fixture)

ls outputs/spec001-verify/
# Expected to contain: responses.jsonl
# Expected NOT to contain: answers.jsonl

jq -r 'keys[]' outputs/spec001-verify/responses.jsonl | sort -u | head -20
# Expected to include: trialId, taskId, response, …
# Expected to exclude: runId, questionId, answer
```

## Step 5 — Strategy label `remote_mcp`, not `mcp`  (SC-003)

In the same fixture (or one configured for remote MCP), check:

```bash
jq -r '.strategy // empty' outputs/spec001-verify/trials.jsonl | sort -u
# For a remote-MCP trial, the value is 'remote_mcp'. The bare 'mcp' never appears.
```

Provoke a rejection:

```bash
echo '{"experimentId":"bad","strategies":["mcp"], …}' > /tmp/bad-exp.json
ctxbench plan /tmp/bad-exp.json
# Expected: exit 1; stderr contains 'unknown strategy: mcp'
ls outputs/bad/ 2>/dev/null || echo OK     # No artifacts produced
```

## Step 6 — Zero legacy terms in produced artifacts  (SC-003)

```bash
grep -RE 'runId|questionId|"answer"|queries\.jsonl|answers\.jsonl|"mcp"' \
    outputs/spec001-verify/ && echo FAIL || echo OK
# Expected: OK (zero matches).
```

## Step 7 — Zero legacy terms in `--help` output  (SC-004)

```bash
for sub in "" plan execute eval export status; do
    ctxbench $sub --help
done | grep -E 'copa|--question|--repeat|--ids|queries\.jsonl|answers\.jsonl|runId|questionId|\bquery\b' \
    && echo FAIL || echo OK
# Expected: OK (zero matches).
```

## Step 8 — Test suite is green  (SC-005)

```bash
pytest -q
# Expected: all tests pass.
```

Then confirm legacy-rejection tests exist:

```bash
pytest -q -m legacy_rejection
# Expected: at least one test runs and passes.
```

And confirm production-path test files do not assert on legacy terms:

```bash
grep -RnE '\b(runId|questionId|answer|queries\.jsonl|answers\.jsonl)\b' \
    tests/ --include='*.py' \
    | grep -v 'legacy_rejection' \
    | grep -v '# legacy-doc' \
    && echo FAIL || echo OK
# Expected: OK.
```

## Step 9 — Documentation updates  (SC-006)

```bash
grep -nE 'questionId.*alias|--question -> --task|During migration, readers should support' \
    docs/architecture/README.md docs/architecture/vocabulary.md docs/architecture/cli-architecture.md \
    && echo FAIL || echo OK
# Expected: OK (compatibility-alias entries removed per FR-012).

grep -nE 'copa|query|queries\.jsonl|answers\.jsonl|runId|questionId|answer|--question|--repeat|--ids|^mcp$' \
    README.md docs/architecture/*.md \
    | grep -vE '(deprecated|legacy|historical|→|->)' \
    && echo FAIL || echo OK
# Expected: OK (any remaining mentions are explicitly framed as deprecated/legacy/historical).
```

## Summary checklist

- [ ] SC-001: `ctxbench` installed; `copa` not on PATH; five subcommands registered.
- [ ] SC-002: `--task`, `--repetition`, `--trial-id` present; legacy selectors rejected.
- [ ] SC-003: Zero legacy terms in produced artifacts.
- [ ] SC-004: Zero legacy terms in `--help` output across all subcommands.
- [ ] SC-005: Test suite passes; legacy-rejection tests exist and pass.
- [ ] SC-006: Compatibility-alias entries removed from `docs/architecture/`.
