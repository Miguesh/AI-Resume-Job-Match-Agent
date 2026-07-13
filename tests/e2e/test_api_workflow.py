from __future__ import annotations

import io
import json

import httpx
import pytest
from docx import Document
from pypdf import PdfReader
from tests.conftest import make_docx


@pytest.mark.integration
async def test_complete_resume_matching_and_export_workflow(
    api_client: httpx.AsyncClient,
    resume_text: str,
    job_description_text: str,
) -> None:
    upload = await api_client.post(
        "/api/v1/resumes",
        files={
            "file": (
                "miguel-resume.docx",
                make_docx(resume_text),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    resume = upload.json()
    assert resume["profile"]["name"] == "Miguel Candidate"
    assert {skill["normalized_name"] for skill in resume["profile"]["skills"]} >= {
        "python",
        "fastapi",
        "docker",
    }
    assert upload.headers["x-content-type-options"] == "nosniff"
    assert upload.headers["cache-control"] == "no-store"
    assert upload.headers["x-request-id"]

    job_response = await api_client.post(
        "/api/v1/jobs",
        json={"job_description": job_description_text},
    )
    assert job_response.status_code == 201, job_response.text
    job = job_response.json()
    assert job["profile"]["title"] == "Senior AI Engineer"
    assert "kubernetes" in {skill["normalized_name"] for skill in job["profile"]["required_skills"]}
    assert "langchain" in {skill["normalized_name"] for skill in job["profile"]["preferred_skills"]}

    match_response = await api_client.post(
        "/api/v1/matches",
        json={"resume_id": resume["id"], "job_id": job["id"]},
    )
    assert match_response.status_code == 201, match_response.text
    analysis = match_response.json()
    assert 0 < analysis["result"]["overall_score"] < 100
    assert analysis["result"]["score_version"] == "1.0.0"
    assert "Kubernetes" in analysis["result"]["missing_required_skills"]
    assert len(analysis["result"]["dimensions"]) == 5
    assert round(sum(item["weight"] for item in analysis["result"]["dimensions"]), 6) == 1

    optimized_response = await api_client.post(f"/api/v1/matches/{analysis['id']}/optimize")
    assert optimized_response.status_code == 200, optimized_response.text
    optimized = optimized_response.json()["optimized_resume"]
    assert optimized is not None
    assert "Kubernetes" not in {skill["name"] for skill in optimized["skills"]}
    assert optimized["changes"]
    assert optimized["warnings"]

    json_export = await api_client.get(f"/api/v1/matches/{analysis['id']}/exports/json")
    assert json_export.status_code == 200
    report = json.loads(json_export.content)
    assert report["schema_version"] == "1.0.0"
    assert report["optimized"] is True
    assert report["match_analysis"]["overall_score"] == analysis["result"]["overall_score"]
    assert "attachment" in json_export.headers["content-disposition"]

    docx_export = await api_client.get(f"/api/v1/matches/{analysis['id']}/exports/docx")
    assert docx_export.status_code == 200
    exported_docx = Document(io.BytesIO(docx_export.content))
    docx_text = "\n".join(paragraph.text for paragraph in exported_docx.paragraphs)
    assert "Miguel Candidate" in docx_text
    assert "CORE SKILLS" in docx_text
    assert "Kubernetes" not in docx_text

    pdf_export = await api_client.get(f"/api/v1/matches/{analysis['id']}/exports/pdf")
    assert pdf_export.status_code == 200
    pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_export.content)).pages
    )
    assert "Miguel Candidate" in pdf_text
    assert "CORE SKILLS" in pdf_text

    stored_match = await api_client.get(f"/api/v1/matches/{analysis['id']}")
    assert stored_match.status_code == 200
    assert stored_match.json()["optimized_resume"] is not None

    deletion = await api_client.delete(f"/api/v1/resumes/{resume['id']}")
    assert deletion.status_code == 200
    assert deletion.json() == {"deleted": True}
    missing = await api_client.get(f"/api/v1/resumes/{resume['id']}")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")
    cascaded_match = await api_client.get(f"/api/v1/matches/{analysis['id']}")
    assert cascaded_match.status_code == 404
