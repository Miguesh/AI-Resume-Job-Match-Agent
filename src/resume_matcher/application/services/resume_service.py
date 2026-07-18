from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from resume_matcher.application.ports import (
    DocumentParser,
    DocumentStorage,
    ResumeIntelligence,
    ResumeRepository,
    TransactionManager,
)
from resume_matcher.domain.entities import ResumeDocument
from resume_matcher.domain.exceptions import EntityNotFoundError


class ResumeService:
    def __init__(
        self,
        *,
        parser: DocumentParser,
        storage: DocumentStorage,
        intelligence: ResumeIntelligence,
        repository: ResumeRepository,
        transaction: TransactionManager,
    ) -> None:
        self._parser = parser
        self._storage = storage
        self._intelligence = intelligence
        self._repository = repository
        self._transaction = transaction

    async def upload(
        self, *, filename: str, content_type: str | None, content: bytes
    ) -> tuple[ResumeDocument, tuple[str, ...]]:
        digest = hashlib.sha256(content).hexdigest()
        existing = await self._repository.find_by_sha256(digest)
        if existing is not None:
            return existing, (
                "An identical resume was already uploaded; returning the existing resource.",
            )

        parsed = self._parser.parse(filename=filename, content_type=content_type, content=content)
        profile = await self._intelligence.extract_resume(parsed.text)
        safe_filename = Path(filename).name or "resume"
        document = ResumeDocument(
            filename=safe_filename,
            content_type=content_type or "application/octet-stream",
            sha256=digest,
            profile=profile,
        )
        try:
            await self._storage.save(document.id, content)
            await self._repository.add(document)
            await self._transaction.commit()
        except Exception as operation_error:
            recovery_errors: list[Exception] = [operation_error]
            try:
                await self._transaction.rollback()
            except Exception as rollback_error:
                recovery_errors.append(rollback_error)
            try:
                await self._storage.delete(document.id)
            except Exception as cleanup_error:
                recovery_errors.append(cleanup_error)
            if len(recovery_errors) > 1:
                raise ExceptionGroup(
                    "Resume upload failed and one or more recovery actions also failed",
                    recovery_errors,
                ) from operation_error
            raise
        return document, parsed.warnings

    async def get(self, document_id: UUID) -> ResumeDocument:
        document = await self._repository.get(document_id)
        if document is None:
            raise EntityNotFoundError("resume", str(document_id))
        return document

    async def delete(self, document_id: UUID) -> None:
        stored_content = await self._storage.load(document_id)
        storage_deleted = False
        try:
            deleted = await self._repository.delete(document_id)
            if not deleted:
                raise EntityNotFoundError("resume", str(document_id))
            await self._storage.delete(document_id)
            storage_deleted = True
            await self._transaction.commit()
        except EntityNotFoundError:
            raise
        except Exception as operation_error:
            recovery_errors: list[Exception] = [operation_error]
            try:
                await self._transaction.rollback()
            except Exception as rollback_error:
                recovery_errors.append(rollback_error)
            if storage_deleted and stored_content is not None:
                try:
                    await self._storage.save(document_id, stored_content)
                except Exception as recovery_error:
                    recovery_errors.append(recovery_error)
            if len(recovery_errors) > 1:
                raise ExceptionGroup(
                    "Resume deletion failed and one or more recovery actions also failed",
                    recovery_errors,
                ) from operation_error
            raise
