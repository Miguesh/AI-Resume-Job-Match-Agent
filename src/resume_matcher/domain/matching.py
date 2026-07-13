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

    score_version = "1.0.0"

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        recommendations: RecommendationService | None = None,
    ) -> None:
        self._weights = weights or ScoringWeights()
        self._recommendations = recommendations or RecommendationService()

    def score(self, resume: ResumeProfile, job: JobProfile) -> MatchResult:
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
                self._weights.skills,
                skills_score,
                (*matched_required, *matched_preferred),
                (*missing_required, *missing_preferred),
                f"Matched {len(matched_required)}/{len(required)} required and "
                f"{len(matched_preferred)}/{len(preferred)} preferred skills.",
            ),
            self._dimension(
                "experience",
                self._weights.experience,
                experience_score,
                (f"{resume.total_years_experience:g} years",),
                (
                    ()
                    if experience_score >= 100
                    else (f"{job.minimum_years_experience:g} years required",)
                ),
                f"Resume evidence indicates {resume.total_years_experience:g} years against "
                f"a {job.minimum_years_experience:g}-year minimum.",
            ),
            self._dimension(
                "keywords",
                self._weights.keywords,
                keyword_score,
                matched_keywords,
                missing_keywords,
                f"Matched {len(matched_keywords)}/{len(job_keywords)} normalized job keywords.",
            ),
            self._dimension(
                "education",
                self._weights.education,
                education_score,
                (() if education_score < 100 else (job.education_level.value,)),
                (() if education_score >= 100 else (job.education_level.value,)),
                self._education_explanation(resume, job.education_level, education_score),
            ),
            self._dimension(
                "responsibilities",
                self._weights.responsibilities,
                responsibility_score,
                tuple(sorted(resume_terms & responsibility_terms)[:12]),
                (),
                "Token overlap between documented achievements and job responsibilities; "
                "this is a small supporting signal, not an LLM-assigned score.",
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
        strongest = max(dimensions, key=lambda item: item.raw_score)
        weakest = min(dimensions, key=lambda item: item.raw_score)
        explanation = (
            f"The {overall:.1f}% score is the weighted result of five deterministic dimensions. "
            f"The strongest dimension is {strongest.name} ({strongest.raw_score:.1f}%), while "
            f"{weakest.name} ({weakest.raw_score:.1f}%) has the largest improvement opportunity."
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
