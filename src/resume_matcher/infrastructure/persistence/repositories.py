from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from resume_matcher.domain.entities import (
    JobDescription,
    MatchAnalysis,
    ResumeDocument,
)
from resume_matcher.infrastructure.persistence.models import JobRow, MatchRow, ResumeRow
from resume_matcher.infrastructure.persistence.serialization import (
    job_profile_from_dict,
    job_profile_to_dict,
    match_result_from_dict,
    match_result_to_dict,
    optimized_resume_from_dict,
    optimized_resume_to_dict,
    resume_profile_from_dict,
    resume_profile_to_dict,
)


class SqlAlchemyResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: ResumeDocument) -> ResumeDocument:
        self._session.add(
            ResumeRow(
                id=str(document.id),
                filename=document.filename,
                content_type=document.content_type,
                sha256=document.sha256,
                profile=resume_profile_to_dict(document.profile),
                created_at=document.created_at,
            )
        )
        await self._session.flush()
        return document

    async def get(self, document_id: UUID) -> ResumeDocument | None:
        row = await self._session.get(ResumeRow, str(document_id))
        return self._to_entity(row) if row else None

    async def find_by_sha256(self, sha256: str) -> ResumeDocument | None:
        row = await self._session.scalar(select(ResumeRow).where(ResumeRow.sha256 == sha256))
        return self._to_entity(row) if row else None

    async def delete(self, document_id: UUID) -> bool:
        row = await self._session.get(ResumeRow, str(document_id))
        if row is None:
            return False
        await self._session.delete(row)
        return True

    @staticmethod
    def _to_entity(row: ResumeRow) -> ResumeDocument:
        return ResumeDocument(
            id=UUID(row.id),
            filename=row.filename,
            content_type=row.content_type,
            sha256=row.sha256,
            profile=resume_profile_from_dict(row.profile),
            created_at=row.created_at,
        )


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: JobDescription) -> JobDescription:
        self._session.add(
            JobRow(
                id=str(job.id),
                title=job.profile.title,
                raw_text=job.profile.raw_text,
                profile=job_profile_to_dict(job.profile),
                created_at=job.created_at,
            )
        )
        await self._session.flush()
        return job

    async def get(self, job_id: UUID) -> JobDescription | None:
        row = await self._session.get(JobRow, str(job_id))
        if row is None:
            return None
        return JobDescription(
            id=UUID(row.id),
            profile=job_profile_from_dict(row.profile),
            created_at=row.created_at,
        )


class SqlAlchemyMatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, analysis: MatchAnalysis) -> MatchAnalysis:
        self._session.add(
            MatchRow(
                id=str(analysis.id),
                resume_id=str(analysis.resume_id),
                job_id=str(analysis.job_id),
                result=match_result_to_dict(analysis.result),
                optimized_resume=(
                    optimized_resume_to_dict(analysis.optimized_resume)
                    if analysis.optimized_resume
                    else None
                ),
                created_at=analysis.created_at,
                updated_at=analysis.updated_at,
            )
        )
        await self._session.flush()
        return analysis

    async def get(self, analysis_id: UUID) -> MatchAnalysis | None:
        row = await self._session.get(MatchRow, str(analysis_id))
        return self._to_entity(row) if row else None

    async def update(self, analysis: MatchAnalysis) -> MatchAnalysis:
        row = await self._session.get(MatchRow, str(analysis.id))
        if row is None:
            return await self.add(analysis)
        row.result = match_result_to_dict(analysis.result)
        row.optimized_resume = (
            optimized_resume_to_dict(analysis.optimized_resume)
            if analysis.optimized_resume
            else None
        )
        row.updated_at = analysis.updated_at
        await self._session.flush()
        return analysis

    @staticmethod
    def _to_entity(row: MatchRow) -> MatchAnalysis:
        return MatchAnalysis(
            id=UUID(row.id),
            resume_id=UUID(row.resume_id),
            job_id=UUID(row.job_id),
            result=match_result_from_dict(row.result),
            optimized_resume=(
                optimized_resume_from_dict(row.optimized_resume) if row.optimized_resume else None
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
