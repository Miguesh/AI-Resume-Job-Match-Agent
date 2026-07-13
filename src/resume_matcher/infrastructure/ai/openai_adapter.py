from __future__ import annotations

import json
import logging
from dataclasses import asdict

import openai
from openai import AsyncOpenAI

from resume_matcher.domain.entities import (
    JobProfile,
    MatchAnalysis,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.domain.exceptions import (
    IntelligenceProviderError,
    IntelligenceProviderUnavailableError,
)
from resume_matcher.infrastructure.ai.contracts import (
    JobExtractionContract,
    OptimizedResumeContract,
    ResumeExtractionContract,
)
from resume_matcher.infrastructure.ai.mappers import (
    job_from_contract,
    optimized_from_contract,
    resume_from_contract,
)
from resume_matcher.infrastructure.ai.prompts import (
    JOB_EXTRACTION_INSTRUCTIONS,
    OPTIMIZATION_INSTRUCTIONS,
    RESUME_EXTRACTION_INSTRUCTIONS,
)

logger = logging.getLogger(__name__)


class OpenAIResumeIntelligence:
    """Typed Responses API adapter; no OpenAI type crosses this boundary."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._model = model

    async def extract_resume(self, text: str) -> ResumeProfile:
        payload = json.dumps({"untrusted_resume_text": text}, ensure_ascii=False)
        parsed = await self._parse(
            instructions=RESUME_EXTRACTION_INSTRUCTIONS,
            payload=payload,
            contract=ResumeExtractionContract,
            operation="resume_extraction",
        )
        return resume_from_contract(parsed, text)

    async def extract_job(self, text: str) -> JobProfile:
        payload = json.dumps({"untrusted_job_description": text}, ensure_ascii=False)
        parsed = await self._parse(
            instructions=JOB_EXTRACTION_INSTRUCTIONS,
            payload=payload,
            contract=JobExtractionContract,
            operation="job_extraction",
        )
        return job_from_contract(parsed, text)

    async def optimize_resume(
        self,
        resume: ResumeProfile,
        job: JobProfile,
        match: MatchAnalysis,
    ) -> OptimizedResume:
        payload = json.dumps(
            {
                "source_resume": asdict(resume),
                "target_job": asdict(job),
                "verified_match_evidence": {
                    "matched_skills": match.result.matched_skills,
                    "missing_required_skills": match.result.missing_required_skills,
                    "missing_preferred_skills": match.result.missing_preferred_skills,
                    "matched_keywords": match.result.matched_keywords,
                },
            },
            ensure_ascii=False,
            default=str,
        )
        parsed = await self._parse(
            instructions=OPTIMIZATION_INSTRUCTIONS,
            payload=payload,
            contract=OptimizedResumeContract,
            operation="resume_optimization",
        )
        return optimized_from_contract(parsed)

    async def _parse[ContractT](
        self,
        *,
        instructions: str,
        payload: str,
        contract: type[ContractT],
        operation: str,
    ) -> ContractT:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "developer", "content": instructions},
                    {"role": "user", "content": payload},
                ],
                text_format=contract,
            )
        except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as exc:
            logger.warning(
                "OpenAI operation unavailable",
                extra={"event": "openai_unavailable", "operation": operation},
            )
            raise IntelligenceProviderUnavailableError(
                "The AI provider is temporarily unavailable; retry the request later"
            ) from exc
        except openai.APIStatusError as exc:
            logger.error(
                "OpenAI operation failed with status %s",
                exc.status_code,
                extra={"event": "openai_status_error", "operation": operation},
            )
            raise IntelligenceProviderError(
                "The AI provider rejected the request; verify provider configuration"
            ) from exc
        parsed = response.output_parsed
        if parsed is None:
            raise IntelligenceProviderError("The AI provider returned no structured result")
        return parsed
