from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from resume_matcher.application.dto import ExportArtifact
from resume_matcher.application.ports import (
    JobRepository,
    MatchRepository,
    ResumeExporter,
    ResumeIntelligence,
    ResumeRepository,
    TransactionManager,
)
from resume_matcher.domain.entities import MatchAnalysis, utc_now
from resume_matcher.domain.exceptions import EntityNotFoundError
from resume_matcher.domain.fact_guard import ResumeFactGuard
from resume_matcher.domain.matching import MatchingService


class MatchService:
    def __init__(
        self,
        *,
        resumes: ResumeRepository,
        jobs: JobRepository,
        matches: MatchRepository,
        transaction: TransactionManager,
        matcher: MatchingService,
        intelligence: ResumeIntelligence,
        fact_guard: ResumeFactGuard,
    ) -> None:
        self._resumes = resumes
        self._jobs = jobs
        self._matches = matches
        self._transaction = transaction
        self._matcher = matcher
        self._intelligence = intelligence
        self._fact_guard = fact_guard

    async def create(self, *, resume_id: UUID, job_id: UUID) -> MatchAnalysis:
        resume = await self._resumes.get(resume_id)
        if resume is None:
            raise EntityNotFoundError("resume", str(resume_id))
        job = await self._jobs.get(job_id)
        if job is None:
            raise EntityNotFoundError("job description", str(job_id))
        result = self._matcher.score(resume.profile, job.profile)
        analysis = MatchAnalysis(resume_id=resume_id, job_id=job_id, result=result)
        try:
            await self._matches.add(analysis)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise
        return analysis

    async def get(self, analysis_id: UUID) -> MatchAnalysis:
        analysis = await self._matches.get(analysis_id)
        if analysis is None:
            raise EntityNotFoundError("match analysis", str(analysis_id))
        return analysis

    async def optimize(self, analysis_id: UUID) -> MatchAnalysis:
        analysis = await self.get(analysis_id)
        resume = await self._resumes.get(analysis.resume_id)
        job = await self._jobs.get(analysis.job_id)
        if resume is None:
            raise EntityNotFoundError("resume", str(analysis.resume_id))
        if job is None:
            raise EntityNotFoundError("job description", str(analysis.job_id))
        optimized = await self._intelligence.optimize_resume(resume.profile, job.profile, analysis)
        self._fact_guard.validate(resume.profile, optimized)
        updated = replace(analysis, optimized_resume=optimized, updated_at=utc_now())
        try:
            await self._matches.update(updated)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise
        return updated


class ExportService:
    def __init__(
        self,
        *,
        resumes: ResumeRepository,
        jobs: JobRepository,
        matches: MatchRepository,
        exporter: ResumeExporter,
    ) -> None:
        self._resumes = resumes
        self._jobs = jobs
        self._matches = matches
        self._exporter = exporter

    async def export(self, analysis_id: UUID, format_name: str) -> ExportArtifact:
        analysis = await self._matches.get(analysis_id)
        if analysis is None:
            raise EntityNotFoundError("match analysis", str(analysis_id))
        resume = await self._resumes.get(analysis.resume_id)
        job = await self._jobs.get(analysis.job_id)
        if resume is None:
            raise EntityNotFoundError("resume", str(analysis.resume_id))
        if job is None:
            raise EntityNotFoundError("job description", str(analysis.job_id))
        selected = analysis.optimized_resume or resume.profile
        artifact: ExportArtifact = self._exporter.export(
            format_name=format_name,
            resume=selected,
            match=analysis,
            job=job.profile,
        )
        return artifact
