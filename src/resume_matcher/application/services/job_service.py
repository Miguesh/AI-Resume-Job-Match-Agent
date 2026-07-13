from __future__ import annotations

from uuid import UUID

from resume_matcher.application.ports import (
    JobRepository,
    ResumeIntelligence,
    TransactionManager,
)
from resume_matcher.domain.entities import JobDescription
from resume_matcher.domain.exceptions import EntityNotFoundError


class JobService:
    def __init__(
        self,
        *,
        intelligence: ResumeIntelligence,
        repository: JobRepository,
        transaction: TransactionManager,
    ) -> None:
        self._intelligence = intelligence
        self._repository = repository
        self._transaction = transaction

    async def create(self, text: str) -> JobDescription:
        profile = await self._intelligence.extract_job(text)
        job = JobDescription(profile=profile)
        await self._repository.add(job)
        await self._transaction.commit()
        return job

    async def get(self, job_id: UUID) -> JobDescription:
        job = await self._repository.get(job_id)
        if job is None:
            raise EntityNotFoundError("job description", str(job_id))
        return job
