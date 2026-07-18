"""Dependency-free Docker Compose smoke test used locally and in CI."""

from __future__ import annotations

import argparse
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import cast


def _request(
    base_url: str,
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, bytes, Mapping[str, str]]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(  # noqa: S310 - URL is an explicit local smoke target.
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {error.code}: {detail}") from error


def _json_request(
    base_url: str,
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    payload: Mapping[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode() if payload is not None else None
    status, raw_body, _ = _request(
        base_url,
        api_key,
        path,
        method=method,
        body=body,
        content_type="application/json" if body is not None else None,
    )
    decoded = json.loads(raw_body)
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{method} {path} returned a non-object JSON response")
    return status, cast(dict[str, object], decoded)


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Response field '{key}' is missing or invalid")
    return value


def _minimal_docx(text: str) -> bytes:
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines()
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _upload_resume(base_url: str, api_key: str) -> dict[str, object]:
    resume_text = """Alex Example
Senior Backend Engineer
alex.example@example.com | New York, NY

Summary
Backend engineer with 6 years of experience building reliable production APIs.

Skills
Python, FastAPI, PostgreSQL, Docker, pytest, GitHub Actions

Senior Backend Engineer at Example Labs | 2020 - Present
- Built Python and FastAPI services for internal teams.
- Reduced API latency by 35 percent using PostgreSQL query optimization.
- Added pytest integration tests and GitHub Actions CI/CD.

Bachelor of Science in Computer Science
Example University
"""
    boundary = f"----resume-smoke-{uuid.uuid4().hex}"
    document = _minimal_docx(resume_text)
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="synthetic-resume.docx"\r\n'
            "Content-Type: application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document\r\n"
            "\r\n"
        ).encode()
        + document
        + f"\r\n--{boundary}--\r\n".encode()
    )
    status, raw_body, _ = _request(
        base_url,
        api_key,
        "/api/v1/resumes",
        method="POST",
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    if status != 201:
        raise RuntimeError(f"Resume upload returned unexpected HTTP {status}")
    decoded = json.loads(raw_body)
    if not isinstance(decoded, dict):
        raise RuntimeError("Resume upload returned a non-object JSON response")
    return cast(dict[str, object], decoded)


def _wait_until_ready(base_url: str) -> None:
    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(  # noqa: S310 - explicit local smoke target.
                f"{base_url.rstrip('/')}/api/v1/health/ready"
            )
            with urllib.request.urlopen(request, timeout=3) as response:  # noqa: S310
                payload = json.loads(response.read())
                if response.status == 200 and payload.get("status") == "ok":
                    return
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = error
        time.sleep(2)
    raise RuntimeError("API did not become migration-ready before the timeout") from last_error


def exercise(base_url: str, api_key: str, state_file: Path) -> None:
    _wait_until_ready(base_url)
    resume = _upload_resume(base_url, api_key)
    resume_id = _required_string(resume, "id")

    job_text = (
        "Senior Backend Engineer role requiring Python, FastAPI, PostgreSQL, Docker, pytest, "
        "and five years of production API experience. The engineer designs reliable services, "
        "improves database performance, owns CI/CD quality, and collaborates with product teams."
    )
    job_status, job = _json_request(
        base_url,
        api_key,
        "/api/v1/jobs",
        method="POST",
        payload={"job_description": job_text},
    )
    if job_status != 201:
        raise RuntimeError(f"Job creation returned unexpected HTTP {job_status}")
    job_id = _required_string(job, "id")

    match_status, match = _json_request(
        base_url,
        api_key,
        "/api/v1/matches",
        method="POST",
        payload={"resume_id": resume_id, "job_id": job_id},
    )
    if match_status != 201:
        raise RuntimeError(f"Match creation returned unexpected HTTP {match_status}")
    match_id = _required_string(match, "id")

    optimize_status, optimized = _json_request(
        base_url,
        api_key,
        f"/api/v1/matches/{match_id}/optimize",
        method="POST",
    )
    if optimize_status != 200 or optimized.get("optimized_resume") is None:
        raise RuntimeError("Local resume optimization did not return an optimized draft")

    signatures = {"json": b"{", "docx": b"PK", "pdf": b"%PDF"}
    for format_name, signature in signatures.items():
        status, content, headers = _request(
            base_url,
            api_key,
            f"/api/v1/matches/{match_id}/exports/{format_name}",
        )
        if status != 200 or not content.startswith(signature):
            raise RuntimeError(f"{format_name.upper()} export was empty or invalid")
        if "attachment" not in headers.get("Content-Disposition", ""):
            raise RuntimeError(f"{format_name.upper()} export omitted attachment metadata")

    state_file.write_text(
        json.dumps({"resume_id": resume_id, "job_id": job_id, "match_id": match_id}),
        encoding="utf-8",
    )


def verify(base_url: str, api_key: str, state_file: Path) -> None:
    _wait_until_ready(base_url)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise RuntimeError("Smoke-test state file is invalid")
    for resource, path in (
        ("resume_id", "/api/v1/resumes/"),
        ("job_id", "/api/v1/jobs/"),
        ("match_id", "/api/v1/matches/"),
    ):
        identifier = _required_string(state, resource)
        status, payload = _json_request(base_url, api_key, f"{path}{identifier}")
        if status != 200 or payload.get("id") != identifier:
            raise RuntimeError(f"Persisted {resource} was unavailable after API restart")
    match_id = _required_string(state, "match_id")
    _, match = _json_request(base_url, api_key, f"/api/v1/matches/{match_id}")
    if match.get("optimized_resume") is None:
        raise RuntimeError("Optimized resume was not persisted across API restart")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("exercise", "verify"))
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    base_url = os.getenv("SMOKE_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("APP_API_KEYS", "")
    if not api_key:
        raise RuntimeError("APP_API_KEYS is required for the production smoke test")
    if args.phase == "exercise":
        exercise(base_url, api_key, args.state_file)
    else:
        verify(base_url, api_key, args.state_file)


if __name__ == "__main__":
    main()
