from __future__ import annotations

from fastapi import FastAPI


def test_openapi_contract_documents_core_workflow(app: FastAPI) -> None:
    schema = app.openapi()
    assert schema["info"]["title"] == "AI Resume & Job Match Agent"
    assert schema["info"]["license"]["identifier"] == "MIT"
    paths = schema["paths"]
    assert "/api/v1/resumes" in paths
    assert "/api/v1/jobs" in paths
    assert "/api/v1/matches" in paths
    assert "/api/v1/matches/{match_id}/optimize" in paths
    assert "/api/v1/matches/{match_id}/exports/{format_name}" in paths
    security_schemes = schema["components"]["securitySchemes"]
    assert security_schemes["Application API key"]["scheme"] == "bearer"


def test_every_operation_has_a_summary_and_tag(app: FastAPI) -> None:
    schema = app.openapi()
    for path in schema["paths"].values():
        for method, operation in path.items():
            if method == "parameters":
                continue
            assert operation.get("summary")
            assert operation.get("tags")
