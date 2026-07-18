"""Offline benchmark runner for extraction, scoring, and factual integrity.

The benchmark intentionally uses only synthetic plain text and the deterministic local
adapter. It is a regression suite, not evidence that the product predicts employment
outcomes or performs equally well on real-world populations.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import fmean
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from resume_matcher.application.ports import ResumeIntelligence
from resume_matcher.domain.entities import (
    JobProfile,
    MatchAnalysis,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.domain.exceptions import FactualIntegrityError
from resume_matcher.domain.fact_guard import ResumeFactGuard
from resume_matcher.domain.matching import MatchingService
from resume_matcher.domain.skill_normalizer import create_skill, normalize_skill
from resume_matcher.infrastructure.ai.contracts import (
    EducationContract,
    ExperienceContract,
    JobExtractionContract,
    ResumeExtractionContract,
)
from resume_matcher.infrastructure.ai.local import LocalResumeIntelligence

DEFAULT_DATASET_PATH = Path(__file__).parent / "fixtures" / "synthetic-v1.json"


class FixtureModel(BaseModel):
    """Strict schema shared by all versioned fixture records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DatasetMetadata(FixtureModel):
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    license: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    intended_use: str = Field(min_length=1)
    limitations: str = Field(min_length=1)


class CaseExpectations(FixtureModel):
    resume_name: str | None
    job_title: str
    resume_skills: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    overall_score: float = Field(ge=0, le=100)


class MatchingCase(FixtureModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    description: str
    tags: list[str]
    resume_text: str = Field(min_length=1)
    job_text: str = Field(min_length=1)
    expected: CaseExpectations


FactGuardMutation = Literal[
    "none",
    "unsupported_skill",
    "identity_change",
    "unrecorded_summary",
    "fabricated_evidence",
]


class FactGuardCase(FixtureModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    source_case_id: str
    mutation: FactGuardMutation
    expected_accepted: bool


class BenchmarkDataset(FixtureModel):
    metadata: DatasetMetadata
    score_tolerance: float = Field(default=0.05, ge=0, le=5)
    matching_cases: list[MatchingCase] = Field(min_length=1)
    fact_guard_cases: list[FactGuardCase] = Field(min_length=1)


@dataclass(slots=True)
class SetMetricAccumulator:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    def observe(self, expected: set[str], predicted: set[str]) -> None:
        self.true_positive += len(expected & predicted)
        self.false_positive += len(predicted - expected)
        self.false_negative += len(expected - predicted)

    def result(self) -> SetMetric:
        precision = _safe_ratio(
            self.true_positive,
            self.true_positive + self.false_positive,
        )
        recall = _safe_ratio(
            self.true_positive,
            self.true_positive + self.false_negative,
        )
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        return SetMetric(
            true_positive=self.true_positive,
            false_positive=self.false_positive,
            false_negative=self.false_negative,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
        )


@dataclass(frozen=True, slots=True)
class SetMetric:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True, slots=True)
class ValidityMetric:
    valid: int
    total: int
    rate: float


@dataclass(frozen=True, slots=True)
class SplitMetric:
    correctly_classified: int
    mislabeled: int
    missing: int
    unexpected: int
    total_expected: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class ScoreAgreementMetric:
    exact_within_tolerance: int
    total: int
    agreement_rate: float
    mean_absolute_error: float
    max_absolute_error: float
    tolerance: float


@dataclass(frozen=True, slots=True)
class FactGuardMetric:
    correct_outcomes: int
    total: int
    accuracy: float
    expected_acceptances: int
    expected_rejections: int


@dataclass(frozen=True, slots=True)
class MatchingCaseResult:
    case_id: str
    tags: tuple[str, ...]
    structured_valid: bool
    expected_resume_skills: tuple[str, ...]
    predicted_resume_skills: tuple[str, ...]
    expected_required_skills: tuple[str, ...]
    predicted_required_skills: tuple[str, ...]
    expected_preferred_skills: tuple[str, ...]
    predicted_preferred_skills: tuple[str, ...]
    expected_score: float
    actual_score: float
    absolute_score_error: float
    score_within_tolerance: bool
    identity_fields_match: bool


@dataclass(frozen=True, slots=True)
class FactGuardCaseResult:
    case_id: str
    mutation: str
    expected_accepted: bool
    actual_accepted: bool
    outcome_correct: bool
    violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    benchmark_name: str
    dataset_version: str
    dataset_license: str
    dataset_provenance: str
    adapter: str
    score_version: str
    sample_counts: dict[str, int]
    structured_validity: ValidityMetric
    identity_exact_match: ValidityMetric
    skills: dict[str, SetMetric]
    required_preferred_split: SplitMetric
    score_agreement: ScoreAgreementMetric
    fact_guard: FactGuardMetric
    matching_cases: tuple[MatchingCaseResult, ...]
    fact_guard_cases: tuple[FactGuardCaseResult, ...]
    interpretation: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def to_markdown(self) -> str:
        metrics = self.skills
        lines = [
            f"# {self.benchmark_name} - local baseline",
            "",
            f"- Dataset version: `{self.dataset_version}`",
            f"- Dataset license: `{self.dataset_license}`",
            f"- Adapter: `{self.adapter}`",
            f"- Score policy: `{self.score_version}`",
            f"- Matching cases: {self.sample_counts['matching_cases']}",
            f"- Fact-guard cases: {self.sample_counts['fact_guard_cases']}",
            "",
            "## Aggregate metrics",
            "",
            "| Metric | Result |",
            "|---|---:|",
            (
                "| Structured contract validity | "
                f"{_percent(self.structured_validity.rate)} "
                f"({self.structured_validity.valid}/{self.structured_validity.total}) |"
            ),
            (
                "| Name/title exact match | "
                f"{_percent(self.identity_exact_match.rate)} "
                f"({self.identity_exact_match.valid}/{self.identity_exact_match.total}) |"
            ),
            f"| Resume skill F1 | {_percent(metrics['resume'].f1)} |",
            f"| Required job skill F1 | {_percent(metrics['required'].f1)} |",
            f"| Preferred job skill F1 | {_percent(metrics['preferred'].f1)} |",
            (
                "| Required/preferred classification accuracy | "
                f"{_percent(self.required_preferred_split.accuracy)} |"
            ),
            (
                "| Score agreement | "
                f"{_percent(self.score_agreement.agreement_rate)} "
                f"(MAE {self.score_agreement.mean_absolute_error:.2f}) |"
            ),
            f"| Fact-guard outcome accuracy | {_percent(self.fact_guard.accuracy)} |",
            "",
            "## Case results",
            "",
            "| Case | Structured | Resume skills | Job split | Score | Expected | Error |",
            "|---|---:|---|---|---:|---:|---:|",
        ]
        for case in self.matching_cases:
            resume_counts = (
                f"{len(set(case.predicted_resume_skills) & set(case.expected_resume_skills))}/"
                f"{len(case.expected_resume_skills)}"
            )
            split_ok = (
                case.predicted_required_skills == case.expected_required_skills
                and case.predicted_preferred_skills == case.expected_preferred_skills
            )
            lines.append(
                f"| `{case.case_id}` | {'pass' if case.structured_valid else 'fail'} | "
                f"{resume_counts} | {'pass' if split_ok else 'fail'} | "
                f"{case.actual_score:.1f} | {case.expected_score:.1f} | "
                f"{case.absolute_score_error:.1f} |"
            )
        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                self.interpretation,
                "",
                "This baseline uses synthetic text and deterministic local heuristics. It is a "
                "software-regression artifact, not evidence of hiring validity, fairness, or "
                "accuracy on real resumes.",
                "",
            ]
        )
        return "\n".join(lines)


async def evaluate_dataset(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    *,
    intelligence: ResumeIntelligence | None = None,
) -> EvaluationReport:
    """Evaluate one versioned dataset using a supplied or local intelligence adapter."""

    dataset = load_dataset(dataset_path)
    adapter = intelligence or LocalResumeIntelligence()
    matcher = MatchingService()
    matching_results: list[MatchingCaseResult] = []
    extracted: dict[str, tuple[ResumeProfile, JobProfile, MatchAnalysis]] = {}
    resume_metrics = SetMetricAccumulator()
    required_metrics = SetMetricAccumulator()
    preferred_metrics = SetMetricAccumulator()
    split_correct = 0
    split_mislabeled = 0
    split_missing = 0
    split_unexpected = 0

    for case in dataset.matching_cases:
        resume = await adapter.extract_resume(case.resume_text)
        job = await adapter.extract_job(case.job_text)
        structured_valid = _profiles_satisfy_contracts(resume, job)
        result = matcher.score(resume, job)
        analysis = MatchAnalysis(
            resume_id=UUID(int=0),
            job_id=UUID(int=1),
            result=result,
        )
        extracted[case.case_id] = (resume, job, analysis)

        expected_resume = _normalized(case.expected.resume_skills)
        expected_required = _normalized(case.expected.required_skills)
        expected_preferred = _normalized(case.expected.preferred_skills)
        predicted_resume = {skill.normalized_name for skill in resume.skills}
        predicted_required = {skill.normalized_name for skill in job.required_skills}
        predicted_preferred = {skill.normalized_name for skill in job.preferred_skills}

        resume_metrics.observe(expected_resume, predicted_resume)
        required_metrics.observe(expected_required, predicted_required)
        preferred_metrics.observe(expected_preferred, predicted_preferred)
        split = _split_counts(
            expected_required,
            expected_preferred,
            predicted_required,
            predicted_preferred,
        )
        split_correct += split[0]
        split_mislabeled += split[1]
        split_missing += split[2]
        split_unexpected += split[3]
        absolute_error = round(abs(result.overall_score - case.expected.overall_score), 4)
        matching_results.append(
            MatchingCaseResult(
                case_id=case.case_id,
                tags=tuple(case.tags),
                structured_valid=structured_valid,
                expected_resume_skills=tuple(sorted(expected_resume)),
                predicted_resume_skills=tuple(sorted(predicted_resume)),
                expected_required_skills=tuple(sorted(expected_required)),
                predicted_required_skills=tuple(sorted(predicted_required)),
                expected_preferred_skills=tuple(sorted(expected_preferred)),
                predicted_preferred_skills=tuple(sorted(predicted_preferred)),
                expected_score=case.expected.overall_score,
                actual_score=result.overall_score,
                absolute_score_error=absolute_error,
                score_within_tolerance=absolute_error <= dataset.score_tolerance,
                identity_fields_match=(
                    resume.name == case.expected.resume_name
                    and job.title == case.expected.job_title
                ),
            )
        )

    fact_guard_results = await _evaluate_fact_guard(dataset, extracted, adapter)
    valid_count = sum(case.structured_valid for case in matching_results)
    identity_match_count = sum(case.identity_fields_match for case in matching_results)
    exact_scores = sum(case.score_within_tolerance for case in matching_results)
    score_errors = [case.absolute_score_error for case in matching_results]
    expected_split_total = split_correct + split_mislabeled + split_missing
    fact_guard_correct = sum(case.outcome_correct for case in fact_guard_results)

    return EvaluationReport(
        benchmark_name=dataset.metadata.name,
        dataset_version=dataset.metadata.version,
        dataset_license=dataset.metadata.license,
        dataset_provenance=dataset.metadata.provenance,
        adapter=type(adapter).__name__,
        score_version=matcher.score_version,
        sample_counts={
            "matching_cases": len(matching_results),
            "fact_guard_cases": len(fact_guard_results),
        },
        structured_validity=ValidityMetric(
            valid=valid_count,
            total=len(matching_results),
            rate=round(_safe_ratio(valid_count, len(matching_results)), 4),
        ),
        identity_exact_match=ValidityMetric(
            valid=identity_match_count,
            total=len(matching_results),
            rate=round(_safe_ratio(identity_match_count, len(matching_results)), 4),
        ),
        skills={
            "resume": resume_metrics.result(),
            "required": required_metrics.result(),
            "preferred": preferred_metrics.result(),
        },
        required_preferred_split=SplitMetric(
            correctly_classified=split_correct,
            mislabeled=split_mislabeled,
            missing=split_missing,
            unexpected=split_unexpected,
            total_expected=expected_split_total,
            accuracy=round(_safe_ratio(split_correct, expected_split_total), 4),
        ),
        score_agreement=ScoreAgreementMetric(
            exact_within_tolerance=exact_scores,
            total=len(matching_results),
            agreement_rate=round(_safe_ratio(exact_scores, len(matching_results)), 4),
            mean_absolute_error=round(fmean(score_errors), 4),
            max_absolute_error=max(score_errors, default=0.0),
            tolerance=dataset.score_tolerance,
        ),
        fact_guard=FactGuardMetric(
            correct_outcomes=fact_guard_correct,
            total=len(fact_guard_results),
            accuracy=round(_safe_ratio(fact_guard_correct, len(fact_guard_results)), 4),
            expected_acceptances=sum(case.expected_accepted for case in dataset.fact_guard_cases),
            expected_rejections=sum(
                not case.expected_accepted for case in dataset.fact_guard_cases
            ),
        ),
        matching_cases=tuple(matching_results),
        fact_guard_cases=tuple(fact_guard_results),
        interpretation=(
            "Exact, versioned golden-case agreement measures deterministic regression behavior "
            "for the local adapter. Provider quality requires a separate opt-in evaluation run."
        ),
    )


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> BenchmarkDataset:
    """Read and validate a benchmark fixture before any evaluation work begins."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    dataset = BenchmarkDataset.model_validate(payload)
    matching_ids = [case.case_id for case in dataset.matching_cases]
    guard_ids = [case.case_id for case in dataset.fact_guard_cases]
    if len(set(matching_ids)) != len(matching_ids):
        raise ValueError("Matching case IDs must be unique")
    if len(set(guard_ids)) != len(guard_ids):
        raise ValueError("Fact-guard case IDs must be unique")
    unknown_sources = {
        case.source_case_id
        for case in dataset.fact_guard_cases
        if case.source_case_id not in matching_ids
    }
    if unknown_sources:
        raise ValueError(f"Unknown fact-guard source cases: {', '.join(sorted(unknown_sources))}")
    return dataset


async def _evaluate_fact_guard(
    dataset: BenchmarkDataset,
    extracted: dict[str, tuple[ResumeProfile, JobProfile, MatchAnalysis]],
    adapter: ResumeIntelligence,
) -> list[FactGuardCaseResult]:
    guard = ResumeFactGuard()
    results: list[FactGuardCaseResult] = []
    for case in dataset.fact_guard_cases:
        resume, job, analysis = extracted[case.source_case_id]
        optimized = await adapter.optimize_resume(resume, job, analysis)
        candidate = _apply_mutation(optimized, case.mutation)
        violations: tuple[str, ...] = ()
        try:
            guard.validate(resume, candidate)
            accepted = True
        except FactualIntegrityError as error:
            accepted = False
            violations = error.violations
        results.append(
            FactGuardCaseResult(
                case_id=case.case_id,
                mutation=case.mutation,
                expected_accepted=case.expected_accepted,
                actual_accepted=accepted,
                outcome_correct=accepted == case.expected_accepted,
                violations=violations,
            )
        )
    return results


def _apply_mutation(optimized: OptimizedResume, mutation: FactGuardMutation) -> OptimizedResume:
    if mutation == "none":
        return optimized
    if mutation == "unsupported_skill":
        return replace(optimized, skills=(*optimized.skills, create_skill("Kubernetes")))
    if mutation == "identity_change":
        return replace(optimized, name="Synthetic Impostor")
    if mutation == "unrecorded_summary":
        return replace(
            optimized,
            summary="Fabricated executive with unsupported achievements.",
            changes=(),
        )
    if mutation == "fabricated_evidence":
        changes = tuple(
            replace(change, source_evidence=("invented billion-dollar outcome",))
            for change in optimized.changes
        )
        return replace(optimized, changes=changes)
    raise AssertionError(f"Unhandled fact-guard mutation: {mutation}")


def _profiles_satisfy_contracts(resume: ResumeProfile, job: JobProfile) -> bool:
    try:
        ResumeExtractionContract(
            name=resume.name,
            headline=resume.headline,
            summary=resume.summary,
            email=resume.email,
            phone=resume.phone,
            location=resume.location,
            skills=[skill.name for skill in resume.skills],
            experiences=[
                ExperienceContract(
                    title=item.title,
                    company=item.company,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    location=item.location,
                    bullets=list(item.bullets),
                    skills=list(item.skills),
                )
                for item in resume.experiences
            ],
            education=[
                EducationContract(
                    institution=item.institution,
                    degree=item.degree,
                    field=item.field,
                    graduation_year=item.graduation_year,
                    level=item.level,
                )
                for item in resume.education
            ],
            certifications=list(resume.certifications),
            total_years_experience=resume.total_years_experience,
            keywords=list(resume.keywords),
        )
        JobExtractionContract(
            title=job.title,
            company=job.company,
            summary=job.summary,
            required_skills=[skill.name for skill in job.required_skills],
            preferred_skills=[skill.name for skill in job.preferred_skills],
            responsibilities=list(job.responsibilities),
            education_level=job.education_level,
            minimum_years_experience=job.minimum_years_experience,
            keywords=list(job.keywords),
        )
    except ValueError:
        return False
    return True


def _split_counts(
    expected_required: set[str],
    expected_preferred: set[str],
    predicted_required: set[str],
    predicted_preferred: set[str],
) -> tuple[int, int, int, int]:
    correct = len(expected_required & predicted_required) + len(
        expected_preferred & predicted_preferred
    )
    mislabeled = len(expected_required & predicted_preferred) + len(
        expected_preferred & predicted_required
    )
    predicted = predicted_required | predicted_preferred
    expected = expected_required | expected_preferred
    missing = len(expected - predicted)
    unexpected = len(predicted - expected)
    return correct, mislabeled, missing, unexpected


def _normalized(values: list[str]) -> set[str]:
    return {normalized for value in values if (normalized := normalize_skill(value))}


def _safe_ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"
