# Evaluation strategy

## Release position

The repository has automated unit, integration, contract, end-to-end, and opt-in external-provider tests. It does **not** yet have a statistically meaningful, human-labeled resume/job benchmark, and no claim is made that the score predicts recruiter decisions, ATS ranking, interviews, or employment outcomes.

Coverage and passing tests establish implementation correctness for specified examples; they do not establish extraction accuracy or fairness in real applicant populations. Those require a separate, privacy-reviewed evaluation program.

## Quality model

Evaluation is divided into four boundaries so a failure can be attributed correctly.

| Boundary | Question | Primary methods |
|---|---|---|
| Document ingestion | Did the service safely recover the available text? | Parser fixtures, malformed files, size/page/archive boundaries, export re-read tests |
| Structured extraction | Did the selected adapter represent resume/job facts correctly? | Field-level labeled examples, normalized set precision/recall, provider contract tests |
| Deterministic matching | Did policy `1.0.0` calculate the specified score from those profiles? | Exact-score tests, branch cases, invariants, serialization round trips |
| Optimization | Did rewriting improve relevance without adding or changing facts? | Fact-guard adversarial tests, source-evidence checks, human review rubric |

API, persistence, authentication, headers, and exports form a fifth cross-cutting reliability boundary covered through integration and end-to-end workflows.

## Existing automated evidence

The current suite is organized as follows:

- `tests/unit/`: scoring, recommendations, skill normalization, fact guarding, PDF/DOCX boundaries, local extraction, serialization, exporters, settings, and rate limiting;
- `tests/integration/`: API authentication, trusted hosts, safe error responses, and middleware behavior;
- `tests/contract/`: generated OpenAPI path, summary, and tag expectations;
- `tests/e2e/`: upload → job extraction → score → optimization → JSON/DOCX/PDF export → deletion using local AI and SQLite;
- `tests/external/`: an explicitly enabled OpenAI structured-extraction smoke test.

CI runs Python 3.12 and 3.13 quality jobs, strict mypy, Ruff, non-external pytest coverage, migration lifecycle checks, dependency auditing, and a Docker image build. External OpenAI tests are deliberately excluded from normal CI because they require a secret, consume budget, and can be nondeterministic.

## Running verification

Install locked development dependencies:

```bash
uv sync --all-groups
```

Run the default suite:

```bash
make test
make coverage
```

Useful focused commands:

```bash
make test-unit
make test-integration
uv run pytest tests/contract tests/e2e -m "not external"
uv run pytest tests/unit/test_matching.py -q
```

Run the consolidated local quality checks (GitHub CI additionally exercises migrations, dependency audit, and the Docker build):

```bash
make ci
```

The live OpenAI smoke test is opt-in:

```bash
export RUN_EXTERNAL_TESTS=1
export OPENAI_API_KEY=your-secret-key
export OPENAI_MODEL=your-supported-model
uv run pytest tests/external -m external -q
```

Use a dedicated low-privilege project key and synthetic text. Do not use a real person's resume in provider smoke tests. A live smoke test verifies connectivity and contract compatibility; it is not a quality benchmark.

## Deterministic scoring evaluation

The scorer should meet these hard invariants for any valid profiles:

1. repeated calls with identical profiles return equal results;
2. every raw dimension and the overall score stays within `0`–`100`;
3. the five weights sum to exactly `1` within floating-point tolerance;
4. the persisted `score_version` remains `1.0.0` for the current formulas;
5. adding a supported exact-match skill cannot reduce the skill score, all else equal;
6. experience at or above the requirement scores `100` and never produces bonus points;
7. equal or higher education rank cannot reduce the education score;
8. empty job criteria follow the documented neutral behavior;
9. aliases produce the same result as their canonical skill names;
10. persistence serialization preserves the result without semantic drift.

Exact expected values—not broad ranges—should be asserted for representative cases. Any intended formula change requires a new score version and side-by-side regression results. See [scoring.md](scoring.md).

## Extraction benchmark design

### Dataset

Create a versioned, reviewable benchmark under a future `evaluations/fixtures/` directory. Use synthetic or explicitly licensed/de-identified documents. Never commit real contact details or private resumes.

Each case should contain:

```json
{
  "case_id": "resume-001",
  "language": "en",
  "source_format": "docx",
  "source_variant": "single_column",
  "input_file": "resume-001.docx",
  "expected": {
    "name": "Synthetic Candidate",
    "skills": ["python", "fastapi"],
    "experience_roles": [
      {
        "title": "Software Engineer",
        "company": "Synthetic Co",
        "start_date": "2021-01",
        "end_date": "2024-01"
      }
    ],
    "education_level": "bachelor",
    "total_years_experience": 3.0
  }
}
```

Maintain separate resume and job-description sets. Include:

- PDF and DOCX;
- one- and two-column layouts;
- tables, bullets, headers, and footers;
- absent optional fields;
- aliases, acronyms, and punctuation-heavy technical skills;
- explicit required versus preferred language;
- equivalent-experience wording;
- prompt-like malicious text treated as data;
- long but valid input;
- cases the parser intentionally rejects, such as scans without selectable text.

Record the parser version, AI provider, model, prompt version, and evaluation timestamp with every run.

### Metrics

| Field | Metric | Notes |
|---|---|---|
| Skills and keywords | Micro/macro precision, recall, F1 on normalized sets | Report required and preferred job skills separately. |
| Name, title, company, contact | Exact and normalized exact match | Contact scoring must run only on synthetic data. |
| Experience roles | Entity-level precision/recall | Match a role by normalized title/company before field scoring. |
| Dates | Field accuracy and interval consistency | Track unknown versus hallucinated dates separately. |
| Total years | Mean absolute error plus overstatement rate | Overstatement is more harmful than conservative omission. |
| Education | Level accuracy and entity precision/recall | Do not infer equivalency unless explicitly supported. |
| Required/preferred split | Classification precision/recall | A required criterion mislabeled preferred is a high-cost error. |
| Contract behavior | Valid structured-output rate | Separately count provider failures and schema failures. |

Always report sample count and confidence intervals where meaningful. A single aggregate F1 can hide serious field or format failures.

## Optimization evaluation

Optimization must be assessed for both relevance and factual integrity.

### Automated checks

- No normalized skill appears in the output unless it was in the source profile.
- No new role/company or institution/degree pair appears.
- Identity and contact fields remain unchanged.
- Certifications remain a subset of the source certifications.
- Every recorded `OptimizationChange` includes non-empty source evidence found in raw source text.
- A changed headline or summary has a corresponding change record.
- A changed multiset of experience bullets or experience skills has an experience change record; pure reordering remains allowed.
- Every output conforms to `OptimizedResumeContract` limits.
- DOCX and PDF outputs can be reopened and their text remains searchable.
- Missing required skills do not appear as newly claimed resume skills.

The fact guard is a defense in depth control, not a semantic proof. Current tests exercise unsupported role metadata, education metadata, titles, contact details, certifications, missing/false evidence, and unrecorded headline, summary, and experience-content changes. Further adversarial evaluation should focus on meaning-changing bullet, summary, headline, and metric rewrites that provide real source evidence while drawing an unsupported conclusion. Gaps found by these tests should become deterministic checks where practical.

### Human rubric

Two reviewers should independently score blinded source/job/output triples on a `1`–`5` scale:

| Criterion | Question |
|---|---|
| Factual fidelity | Can every output claim be supported directly by the source? |
| Relevance | Are verified qualifications important to the target job easier to find? |
| Specificity | Does the draft preserve meaningful evidence instead of producing generic prose? |
| Readability | Is the structure concise, grammatical, and easy to scan? |
| Restraint | Does it avoid keyword stuffing, unsupported claims, and misleading certainty? |

Any factual-fidelity score below `5` is a release-blocking case for the tested prompt/model combination. Review disagreements should be adjudicated and retained as benchmark notes.

## Proposed release gates

These are target gates for a future labeled evaluation release, not achieved metrics:

| Gate | Proposed threshold |
|---|---:|
| Valid structured output on supported benchmark inputs | 100% |
| Required-skill precision | ≥ 0.95 |
| Required-skill recall | ≥ 0.90 |
| Unsupported optimized claims after fact guard | 0 |
| Identity/contact mutations | 0 |
| Deterministic score repeatability | 100% |
| Golden score-regression pass rate | 100% |
| Non-external automated tests | 100% pass |
| Branch coverage | ≥ 85% repository gate |

Do not tune thresholds on the test set used for final reporting. Split future examples by source document/job pair to avoid near-duplicate leakage.

## Fairness and employment-use cautions

The application does not ingest protected attributes as score dimensions, but resumes can expose names, locations, education, career gaps, and other proxies. Excluding a field from the formula does not establish fairness.

Before any consequential employment use:

- define the exact human decision supported by the score;
- assess performance across relevant languages, formats, career levels, and job families;
- test for disparate error rates with qualified legal/privacy review;
- preserve explanations and permit correction of extracted evidence;
- prohibit automated rejection based on the score;
- review applicable employment, privacy, and automated-decision laws.

This MVP should be positioned as candidate-controlled resume assistance, not employer-side automated screening.

## Evaluation report template

Every model or prompt evaluation should publish:

1. code commit, score version, prompt version, provider, and model;
2. dataset version, license/provenance, sample counts, and exclusions;
3. parser and extraction metrics by field and document slice;
4. factual-integrity violations and adjudicated examples;
5. latency and token/cost distributions for OpenAI mode;
6. regressions against the previous accepted configuration;
7. known limitations and the release decision.

Until such a report exists, the automated suite is evidence of software behavior only—not evidence of real-world matching validity.
