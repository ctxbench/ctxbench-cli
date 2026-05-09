# Vocabulary

## Core terms

| Term | Meaning |
|---|---|
| `dataset` | Versioned package of benchmark inputs. |
| `instance` | One concrete dataset unit over which tasks are executed. |
| `context artifact` | A representation of an instance used by a strategy. |
| `task` | Unit of work to be performed over an instance. |
| `trial` | One planned experimental execution. |
| `response` | Model output produced by executing a trial. |
| `evaluation` | Assessment of a response. |
| `judge vote` | One individual judge assessment. |
| `trace` | Detailed event record of execution or evaluation. |
| `result` | Derived analysis-ready artifact, usually exported as CSV. |

## Instance

An instance is one dataset unit.

Examples:

| Domain | Instance |
|---|---|
| Lattes | one curriculum |
| PDFs | one document |
| source code | one repository or project |
| traces | one execution trace |
| tickets | one ticket or conversation |
| images | one image or image set |

Recommended field:

```text
instanceId
```

## Task

A task is what the model must do. In Q/A, a task may be a question. In a broader benchmark, a task may be classification, extraction, summarization, ranking, comparison, or tool-mediated analysis.

Recommended field:

```text
taskId
```

Compatibility alias:

```text
questionId
```

## Trial

A trial is one planned experimental execution:

```text
instance × task × model × strategy × format × repetition
```

Recommended field:

```text
trialId
```

## Response

A response is the model output for one executed trial.

Recommended file:

```text
responses.jsonl
```

## Evaluation and judge vote

An evaluation is the aggregate assessment of a response.

A judge vote is one individual assessment from one judge.

Recommended files:

```text
evals.jsonl
judge_votes.jsonl
```

## Naming rules

Use JSON fields with `Id` suffix:

```text
datasetId
experimentId
instanceId
taskId
trialId
modelId
judgeId
```

Use plural file names for JSONL collections:

```text
trials.jsonl
responses.jsonl
evals.jsonl
judge_votes.jsonl
```

## Current-to-target mapping

| Current | Target |
|---|---|
| `query` | `execute` |
| `queries.jsonl` | `trials.jsonl` |
| `answers.jsonl` | `responses.jsonl` |
| `runId` | `trialId` |
| `questionId` | `taskId` |
| `answer` | `response` |
