from __future__ import annotations

import os

import pytest

from resume_matcher.infrastructure.ai.openai_adapter import OpenAIResumeIntelligence


@pytest.mark.external
@pytest.mark.skipif(
    os.getenv("RUN_EXTERNAL_TESTS") != "1" or not os.getenv("OPENAI_API_KEY"),
    reason="Set RUN_EXTERNAL_TESTS=1 and OPENAI_API_KEY to run the live provider test",
)
async def test_openai_structured_job_extraction() -> None:
    adapter = OpenAIResumeIntelligence(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        timeout_seconds=60,
        max_retries=2,
    )
    result = await adapter.extract_job(
        "Senior Python Engineer. Required: Python and FastAPI. Preferred: Docker. "
        "Build reliable APIs with at least 4 years of experience."
    )
    assert result.title
    assert {skill.normalized_name for skill in result.required_skills} >= {
        "python",
        "fastapi",
    }
