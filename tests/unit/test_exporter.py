from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import replace

import fitz
import pytest
from docx import Document

from resume_matcher.domain.entities import (
    JobProfile,
    MatchAnalysis,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.infrastructure.export.resume_exporter import MultiFormatResumeExporter


def test_json_export_contains_versioned_complete_analysis(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
    match_analysis: MatchAnalysis,
) -> None:
    resume = resume_factory()
    job = job_factory()

    artifact = MultiFormatResumeExporter().export(
        format_name="JSON", resume=resume, match=match_analysis, job=job
    )
    payload = json.loads(artifact.content)

    assert artifact.media_type == "application/json"
    assert artifact.filename == f"resume-analysis-{match_analysis.id}.json"
    assert payload["schema_version"] == "1.0.0"
    assert payload["generated_at"].endswith("+00:00")
    assert payload["resume"]["name"] == "Jane Doe"
    assert payload["target_job"]["title"] == "Senior API Engineer"
    assert payload["match_analysis"]["overall_score"] == 60.0
    assert payload["match_analysis"]["score_version"] == "1.0.0"
    assert payload["optimized"] is False


def test_docx_export_is_valid_and_contains_resume_sections(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
    match_analysis: MatchAnalysis,
) -> None:
    artifact = MultiFormatResumeExporter().export(
        format_name="docx",
        resume=resume_factory(),
        match=match_analysis,
        job=job_factory(),
    )

    assert artifact.content.startswith(b"PK")
    assert artifact.media_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = Document(io.BytesIO(artifact.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Jane Doe" in text
    assert "PROFESSIONAL SUMMARY" in text
    assert "CORE SKILLS" in text
    assert "EXPERIENCE" in text
    assert "Senior Engineer | Acme" in text
    assert "Reduced processing latency by 35 percent." in text
    assert "EDUCATION" in text
    assert "CERTIFICATIONS" in text
    assert round(document.sections[0].top_margin.inches, 2) == 0.6


def test_pdf_export_is_valid_searchable_and_escapes_user_content(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
    match_analysis: MatchAnalysis,
) -> None:
    resume = resume_factory(
        name="Jane & Doe",
        summary="Built <safe> APIs & reliable platforms.",
    )
    artifact = MultiFormatResumeExporter().export(
        format_name="pdf", resume=resume, match=match_analysis, job=job_factory()
    )

    assert artifact.content.startswith(b"%PDF-")
    assert artifact.media_type == "application/pdf"
    with fitz.open(stream=artifact.content, filetype="pdf") as document:
        assert document.page_count >= 1
        text = "\n".join(page.get_text() for page in document)
        assert "Jane & Doe" in text
        assert "Built <safe> APIs & reliable platforms." in text
        assert "Page 1" in text
        assert document.metadata["title"] == "Resume - Jane & Doe"


def test_optimized_export_uses_optimized_filename_and_content(
    job_factory: Callable[..., JobProfile],
    match_analysis: MatchAnalysis,
    optimized_resume: OptimizedResume,
) -> None:
    analysis = replace(match_analysis, optimized_resume=optimized_resume)

    artifact = MultiFormatResumeExporter().export(
        format_name="json",
        resume=optimized_resume,
        match=analysis,
        job=job_factory(),
    )
    payload = json.loads(artifact.content)

    assert artifact.filename == f"optimized-resume-{analysis.id}.json"
    assert payload["optimized"] is True
    assert payload["resume"]["summary"] == "Platform engineer focused on reliable APIs."
    assert payload["resume"]["changes"][0]["source_evidence"] == ["Build reliable APIs"]


def test_export_rejects_unknown_format(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
    match_analysis: MatchAnalysis,
) -> None:
    with pytest.raises(ValueError, match="Unsupported export format 'txt'"):
        MultiFormatResumeExporter().export(
            format_name="txt",
            resume=resume_factory(),
            match=match_analysis,
            job=job_factory(),
        )
