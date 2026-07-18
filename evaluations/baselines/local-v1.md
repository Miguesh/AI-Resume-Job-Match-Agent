# Synthetic resume-matcher regression benchmark - local baseline

- Dataset version: `1.0.0`
- Dataset license: `CC0-1.0`
- Adapter: `LocalResumeIntelligence`
- Score policy: `2.0.0`
- Matching cases: 5
- Fact-guard cases: 6

## Aggregate metrics

| Metric | Result |
|---|---:|
| Structured contract validity | 100.0% (5/5) |
| Name/title exact match | 100.0% (5/5) |
| Resume skill F1 | 100.0% |
| Required job skill F1 | 100.0% |
| Preferred job skill F1 | 100.0% |
| Required/preferred classification accuracy | 100.0% |
| Score agreement | 100.0% (MAE 0.00) |
| Fact-guard outcome accuracy | 100.0% |

## Case results

| Case | Structured | Resume skills | Job split | Score | Expected | Error |
|---|---:|---|---|---:|---:|---:|
| `backend-strong-match` | pass | 7/7 | pass | 80.6 | 80.6 | 0.0 |
| `ml-partial-match` | pass | 6/6 | pass | 73.9 | 73.9 | 0.0 |
| `platform-punctuation` | pass | 6/6 | pass | 84.1 | 84.1 | 0.0 |
| `prompt-injection-as-data` | pass | 4/4 | pass | 82.5 | 82.5 | 0.0 |
| `frontend-sparse-job` | pass | 5/5 | pass | 70.8 | 70.8 | 0.0 |

## Interpretation

Exact, versioned golden-case agreement measures deterministic regression behavior for the local adapter. Provider quality requires a separate opt-in evaluation run.

This baseline uses synthetic text and deterministic local heuristics. It is a software-regression artifact, not evidence of hiring validity, fairness, or accuracy on real resumes.
