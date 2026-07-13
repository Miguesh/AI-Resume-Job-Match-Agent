from __future__ import annotations

import io
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from docx import Document
from fastapi import FastAPI
from reportlab.pdfgen import canvas

from resume_matcher.app import create_app
from resume_matcher.config.settings import AppEnvironment, Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env=AppEnvironment.TEST,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        storage_path=tmp_path / "uploads",
        log_json=False,
        app_rate_limit_per_minute=1_000,
        app_allowed_hosts=("testserver",),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.fixture
def resume_text() -> str:
    return """Miguel Candidate
Senior AI Engineer
miguel.candidate@example.com | +1 212 555 0100 | New York, NY

Summary
AI engineer with 6 years of experience building reliable machine learning products.

Skills
Python, FastAPI, Pydantic, PostgreSQL, SQLAlchemy, Docker, AWS, pytest, GitHub Actions

Senior AI Engineer at Acme Corp | 2020 - Present
- Built Python and FastAPI services used by internal recruiting teams.
- Containerized APIs with Docker and deployed workloads on AWS.
- Added pytest integration testing and GitHub Actions CI/CD.

Bachelor of Science in Computer Science
State University
"""


@pytest.fixture
def job_description_text() -> str:
    return """Senior AI Engineer at ExampleCo

We are hiring an engineer with 5+ years of experience to design and deliver production AI APIs.
Required skills: Python, FastAPI, Pydantic, Docker, PostgreSQL, Kubernetes.
Preferred: AWS and LangChain experience.
Bachelor's degree in Computer Science or equivalent experience.

Build reliable machine learning services and REST API integrations.
Design maintainable systems, write integration tests, and own CI/CD delivery.
Collaborate with product partners and explain technical decisions clearly.
"""


def make_docx(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def make_pdf(text: str) -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    text_object = pdf.beginText(48, 800)
    for line in text.splitlines():
        text_object.textLine(line)
    pdf.drawText(text_object)
    pdf.save()
    return output.getvalue()
