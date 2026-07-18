from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from resume_matcher.application.dto import ParsedDocument
from resume_matcher.application.services.job_service import JobService
from resume_matcher.application.services.match_service import MatchService
from resume_matcher.application.services.resume_service import ResumeService
from resume_matcher.domain.entities import (
    JobDescription,
    JobProfile,
    MatchAnalysis,
    OptimizedResume,
    ResumeDocument,
    ResumeProfile,
)
from resume_matcher.domain.exceptions import EntityNotFoundError
from resume_matcher.domain.fact_guard import ResumeFactGuard
from resume_matcher.domain.matching import MatchingService


def _resume_document(profile: ResumeProfile) -> ResumeDocument:
    return ResumeDocument(
        filename="resume.docx",
        content_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        sha256="0" * 64,
        profile=profile,
    )


async def test_resume_upload_returns_existing_duplicate_without_reprocessing(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    existing = _resume_document(resume_factory())
    parser = Mock()
    intelligence = AsyncMock()
    repository = AsyncMock()
    repository.find_by_sha256.return_value = existing
    service = ResumeService(
        parser=parser,
        storage=AsyncMock(),
        intelligence=intelligence,
        repository=repository,
        transaction=AsyncMock(),
    )

    result, warnings = await service.upload(
        filename="resume.docx",
        content_type=existing.content_type,
        content=b"same bytes",
    )

    assert result is existing
    assert "identical resume" in warnings[0]
    parser.parse.assert_not_called()
    intelligence.extract_resume.assert_not_awaited()


async def test_resume_upload_rolls_back_and_removes_file_when_commit_fails(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    parser = Mock()
    parser.parse.return_value = ParsedDocument(text="Synthetic resume", warnings=("warning",))
    intelligence = AsyncMock()
    intelligence.extract_resume.return_value = resume_factory()
    repository = AsyncMock()
    repository.find_by_sha256.return_value = None
    storage = AsyncMock()
    transaction = AsyncMock()
    transaction.commit.side_effect = RuntimeError("database unavailable")
    service = ResumeService(
        parser=parser,
        storage=storage,
        intelligence=intelligence,
        repository=repository,
        transaction=transaction,
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.upload(
            filename="../unsafe-name.docx",
            content_type=None,
            content=b"new resume",
        )

    transaction.rollback.assert_awaited_once()
    stored_id = storage.save.await_args.args[0]
    storage.delete.assert_awaited_once_with(stored_id)
    document = repository.add.await_args.args[0]
    assert document.filename == "unsafe-name.docx"


async def test_resume_upload_cleanup_runs_even_when_rollback_fails(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    parser = Mock()
    parser.parse.return_value = ParsedDocument(text="Synthetic resume")
    intelligence = AsyncMock()
    intelligence.extract_resume.return_value = resume_factory()
    repository = AsyncMock()
    repository.find_by_sha256.return_value = None
    storage = AsyncMock()
    transaction = AsyncMock()
    transaction.commit.side_effect = RuntimeError("commit failed")
    transaction.rollback.side_effect = RuntimeError("rollback failed")
    service = ResumeService(
        parser=parser,
        storage=storage,
        intelligence=intelligence,
        repository=repository,
        transaction=transaction,
    )

    with pytest.raises(ExceptionGroup) as error:
        await service.upload(filename="resume.docx", content_type=None, content=b"resume")

    assert len(error.value.exceptions) == 2
    storage.delete.assert_awaited_once()


async def test_resume_delete_rolls_back_when_storage_deletion_fails() -> None:
    repository = AsyncMock()
    repository.delete.return_value = True
    storage = AsyncMock()
    storage.load.return_value = b"original resume"
    storage.delete.side_effect = OSError("volume unavailable")
    transaction = AsyncMock()
    service = ResumeService(
        parser=Mock(),
        storage=storage,
        intelligence=AsyncMock(),
        repository=repository,
        transaction=transaction,
    )

    with pytest.raises(OSError, match="volume unavailable"):
        await service.delete(uuid4())

    transaction.rollback.assert_awaited_once()
    transaction.commit.assert_not_awaited()
    storage.save.assert_not_awaited()


async def test_resume_delete_restores_file_when_commit_fails() -> None:
    document_id = uuid4()
    repository = AsyncMock()
    repository.delete.return_value = True
    storage = AsyncMock()
    storage.load.return_value = b"original resume"
    transaction = AsyncMock()
    transaction.commit.side_effect = RuntimeError("commit failed")
    service = ResumeService(
        parser=Mock(),
        storage=storage,
        intelligence=AsyncMock(),
        repository=repository,
        transaction=transaction,
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.delete(document_id)

    transaction.rollback.assert_awaited_once()
    storage.delete.assert_awaited_once_with(document_id)
    storage.save.assert_awaited_once_with(document_id, b"original resume")


async def test_resume_delete_restores_file_even_when_rollback_fails() -> None:
    document_id = uuid4()
    repository = AsyncMock()
    repository.delete.return_value = True
    storage = AsyncMock()
    storage.load.return_value = b"original resume"
    transaction = AsyncMock()
    transaction.commit.side_effect = RuntimeError("commit failed")
    transaction.rollback.side_effect = RuntimeError("rollback failed")
    service = ResumeService(
        parser=Mock(),
        storage=storage,
        intelligence=AsyncMock(),
        repository=repository,
        transaction=transaction,
    )

    with pytest.raises(ExceptionGroup) as error:
        await service.delete(document_id)

    assert len(error.value.exceptions) == 2
    storage.save.assert_awaited_once_with(document_id, b"original resume")


async def test_job_create_rolls_back_when_commit_fails(
    job_factory: Callable[..., JobProfile],
) -> None:
    intelligence = AsyncMock()
    intelligence.extract_job.return_value = job_factory()
    repository = AsyncMock()
    transaction = AsyncMock()
    transaction.commit.side_effect = RuntimeError("commit failed")
    service = JobService(
        intelligence=intelligence,
        repository=repository,
        transaction=transaction,
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.create("Synthetic job description")

    repository.add.assert_awaited_once()
    transaction.rollback.assert_awaited_once()


async def test_match_create_rejects_missing_job_before_persistence(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    resume = _resume_document(resume_factory())
    resumes = AsyncMock()
    resumes.get.return_value = resume
    jobs = AsyncMock()
    jobs.get.return_value = None
    matches = AsyncMock()
    transaction = AsyncMock()
    service = MatchService(
        resumes=resumes,
        jobs=jobs,
        matches=matches,
        transaction=transaction,
        matcher=MatchingService(),
        intelligence=AsyncMock(),
        fact_guard=ResumeFactGuard(),
    )

    with pytest.raises(EntityNotFoundError, match="job description"):
        await service.create(resume_id=resume.id, job_id=uuid4())

    matches.add.assert_not_awaited()
    transaction.commit.assert_not_awaited()


async def test_match_optimization_rolls_back_when_update_commit_fails(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
    optimized_resume: OptimizedResume,
) -> None:
    resume = _resume_document(resume_factory())
    job = JobDescription(profile=job_factory())
    analysis = MatchAnalysis(
        resume_id=resume.id,
        job_id=job.id,
        result=MatchingService().score(resume.profile, job.profile),
    )
    resumes = AsyncMock()
    resumes.get.return_value = resume
    jobs = AsyncMock()
    jobs.get.return_value = job
    matches = AsyncMock()
    matches.get.return_value = analysis
    intelligence = AsyncMock()
    intelligence.optimize_resume.return_value = optimized_resume
    transaction = AsyncMock()
    transaction.commit.side_effect = RuntimeError("commit failed")
    service = MatchService(
        resumes=resumes,
        jobs=jobs,
        matches=matches,
        transaction=transaction,
        matcher=MatchingService(),
        intelligence=intelligence,
        fact_guard=ResumeFactGuard(),
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.optimize(analysis.id)

    matches.update.assert_awaited_once()
    transaction.rollback.assert_awaited_once()
