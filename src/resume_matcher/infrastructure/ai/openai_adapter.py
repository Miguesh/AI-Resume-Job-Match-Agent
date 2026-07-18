from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict

import openai
import pydantic
from openai import AsyncOpenAI
from openai.types.responses import ParsedResponse

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

_TERMINAL_ERROR_STATUSES = frozenset({"cancelled", "failed"})
_NON_TERMINAL_STATUSES = frozenset({"in_progress", "queued"})
_RETRYABLE_RESPONSE_ERROR_CODES = frozenset(
    {"rate_limit_exceeded", "server_error", "vector_store_timeout"}
)


class OpenAIResumeIntelligence:
    """Typed Responses API adapter; no OpenAI type crosses this boundary."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int = 16_000,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._model = model
        self._max_output_tokens = max_output_tokens

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
        target_job = asdict(job)
        # Structured criteria are sufficient for tailoring; omitting the original job text
        # avoids paying for the same evidence twice and reduces prompt-injection surface.
        target_job.pop("raw_text", None)
        payload = json.dumps(
            {
                "source_resume": asdict(resume),
                "target_job": target_job,
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
        started = time.perf_counter()
        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "developer", "content": instructions},
                    {"role": "user", "content": payload},
                ],
                text_format=contract,
                max_output_tokens=self._max_output_tokens,
                store=False,
            )
        except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError) as exc:
            logger.warning(
                "OpenAI operation unavailable",
                extra={
                    "event": "openai_unavailable",
                    "operation": operation,
                    "duration_ms": _elapsed_ms(started),
                },
            )
            raise IntelligenceProviderUnavailableError(
                "The AI provider is temporarily unavailable; retry the request later"
            ) from exc
        except openai.APIStatusError as exc:
            log_context = {
                "operation": operation,
                "status_code": exc.status_code,
                "duration_ms": _elapsed_ms(started),
            }
            if exc.status_code >= 500 or exc.status_code in {408, 409}:
                logger.warning(
                    "OpenAI operation unavailable",
                    extra={"event": "openai_unavailable", **log_context},
                )
                raise IntelligenceProviderUnavailableError(
                    "The AI provider is temporarily unavailable; retry the request later"
                ) from exc
            logger.error(
                "OpenAI operation failed",
                extra={"event": "openai_status_error", **log_context},
            )
            raise IntelligenceProviderError(
                "The AI provider rejected the request; verify provider configuration"
            ) from exc
        except openai.OpenAIError as exc:
            logger.error(
                "OpenAI SDK response error",
                extra={
                    "event": "openai_sdk_error",
                    "operation": operation,
                    "duration_ms": _elapsed_ms(started),
                },
            )
            raise IntelligenceProviderError(
                "The AI provider returned an invalid protocol response"
            ) from exc
        except (pydantic.ValidationError, json.JSONDecodeError) as exc:
            logger.warning(
                "OpenAI structured response violated its contract",
                extra={
                    "event": "openai_contract_error",
                    "operation": operation,
                    "duration_ms": _elapsed_ms(started),
                },
            )
            raise IntelligenceProviderError(
                "The AI provider returned a result that violated the expected contract"
            ) from exc

        _log_response(response, operation=operation, duration_ms=_elapsed_ms(started))

        if response.status == "incomplete":
            reason = response.incomplete_details.reason if response.incomplete_details else None
            logger.warning(
                "OpenAI operation returned an incomplete response",
                extra={
                    "event": "openai_incomplete",
                    "operation": operation,
                    "provider_status": "incomplete",
                },
            )
            if reason == "max_output_tokens":
                detail = "The AI provider response exceeded the configured output-token limit"
            elif reason == "content_filter":
                detail = (
                    "The AI provider could not complete the response because of content filtering"
                )
            else:
                detail = "The AI provider returned an incomplete response"
            raise IntelligenceProviderError(detail)

        if (
            response.status == "failed"
            and response.error
            and response.error.code in _RETRYABLE_RESPONSE_ERROR_CODES
        ):
            logger.warning(
                "OpenAI operation failed with a retryable response error",
                extra={
                    "event": "openai_unavailable",
                    "operation": operation,
                    "provider_status": "failed",
                },
            )
            raise IntelligenceProviderUnavailableError(
                "The AI provider is temporarily unavailable; retry the request later"
            )

        if response.status in _TERMINAL_ERROR_STATUSES:
            logger.warning(
                "OpenAI operation did not complete successfully",
                extra={
                    "event": "openai_response_error",
                    "operation": operation,
                    "provider_status": response.status,
                },
            )
            raise IntelligenceProviderError("The AI provider could not complete the request")

        if response.status in _NON_TERMINAL_STATUSES:
            logger.warning(
                "OpenAI operation returned an unexpected non-terminal response",
                extra={
                    "event": "openai_response_error",
                    "operation": operation,
                    "provider_status": response.status,
                },
            )
            raise IntelligenceProviderError("The AI provider returned an unexpected response state")

        if _contains_refusal(response):
            logger.info(
                "OpenAI declined to produce a structured response",
                extra={"event": "openai_refusal", "operation": operation},
            )
            raise IntelligenceProviderError("The AI provider declined to process this content")

        parsed = response.output_parsed
        if parsed is None or not isinstance(parsed, contract):
            logger.warning(
                "OpenAI response contained no valid structured result",
                extra={"event": "openai_contract_error", "operation": operation},
            )
            raise IntelligenceProviderError("The AI provider returned no valid structured result")
        return parsed


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _contains_refusal[ContractT](response: ParsedResponse[ContractT]) -> bool:
    return any(
        content.type == "refusal"
        for output in response.output
        if output.type == "message"
        for content in output.content
    )


def _log_response[ContractT](
    response: ParsedResponse[ContractT], *, operation: str, duration_ms: float
) -> None:
    usage = response.usage
    logger.info(
        "OpenAI operation finished",
        extra={
            "event": "openai_response",
            "operation": operation,
            "provider_status": response.status or "unknown",
            "duration_ms": duration_ms,
            "input_tokens": usage.input_tokens if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
            "cached_input_tokens": usage.input_tokens_details.cached_tokens if usage else None,
            "reasoning_tokens": usage.output_tokens_details.reasoning_tokens if usage else None,
        },
    )
