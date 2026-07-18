# Deterministic scoring policy

## Policy summary

Score version `2.0.0` computes a `0.0`–`100.0` match score from validated `ResumeProfile` and `JobProfile` evidence. No LLM assigns, adjusts, or interprets the numeric result.

```text
active_weight = sum(base_weight[d] for each applicable dimension d)
effective_weight[d] = base_weight[d] / active_weight
overall = round(sum(raw_score[d] * effective_weight[d]), 1)
```

The table below defines base weights. A dimension is applicable only when the extracted job contains its corresponding criterion. Omitted dimensions receive raw score `0`, effective weight `0`, and no contribution. The remaining base weights are renormalized to sum to `1.0`, preventing unspecified criteria from inflating the result. If every dimension is omitted, the overall score is `0` with an insufficient-criteria explanation.

Each applicable dimension is a percentage from `0` to `100`. Raw dimension scores and weighted contributions are rounded independently to two decimal places in the response; the final sum of those weighted contributions is rounded to one decimal place. Because the weighted value is calculated from the internal score before its display rounding, multiplying a displayed raw score by its effective weight can differ from the displayed contribution by `0.01` at a rounding boundary.

| Dimension | Base weight | Applicability | Primary evidence |
|---|---:|---|---|
| Skills | 0.45 | At least one required or preferred skill | Normalized required/preferred job skills and resume skills |
| Experience | 0.25 | Minimum years greater than zero | Extracted total years and stated job minimum |
| Keywords | 0.15 | At least one job keyword | Normalized resume keywords/skills and job keywords |
| Education | 0.10 | Level other than `none` | Ordered extracted education levels |
| Responsibilities | 0.05 | At least one responsibility | Token overlap between resume achievements and job responsibilities |

The source of truth is `src/resume_matcher/domain/matching.py`.

## Normalization

Skills and keyword comparisons are case-insensitive. Normalization:

1. applies Unicode-aware case folding and trims whitespace;
2. replaces `&` with `and`;
3. removes unsupported punctuation while retaining characters useful in technical terms such as `+`, `#`, `.`, `/`, and `-`;
4. collapses repeated whitespace;
5. applies a reviewed alias map—for example `k8s` to `kubernetes`, `postgres` to `postgresql`, and `natural language processing` to `nlp`.

Each skill list is deduplicated by normalized value during contract-to-domain mapping. Display names such as `AWS`, `CI/CD`, and `REST APIs` are retained for explanations.

Normalization is lexical, not ontological. The policy does not infer that one technology is a substitute for another or that a broad category proves a specific skill.

## Dimension formulas

### Skills — 45%

Let:

- `R` be the set of normalized required skills;
- `P` be the set of normalized preferred skills;
- `S` be the set of normalized resume skills;
- `coverage(A) = |A intersect S| / |A| * 100`.

An empty required or preferred subset is neutral inside the skills formula. If both subsets are empty, the entire dimension is inapplicable and excluded from the overall score.

```text
if R and P: skills = 0.80 * coverage(R) + 0.20 * coverage(P)
if R only:  skills = coverage(R)
if P only:  skills = coverage(P)
if neither: skills is not applicable
```

The response separately reports matched skills, missing required skills, and missing preferred skills. Required criteria receive four times the influence of preferred criteria inside the dimension when both categories are present.

### Experience — 25%

```text
if required_years > 0:
    experience = min(max(resume_years, 0) / required_years, 1) * 100
else:
    experience is not applicable
```

Experience saturates at `100`; extra years do not create bonus points. Extraction contracts constrain both values to `0`–`80` years. The policy does not independently validate whether date ranges support the extracted total.

### Keywords — 15%

Resume evidence is the union of extracted resume keywords and displayed resume skill names, normalized with the same function used for skills. The job keywords are normalized and deduplicated.

```text
keywords = matched_normalized_job_keywords / normalized_job_keywords * 100
```

An empty job-keyword set makes the dimension inapplicable. Keyword matching does not use term frequency, stemming, embeddings, hidden text, or an LLM. Recommendations explicitly discourage keyword stuffing.

### Education — 10%

Education uses this ordered rank:

| Level | Rank |
|---|---:|
| `none` | 0 |
| `high_school` | 1 |
| `associate` | 2 |
| `bachelor` | 3 |
| `master` | 4 |
| `doctorate` | 5 |

If the job has no explicit requirement, the dimension is inapplicable. Otherwise the highest resume level is compared with the required rank:

```text
if attained_rank >= required_rank:
    education = 100
else:
    education = attained_rank / required_rank * 100
```

This ordinal partial-credit policy is intentionally simple. It does not infer equivalency from experience, certifications, field of study, institution, or jurisdiction.

### Responsibilities — 5%

The scorer tokenizes:

- the resume summary plus every experience bullet; and
- every extracted job responsibility.

Tokens are case-folded, must start with a letter, are at least three characters long, and may retain technical punctuation. A small fixed stop-word set is removed. The score is target coverage:

```text
responsibilities = |resume_terms intersect job_terms| / |job_terms| * 100
```

An empty responsibility set makes the dimension inapplicable. The API reports at most the first 12 matched terms for this dimension. This deliberately low-base-weight lexical signal does not claim semantic equivalence.

## Worked example

Assume the extracted evidence yields:

- required skills: Python, FastAPI, Docker; resume matches Python and FastAPI;
- preferred skills: AWS, Kubernetes; resume matches AWS;
- three resume years against a five-year minimum;
- three of four job keywords matched;
- a bachelor's requirement met by a bachelor's degree;
- `40%` responsibility-token coverage.

All five dimensions are applicable in this example, so effective and base weights are identical.

| Dimension | Raw score | Weight | Contribution |
|---|---:|---:|---:|
| Skills | `(66.67 * 0.8) + (50 * 0.2) = 63.34` | 0.45 | 28.50 |
| Experience | 60.00 | 0.25 | 15.00 |
| Keywords | 75.00 | 0.15 | 11.25 |
| Education | 100.00 | 0.10 | 10.00 |
| Responsibilities | 40.00 | 0.05 | 2.00 |
| **Overall** |  |  | **66.8** |

## Explanation and recommendations

Every `ScoreDimension` includes:

- its stable name and weight;
- raw and weighted scores;
- matched and missing evidence where the policy exposes it;
- a calculation-specific explanation.

With multiple enabled dimensions, the top-level explanation names the strongest raw
dimension and the largest weighted improvement opportunity. The latter is the remaining
raw-score gap multiplied by the effective weight, so it reflects the dimension's maximum
possible effect on the overall score. A single enabled dimension receives a dedicated
explanation instead of being described as both strongest and weakest. Deterministic
recommendation rules prioritize:

1. missing required skills and insufficient documented experience as high priority;
2. education gaps and missing preferred skills as medium priority;
3. missing terminology as low priority.

When no explicit criteria can be extracted, the recommendation category is `input_quality`
and asks for a complete job description instead of claiming the available criteria align.

Guidance consistently distinguishes missing resume evidence from an actual missing qualification. It instructs users to add a skill only when supported by real experience.

## Omitted-criteria behavior

When the extractor finds no job criterion for a dimension, policy `2.0.0` reports raw score and weight `0` for that dimension and renormalizes the remaining base weights. For example, if a job contains only skills, skills receive effective weight `1.0`. If no explicit criteria are extracted at all, the result is `0` and explicitly says a meaningful match cannot be calculated. If criteria exist but custom scoring configuration assigns zero weight to every applicable dimension, the result remains `0` but reports the configuration problem separately from missing job input.

This prevents a sparse job description from receiving free points. It does not measure extraction confidence: consumers should still inspect the dimension evidence and distinguish an inapplicable dimension from a verified mismatch. A future confidence or completeness indicator should remain separate from compatibility.

## Versioning policy

`score_version` is persisted with every result. Increase it whenever a change can alter numeric output for the same `ResumeProfile` and `JobProfile`, including:

- weights or required/preferred allocation;
- normalization aliases;
- stop words or tokenization;
- empty-set behavior;
- education ranking;
- rounding or dimension formulas.

Pure wording changes to explanations need not change the numeric version, but prompt or extraction changes require their own evaluation because they may alter the structured evidence supplied to the scorer.

Stored analyses are snapshots and are not recomputed automatically after a policy release. If migration or comparison is required later, retain both the old and new score versions.

## Interpretation limits

- The score measures alignment of extracted resume evidence to extracted job criteria; it does not measure candidate quality or predict hiring outcomes.
- Extraction errors propagate into scoring even though calculation is deterministic.
- Lexical matching can miss legitimate synonyms not present in the alias map.
- Years of experience are a coarse signal and may not represent directly relevant experience.
- Education rank is not a legal or professional equivalency determination.
- The policy has not yet been calibrated against hiring outcomes and should not be used as an automated employment decision system.
- A score should always be shown with its dimension evidence, missing items, policy version, and limitations.

## Testing expectations

At minimum, policy tests should cover:

- exact known-score examples;
- empty required/preferred/keyword/responsibility sets;
- required-only and preferred-only jobs;
- aliases and case-insensitive matching;
- zero and excess experience;
- each education boundary;
- weight validation and custom weight injection;
- deterministic repeated results;
- monotonic behavior when supported matching evidence is added;
- persisted score-version round trips.

See [evaluation.md](evaluation.md) for the broader extraction and optimization evaluation plan.
