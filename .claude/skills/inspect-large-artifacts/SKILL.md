---
name: inspect-large-artifacts
description: "Inspect large benchmark artifacts such as JSONL files, traces, results CSVs, Lattes HTML, parsed JSON, and blocks files without loading them fully into context."
---

# Inspect Large Artifacts

## Purpose

Use this skill when the task involves large ctxbench artifacts.

Large files must be inspected economically. The goal is to extract evidence, not to read entire artifacts into the conversation.

## Trigger examples

Use this skill when the user asks:

- "look at this responses.jsonl"
- "inspect the traces"
- "find failures in this run"
- "check judge disagreement"
- "analyze this large file"
- "find rows for q_sup"
- "inspect results without loading everything"
- "what happened in this trialId?"

## Large artifact types

Treat these as large by default:

- `responses.jsonl`
- `evals.jsonl`
- `judge_votes.jsonl`
- `results.csv`
- `traces/**/*.json`
- `raw.html`
- `clean.html`
- `parsed.json`
- `blocks.json`
- exported notebook data
- provider logs
- model traces

## Required procedure

1. Identify file type, size, and line count.

   ```bash
   ls -lh path/to/file
   wc -l path/to/file
   ```

2. Sample only a few records first.

   JSONL:

   ```bash
   head -n 3 path/to/file.jsonl
   ```

   CSV:

   ```bash
   head -n 5 path/to/file.csv
   ```

   JSON:

   ```bash
   jq 'keys' path/to/file.json
   ```

3. Use targeted filters.

   Examples:

   ```bash
   rg '"trialId":"TRIAL_ID"' responses.jsonl
   rg '"taskId":"q_sup"' responses.jsonl
   rg '"strategy":"mcp"' responses.jsonl
   jq -c 'select(.trialId == "TRIAL_ID")' responses.jsonl
   jq -c 'select(.status != "success")' responses.jsonl
   ```

4. For aggregation, prefer scripts or DuckDB instead of manual inspection.

   Python example:

   ```bash
   python - <<'PY'
   import json
   from collections import Counter

   path = "responses.jsonl"
   c = Counter()

   with open(path, "r", encoding="utf-8") as f:
       for line in f:
           row = json.loads(line)
           c[(row.get("strategy"), row.get("status"))] += 1

   for key, value in sorted(c.items()):
       print(key, value)
   PY
   ```

5. Report the exact commands used.

## Constraints

- Never paste long rows, full traces, or full documents into the final answer.
- Never read an entire large artifact into model context.
- Never use full artifact inspection when a targeted query can answer the question.
- Do not modify artifacts unless explicitly requested.
- Do not regenerate expensive artifacts unless explicitly requested.
- Do not call LLM providers.

## Recommended inspection patterns

### Find failed answers

```bash
jq -c 'select(.status != "success") | {trialId, taskId, model, strategy, format, status, error}' responses.jsonl
```

### Count by strategy and status

```bash
python - <<'PY'
import json
from collections import Counter

c = Counter()
with open("responses.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        c[(r.get("strategy"), r.get("format"), r.get("status"))] += 1

for k, v in sorted(c.items()):
    print(k, v)
PY
```

### Inspect judge disagreement

```bash
python - <<'PY'
import json
from collections import defaultdict, Counter

votes = defaultdict(list)
with open("judge_votes.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        votes[r["trialId"]].append(r)

for run_id, rows in votes.items():
    ratings = [r.get("correctness", {}).get("rating") for r in rows]
    if len(set(ratings)) > 1:
        print(run_id, Counter(ratings))
PY
```

### Inspect a single run

```bash
TRIAL_ID="..."
jq -c --arg id "$TRIAL_ID" 'select(.trialId == $id)' responses.jsonl
jq -c --arg id "$TRIAL_ID" 'select(.trialId == $id)' evals.jsonl
jq -c --arg id "$TRIAL_ID" 'select(.trialId == $id)' judge_votes.jsonl
```

## Output format

Return:

```text
Files inspected
- ...

Commands used
- ...

Relevant findings
- ...

Evidence
- short snippets only

Limitations
- ...

Next recommended query
- ...
```
