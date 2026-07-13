from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, cast

from resume_matcher.domain.entities import (
    Education,
    EducationLevel,
    Experience,
    JobProfile,
    MatchResult,
    OptimizationChange,
    OptimizedResume,
    Recommendation,
    RecommendationPriority,
    ResumeProfile,
    ScoreDimension,
    Skill,
)

JsonObject = dict[str, Any]


def _jsonable(
    value: ResumeProfile | JobProfile | MatchResult | OptimizedResume,
) -> JsonObject:
    return cast(JsonObject, json.loads(json.dumps(asdict(value), default=str)))


def _skill(value: JsonObject) -> Skill:
    return Skill(name=str(value["name"]), normalized_name=str(value["normalized_name"]))


def _experience(value: JsonObject) -> Experience:
    return Experience(
        title=str(value["title"]),
        company=str(value["company"]),
        start_date=value.get("start_date"),
        end_date=value.get("end_date"),
        location=value.get("location"),
        bullets=tuple(value.get("bullets", ())),
        skills=tuple(value.get("skills", ())),
    )


def _education(value: JsonObject) -> Education:
    return Education(
        institution=str(value["institution"]),
        degree=str(value["degree"]),
        field=value.get("field"),
        graduation_year=value.get("graduation_year"),
        level=EducationLevel(value.get("level", EducationLevel.NONE)),
    )


def resume_profile_to_dict(value: ResumeProfile) -> JsonObject:
    return _jsonable(value)


def resume_profile_from_dict(value: JsonObject) -> ResumeProfile:
    return ResumeProfile(
        name=value.get("name"),
        headline=value.get("headline"),
        summary=value.get("summary"),
        email=value.get("email"),
        phone=value.get("phone"),
        location=value.get("location"),
        skills=tuple(_skill(item) for item in value.get("skills", ())),
        experiences=tuple(_experience(item) for item in value.get("experiences", ())),
        education=tuple(_education(item) for item in value.get("education", ())),
        certifications=tuple(value.get("certifications", ())),
        total_years_experience=float(value.get("total_years_experience", 0)),
        keywords=tuple(value.get("keywords", ())),
        raw_text=str(value.get("raw_text", "")),
    )


def job_profile_to_dict(value: JobProfile) -> JsonObject:
    return _jsonable(value)


def job_profile_from_dict(value: JsonObject) -> JobProfile:
    return JobProfile(
        title=str(value["title"]),
        company=value.get("company"),
        summary=value.get("summary"),
        required_skills=tuple(_skill(item) for item in value.get("required_skills", ())),
        preferred_skills=tuple(_skill(item) for item in value.get("preferred_skills", ())),
        responsibilities=tuple(value.get("responsibilities", ())),
        education_level=EducationLevel(value.get("education_level", EducationLevel.NONE)),
        minimum_years_experience=float(value.get("minimum_years_experience", 0)),
        keywords=tuple(value.get("keywords", ())),
        raw_text=str(value.get("raw_text", "")),
    )


def match_result_to_dict(value: MatchResult) -> JsonObject:
    return _jsonable(value)


def match_result_from_dict(value: JsonObject) -> MatchResult:
    return MatchResult(
        overall_score=float(value["overall_score"]),
        dimensions=tuple(
            ScoreDimension(
                name=str(item["name"]),
                weight=float(item["weight"]),
                raw_score=float(item["raw_score"]),
                weighted_score=float(item["weighted_score"]),
                matched=tuple(item.get("matched", ())),
                missing=tuple(item.get("missing", ())),
                explanation=str(item["explanation"]),
            )
            for item in value.get("dimensions", ())
        ),
        matched_skills=tuple(value.get("matched_skills", ())),
        missing_required_skills=tuple(value.get("missing_required_skills", ())),
        missing_preferred_skills=tuple(value.get("missing_preferred_skills", ())),
        matched_keywords=tuple(value.get("matched_keywords", ())),
        missing_keywords=tuple(value.get("missing_keywords", ())),
        recommendations=tuple(
            Recommendation(
                category=str(item["category"]),
                priority=RecommendationPriority(item["priority"]),
                title=str(item["title"]),
                guidance=str(item["guidance"]),
                evidence=tuple(item.get("evidence", ())),
            )
            for item in value.get("recommendations", ())
        ),
        explanation=str(value["explanation"]),
        score_version=str(value.get("score_version", "1.0.0")),
    )


def optimized_resume_to_dict(value: OptimizedResume) -> JsonObject:
    return _jsonable(value)


def optimized_resume_from_dict(value: JsonObject) -> OptimizedResume:
    return OptimizedResume(
        name=value.get("name"),
        headline=value.get("headline"),
        summary=value.get("summary"),
        email=value.get("email"),
        phone=value.get("phone"),
        location=value.get("location"),
        skills=tuple(_skill(item) for item in value.get("skills", ())),
        experiences=tuple(_experience(item) for item in value.get("experiences", ())),
        education=tuple(_education(item) for item in value.get("education", ())),
        certifications=tuple(value.get("certifications", ())),
        changes=tuple(
            OptimizationChange(
                section=str(item["section"]),
                before=item.get("before"),
                after=str(item["after"]),
                reason=str(item["reason"]),
                source_evidence=tuple(item.get("source_evidence", ())),
            )
            for item in value.get("changes", ())
        ),
        warnings=tuple(value.get("warnings", ())),
    )
