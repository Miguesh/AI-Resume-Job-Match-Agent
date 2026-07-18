# ADR 0002: Keep numeric matching deterministic and versioned

- Status: Accepted
- Date: 2026-07-13
- Amended: 2026-07-18

## Context

Users need to understand why a resume received a score and what evidence would change it. Asking an LLM for an opaque percentage would make repeated results unstable, complicate tests, mix extraction uncertainty with business policy, and make stored analyses hard to compare.

LLMs are useful for converting unstructured documents into schemas and conservatively rewriting text. They are not required to perform arithmetic over validated evidence.

## Decision

Only `domain/matching.py` may calculate the numeric score. The current policy is version `2.0.0`, with these base weights:

- skills: 45%;
- experience: 25%;
- keywords: 15%;
- education: 10%;
- responsibility-token overlap: 5%.

When required and preferred skill sets are both present, required coverage receives 80% of the skill dimension and preferred coverage 20%. A dimension is applicable only when the job contains its criterion; omitted dimensions receive weight zero and the remaining base weights are renormalized. If no criteria are extracted, the policy returns zero with an insufficient-criteria explanation. This replaced version `1.0.0`, where omitted criteria contributed full-credit points and could inflate sparse jobs.

Each response persists raw and weighted dimension scores, matched and missing evidence, a calculation explanation, recommendations, and `score_version`.

AI adapters may extract `ResumeProfile` and `JobProfile` inputs and generate prose, but their contracts do not include score fields. Stored results are snapshots and are not silently recalculated.

Any code or normalization change that can alter numeric output for identical structured profiles requires a new score version and regression evaluation.

## Consequences

### Positive

- Identical structured evidence produces identical output.
- Every point is attributable to a named dimension and weight.
- Unit tests can assert exact values without external services.
- Provider/model changes cannot directly manipulate numeric policy.
- Historical analyses can be interpreted using their stored policy version.

### Negative

- Extraction errors still affect the evidence provided to the scorer.
- Lexical overlap and a finite alias map miss some valid equivalence.
- The initial weights are product policy, not empirically calibrated hiring-outcome predictors.
- Version maintenance is required when policy evolves.

## Alternatives considered

- **LLM-generated overall score:** rejected for opacity, nondeterminism, and weak auditability.
- **Embedding similarity as the primary score:** deferred; it would introduce model/version dependence and less direct evidence. A future semantic signal could be an explicitly versioned, low-weight dimension.
- **Rules without versioning:** rejected because stored scores would become ambiguous after policy changes.

## Follow-up rules

- Present the score with dimensions, evidence, and limitations—not as an isolated percentage.
- Treat missing resume evidence differently from proof that a candidate lacks a skill.
- Never position the score as an automated hiring decision or validated prediction until a suitable evaluation exists.
