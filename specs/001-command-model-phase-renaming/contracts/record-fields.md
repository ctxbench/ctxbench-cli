# Contract: Record Field Names

## Field renames in canonical and derived artifacts

| Legacy field | Target field | Type | Appears in |
|--------------|--------------|------|-----------|
| `runId` | `trialId` | string | `manifest.json`, `trials.jsonl`, `responses.jsonl`, `evals.jsonl`, `judge_votes.jsonl`, `evals-summary.json`, `results.csv` |
| `questionId` | `taskId` | string | same as above |
| `answer` | `response` | string | `responses.jsonl`, `evals.jsonl`, `evals-summary.json`, `results.csv` |

## Writer obligations

- All JSON/JSONL records produced by `ctxbench plan`, `ctxbench execute`,
  `ctxbench eval`, and `ctxbench export` use target field names
  exclusively.
- CSV column headers in `results.csv` use target field names
  (`trialId`, `taskId`, `response`, etc.).
- JSON Schema files under `src/schemas/` declare `properties` and
  `required` using target field names.

## Reader obligations

- All consumers in `ctxbench eval`, `ctxbench export`, and `ctxbench
  status` read only target field names.
- A record missing a target field is treated as malformed; readers
  MUST NOT fall back to a legacy field name.

## Negative contract

Across all public artifacts produced after migration:

- The string `"runId"` does not appear as a JSON object key.
- The string `"questionId"` does not appear as a JSON object key.
- The string `"answer"` does not appear as a JSON object key.
- The CSV header `runId`, `questionId`, or `answer` does not appear in
  `results.csv`.

(These strings MAY appear as substrings of unrelated values, e.g. inside
a free-text `response` field. The contract is about field/column names,
not value content.)

## Verification

```
# After running plan → execute → eval → export against a fixture
jq -r 'keys[]' outputs/demo/trials.jsonl | sort -u
# Expected output includes: trialId, taskId, …  (no runId, no questionId)

jq -r 'keys[]' outputs/demo/responses.jsonl | sort -u
# Expected output includes: trialId, taskId, response, …  (no runId, no questionId, no answer)

head -1 outputs/demo/results.csv
# Expected: trialId,taskId,response,…   (no runId, no questionId, no answer)
```
