from __future__ import annotations

import os
from uuid import uuid4

import pytest

from resume_matcher.domain.entities import MatchAnalysis
from resume_matcher.domain.fact_guard import ResumeFactGuard
from resume_matcher.domain.matching import MatchingService
from resume_matcher.infrastructure.ai.openai_adapter import OpenAIResumeIntelligence

_LIVE_TEST_DISABLED = os.getenv("RUN_EXTERNAL_TESTS") != "1" or not os.getenv("OPENAI_API_KEY")


def _adapter() -> OpenAIResumeIntelligence:
    return OpenAIResumeIntelligence(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        timeout_seconds=60,
        max_retries=2,
        max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "16000")),
    )


@pytest.mark.external
@pytest.mark.skipif(
    _LIVE_TEST_DISABLED,
    reason="Set RUN_EXTERNAL_TESTS=1 and OPENAI_API_KEY to run the live provider test",
)
async def test_openai_structured_job_extraction() -> None:
    adapter = _adapter()
    result = await adapter.extract_job(
        "Senior Python Engineer. Required: Python and FastAPI. Preferred: Docker. "
        "Build reliable APIs with at least 4 years of experience."
    )
    assert result.title
    assert {skill.normalized_name for skill in result.required_skills} >= {
        "python",
        "fastapi",
    }


@pytest.mark.external
@pytest.mark.skipif(
    _LIVE_TEST_DISABLED,
    reason="Set RUN_EXTERNAL_TESTS=1 and OPENAI_API_KEY to run the live provider test",
)
async def test_openai_optimization_contract_passes_fact_guard_end_to_end() -> None:
    adapter = _adapter()
    resume = await adapter.extract_resume(
        """Alex Example
Senior Backend Engineer
alex.example@example.com | New York, NY

Summary
Backend engineer with 6 years of experience building reliable APIs.

Skills
Python, FastAPI, PostgreSQL, Docker, pytest

Senior Backend Engineer at Example Labs | 2020 - Present
- Built Python and FastAPI services for internal teams.
- Reduced API latency by 35 percent using PostgreSQL query optimization.
- Added pytest integration tests and containerized services with Docker.

Bachelor of Science in Computer Science, Example University, 2020
"""
    )
    job = await adapter.extract_job(
        """Senior Backend Engineer
Required: Python, FastAPI, PostgreSQL, Docker, and automated testing.
At least 5 years of experience building production APIs.
Design reliable services, improve database performance, and maintain CI quality.
"""
    )
    analysis = MatchAnalysis(
        resume_id=uuid4(),
        job_id=uuid4(),
        result=MatchingService().score(resume, job),
    )

    optimized = await adapter.optimize_resume(resume, job, analysis)

    ResumeFactGuard().validate(resume, optimized)
