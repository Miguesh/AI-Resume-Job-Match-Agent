from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from resume_matcher.application.ports import ResumeIntelligence
from resume_matcher.application.services.job_service import JobService
from resume_matcher.application.services.match_service import ExportService, MatchService
from resume_matcher.application.services.resume_service import ResumeService
from resume_matcher.config.settings import AIProvider, Settings
from resume_matcher.domain.exceptions import ConfigurationError
from resume_matcher.domain.fact_guard import ResumeFactGuard
from resume_matcher.domain.matching import MatchingService
from resume_matcher.infrastructure.ai.local import LocalResumeIntelligence
from resume_matcher.infrastructure.ai.openai_adapter import OpenAIResumeIntelligence
from resume_matcher.infrastructure.export.resume_exporter import MultiFormatResumeExporter
from resume_matcher.infrastructure.parsing.document_parser import SecureDocumentParser
from resume_matcher.infrastructure.persistence.database import (
    Database,
    SqlAlchemyTransactionManager,
)
from resume_matcher.infrastructure.persistence.repositories import (
    SqlAlchemyJobRepository,
    SqlAlchemyMatchRepository,
    SqlAlchemyResumeRepository,
)
from resume_matcher.infrastructure.rate_limit import InMemoryRateLimiter
from resume_matcher.infrastructure.storage import FileSystemDocumentStorage


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    database: Database
    parser: SecureDocumentParser
    storage: FileSystemDocumentStorage
    intelligence: ResumeIntelligence
    matcher: MatchingService
    fact_guard: ResumeFactGuard
    exporter: MultiFormatResumeExporter
    rate_limiter: InMemoryRateLimiter

    @classmethod
    def build(cls, settings: Settings) -> AppContainer:
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        if settings.ai_provider is AIProvider.OPENAI:
            if not api_key:
                raise ConfigurationError(
                    "OPENAI_API_KEY is required when AI_PROVIDER is configured as openai"
                )
            intelligence: ResumeIntelligence = OpenAIResumeIntelligence(
                api_key=api_key,
                model=settings.openai_model,
                timeout_seconds=settings.openai_timeout_seconds,
                max_retries=settings.openai_max_retries,
                max_output_tokens=settings.openai_max_output_tokens,
            )
        else:
            intelligence = LocalResumeIntelligence()
        return cls(
            settings=settings,
            database=Database(
                settings.database_url.get_secret_value(), echo=settings.database_echo
            ),
            parser=SecureDocumentParser(max_bytes=settings.app_max_upload_bytes),
            storage=FileSystemDocumentStorage(settings.storage_path),
            intelligence=intelligence,
            matcher=MatchingService(),
            fact_guard=ResumeFactGuard(),
            exporter=MultiFormatResumeExporter(),
            rate_limiter=InMemoryRateLimiter(settings.app_rate_limit_per_minute),
        )

    def resume_service(self, session: AsyncSession) -> ResumeService:
        return ResumeService(
            parser=self.parser,
            storage=self.storage,
            intelligence=self.intelligence,
            repository=SqlAlchemyResumeRepository(session),
            transaction=SqlAlchemyTransactionManager(session),
        )

    def job_service(self, session: AsyncSession) -> JobService:
        return JobService(
            intelligence=self.intelligence,
            repository=SqlAlchemyJobRepository(session),
            transaction=SqlAlchemyTransactionManager(session),
        )

    def match_service(self, session: AsyncSession) -> MatchService:
        return MatchService(
            resumes=SqlAlchemyResumeRepository(session),
            jobs=SqlAlchemyJobRepository(session),
            matches=SqlAlchemyMatchRepository(session),
            transaction=SqlAlchemyTransactionManager(session),
            matcher=self.matcher,
            intelligence=self.intelligence,
            fact_guard=self.fact_guard,
        )

    def export_service(self, session: AsyncSession) -> ExportService:
        return ExportService(
            resumes=SqlAlchemyResumeRepository(session),
            jobs=SqlAlchemyJobRepository(session),
            matches=SqlAlchemyMatchRepository(session),
            exporter=self.exporter,
        )
