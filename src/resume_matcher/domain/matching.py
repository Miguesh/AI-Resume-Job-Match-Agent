"""Versioned, deterministic, explainable resume matching policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite

from resume_matcher.domain.entities import (
    EducationLevel,
    JobProfile,
    MatchResult,
    ResumeProfile,
    ScoreDimension,
)
from resume_matcher.domain.recommendations import RecommendationService
from resume_matcher.domain.skill_normalizer import normalize_skill


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    skills: float = 0.45
    experience: float = 0.25
    keywords: float = 0.15
    education: float = 0.10
    responsibilities: float = 0.05

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in self.as_tuple()):
            raise ValueError("Scoring weights must be finite")
        total = (
            self.skills + self.experience + self.keywords + self.education + self.responsibilities
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Scoring weights must add up to 1.0")
        if any(value < 0 for value in self.as_tuple()):
            raise ValueError("Scoring weights cannot be negative")

    def as_tuple(self) -> tuple[float, ...]:
        return (
            self.skills,
            self.experience,
            self.keywords,
            self.education,
            self.responsibilities,
        )


_EDUCATION_RANK = {
    EducationLevel.NONE: 0,
    EducationLevel.HIGH_SCHOOL: 1,
    EducationLevel.ASSOCIATE: 2,
    EducationLevel.BACHELOR: 3,
    EducationLevel.MASTER: 4,
    EducationLevel.DOCTORATE: 5,
}

_STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "our",
    "that",
    "the",
    "this",
    "with",
    "will",
    "you",
    "your",
}


class MatchingService:
    """Compute a score exclusively from validated structured evidence."""

    score_version = "2.0.0"

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        recommendations: RecommendationService | None = None,
    ) -> None:
        self._weights = weights or ScoringWeights()
        self._recommendations = recommendations or RecommendationService()

    def score(self, resume: ResumeProfile, job: JobProfile) -> MatchResult:
        applicable = {
            "skills": bool(job.required_skills or job.preferred_skills),
            "experience": job.minimum_years_experience > 0,
            "keywords": bool(job.keywords),
            "education": job.education_level is not EducationLevel.NONE,
            "responsibilities": bool(job.responsibilities),
        }
        base_weights = {
            "skills": self._weights.skills,
            "experience": self._weights.experience,
            "keywords": self._weights.keywords,
            "education": self._weights.education,
            "responsibilities": self._weights.responsibilities,
        }
        active_weight = sum(
            base_weights[name] for name, is_applicable in applicable.items() if is_applicable
        )
        effective_weights = {
            name: (weight / active_weight if applicable[name] and active_weight else 0.0)
            for name, weight in base_weights.items()
        }

        resume_skills = {skill.normalized_name for skill in resume.skills}
        required = {skill.normalized_name: skill.name for skill in job.required_skills}
        preferred = {skill.normalized_name: skill.name for skill in job.preferred_skills}

        matched_required = sorted(required[name] for name in required.keys() & resume_skills)
        missing_required = sorted(required[name] for name in required.keys() - resume_skills)
        matched_preferred = sorted(preferred[name] for name in preferred.keys() & resume_skills)
        missing_preferred = sorted(preferred[name] for name in preferred.keys() - resume_skills)

        required_score = self._ratio(len(matched_required), len(required))
        preferred_score = self._ratio(len(matched_preferred), len(preferred))
        if required and preferred:
            skills_score = required_score * 0.8 + preferred_score * 0.2
        elif required:
            skills_score = required_score
        elif preferred:
            skills_score = preferred_score
        else:
            skills_score = 100.0

        experience_score = self._experience_score(
            resume.total_years_experience, job.minimum_years_experience
        )
        education_score = self._education_score(resume, job.education_level)

        resume_keywords = {
            normalize_skill(value) for value in (*resume.keywords, *[s.name for s in resume.skills])
        }
        job_keywords = {normalize_skill(value): value for value in job.keywords}
        matched_keywords = sorted(
            job_keywords[value] for value in job_keywords.keys() & resume_keywords
        )
        missing_keywords = sorted(
            job_keywords[value] for value in job_keywords.keys() - resume_keywords
        )
        keyword_score = self._ratio(len(matched_keywords), len(job_keywords))

        resume_terms = self._terms(
            " ".join(
                [
                    resume.summary or "",
                    *(bullet for item in resume.experiences for bullet in item.bullets),
                ]
            )
        )
        responsibility_terms = self._terms(" ".join(job.responsibilities))
        responsibility_score = self._overlap_score(resume_terms, responsibility_terms)

        dimensions = (
            self._dimension(
                "skills",
                effective_weights["skills"],
                skills_score if applicable["skills"] else 0.0,
                (*matched_required, *matched_preferred),
                (*missing_required, *missing_preferred),
                (
                    f"Matched {len(matched_required)}/{len(required)} required and "
                    f"{len(matched_preferred)}/{len(preferred)} preferred skills."
                    if applicable["skills"]
                    else (
                        "No required or preferred skills were extracted; this dimension is not "
                        "scored."
                    )
                ),
            ),
            self._dimension(
                "experience",
                effective_weights["experience"],
                experience_score if applicable["experience"] else 0.0,
                ((f"{resume.total_years_experience:g} years",) if applicable["experience"] else ()),
                (
                    ()
                    if experience_score >= 100 or not applicable["experience"]
                    else (f"{job.minimum_years_experience:g} years required",)
                ),
                (
                    f"Resume evidence indicates {resume.total_years_experience:g} years against "
                    f"a {job.minimum_years_experience:g}-year minimum."
                    if applicable["experience"]
                    else "No minimum experience was extracted; this dimension is not scored."
                ),
            ),
            self._dimension(
                "keywords",
                effective_weights["keywords"],
                keyword_score if applicable["keywords"] else 0.0,
                matched_keywords,
                missing_keywords,
                (
                    f"Matched {len(matched_keywords)}/{len(job_keywords)} normalized job keywords."
                    if applicable["keywords"]
                    else "No job keywords were extracted; this dimension is not scored."
                ),
            ),
            self._dimension(
                "education",
                effective_weights["education"],
                education_score if applicable["education"] else 0.0,
                (
                    ()
                    if education_score < 100 or not applicable["education"]
                    else (job.education_level.value,)
                ),
                (
                    ()
                    if education_score >= 100 or not applicable["education"]
                    else (job.education_level.value,)
                ),
                (
                    self._education_explanation(resume, job.education_level, education_score)
                    if applicable["education"]
                    else "No minimum education was extracted; this dimension is not scored."
                ),
            ),
            self._dimension(
                "responsibilities",
                effective_weights["responsibilities"],
                responsibility_score if applicable["responsibilities"] else 0.0,
                tuple(sorted(resume_terms & responsibility_terms)[:12]),
                (),
                (
                    "Token overlap between documented achievements and job responsibilities; "
                    "this is a small supporting signal, not an LLM-assigned score."
                    if applicable["responsibilities"]
                    else "No responsibilities were extracted; this dimension is not scored."
                ),
            ),
        )
        overall = round(sum(item.weighted_score for item in dimensions), 1)
        recommendations = self._recommendations.build(
            resume=resume,
            job=job,
            missing_required=tuple(missing_required),
            missing_preferred=tuple(missing_preferred),
            missing_keywords=tuple(missing_keywords),
            experience_score=experience_score,
            education_score=education_score,
        )
        has_applicable_criteria = any(applicable.values())
        scored_dimensions = tuple(item for item in dimensions if item.weight > 0)
        if not has_applicable_criteria:
            explanation = (
                "A meaningful match score cannot be calculated because the job description did "
                "not yield any explicit skills, experience, keywords, education, or responsibility "
                "criteria."
            )
        elif not scored_dimensions:
            explanation = (
                "A meaningful match score cannot be calculated because every extracted job "
                "criterion is disabled by the configured scoring weights."
            )
        elif len(scored_dimensions) == 1:
            dimension = scored_dimensions[0]
            explanation = (
                f"The {overall:.1f}% score is based on the only enabled applicable deterministic "
                f"dimension, {dimension.name} ({dimension.raw_score:.1f}%); its configured base "
                "weight is renormalized to 100.0%."
            )
        else:
            strongest = max(scored_dimensions, key=lambda item: item.raw_score)
            opportunity = max(
                scored_dimensions,
                key=lambda item: (100.0 - item.raw_score) * item.weight,
            )
            weighted_opportunity = (100.0 - opportunity.raw_score) * opportunity.weight
            if weighted_opportunity > 0:
                opportunity_text = (
                    f"The largest weighted improvement opportunity is {opportunity.name} "
                    f"({opportunity.raw_score:.1f}%), worth up to "
                    f"{weighted_opportunity:.1f} overall percentage points."
                )
            else:
                opportunity_text = (
                    "Every enabled applicable dimension reached 100.0% based on the extracted "
                    "evidence."
                )
            explanation = (
                f"The {overall:.1f}% score is the weighted result of "
                f"{len(scored_dimensions)} enabled applicable deterministic dimensions; weights "
                "are renormalized across them. "
                f"The strongest dimension is {strongest.name} ({strongest.raw_score:.1f}%). "
                f"{opportunity_text}"
            )
        return MatchResult(
            overall_score=overall,
            dimensions=dimensions,
            matched_skills=tuple(sorted({*matched_required, *matched_preferred})),
            missing_required_skills=tuple(missing_required),
            missing_preferred_skills=tuple(missing_preferred),
            matched_keywords=tuple(matched_keywords),
            missing_keywords=tuple(missing_keywords),
            recommendations=recommendations,
            explanation=explanation,
            score_version=self.score_version,
        )

    @staticmethod
    def _ratio(matched: int, total: int) -> float:
        return 100.0 if total == 0 else round(matched / total * 100, 2)

    @staticmethod
    def _experience_score(actual: float, required: float) -> float:
        if required <= 0:
            return 100.0
        return round(min(max(actual, 0) / required, 1.0) * 100, 2)

    @staticmethod
    def _education_score(resume: ResumeProfile, required: EducationLevel) -> float:
        if required is EducationLevel.NONE:
            return 100.0
        attained = max((_EDUCATION_RANK[item.level] for item in resume.education), default=0)
        required_rank = _EDUCATION_RANK[required]
        return 100.0 if attained >= required_rank else round(attained / required_rank * 100, 2)

    @staticmethod
    def _education_explanation(
        resume: ResumeProfile, required: EducationLevel, score: float
    ) -> str:
        if required is EducationLevel.NONE:
            return "The job description does not specify a minimum education level."
        highest = max(
            (item.level for item in resume.education),
            key=lambda level: _EDUCATION_RANK[level],
            default=EducationLevel.NONE,
        )
        outcome = "meets" if score >= 100 else "does not clearly meet"
        return (
            f"Highest extracted level ({highest.value}) {outcome} the {required.value} requirement."
        )

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z][a-z0-9+#.-]{2,}", text.casefold())
            if token not in _STOP_WORDS
        }

    @staticmethod
    def _overlap_score(actual: set[str], target: set[str]) -> float:
        if not target:
            return 100.0
        return round(len(actual & target) / len(target) * 100, 2)

    @staticmethod
    def _dimension(
        name: str,
        weight: float,
        score: float,
        matched: tuple[str, ...] | list[str],
        missing: tuple[str, ...] | list[str],
        explanation: str,
    ) -> ScoreDimension:
        return ScoreDimension(
            name=name,
            weight=weight,
            raw_score=round(score, 2),
            weighted_score=round(score * weight, 2),
            matched=tuple(matched),
            missing=tuple(missing),
            explanation=explanation,
        )
