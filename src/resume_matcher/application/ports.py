"""Ports implemented by infrastructure adapters."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from resume_matcher.application.dto import ExportArtifact, ParsedDocument
from resume_matcher.domain.entities import (
    JobDescription,
    JobProfile,
    MatchAnalysis,
    OptimizedResume,
    ResumeDocument,
    ResumeProfile,
)


class DocumentParser(Protocol):
    def parse(
        self, *, filename: str, content_type: str | None, content: bytes
    ) -> ParsedDocument: ...


class DocumentStorage(Protocol):
    async def save(self, document_id: UUID, content: bytes) -> None: ...

    async def load(self, document_id: UUID) -> bytes | None: ...

    async def delete(self, document_id: UUID) -> None: ...


class ResumeIntelligence(Protocol):
    async def extract_resume(self, text: str) -> ResumeProfile: ...

    async def extract_job(self, text: str) -> JobProfile: ...

    async def optimize_resume(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        match: MatchAnalysis,
    ) -> OptimizedResume: ...


class ResumeRepository(Protocol):
    async def add(self, document: ResumeDocument) -> ResumeDocument: ...

    async def get(self, document_id: UUID) -> ResumeDocument | None: ...

    async def find_by_sha256(self, sha256: str) -> ResumeDocument | None: ...

    async def delete(self, document_id: UUID) -> bool: ...


class JobRepository(Protocol):
    async def add(self, job: JobDescription) -> JobDescription: ...

    async def get(self, job_id: UUID) -> JobDescription | None: ...


class MatchRepository(Protocol):
    async def add(self, analysis: MatchAnalysis) -> MatchAnalysis: ...

    async def get(self, analysis_id: UUID) -> MatchAnalysis | None: ...

    async def update(self, analysis: MatchAnalysis) -> MatchAnalysis: ...


class TransactionManager(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class ResumeExporter(Protocol):
    def export(
        self,
        *,
        format_name: str,
        resume: ResumeProfile | OptimizedResume,
        match: MatchAnalysis,
        job: JobProfile,
    ) -> ExportArtifact: ...
