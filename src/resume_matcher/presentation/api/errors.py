from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from resume_matcher.domain.exceptions import (
    DocumentTooLargeError,
    EntityNotFoundError,
    FactualIntegrityError,
    IntelligenceProviderError,
    IntelligenceProviderUnavailableError,
    InvalidDocumentError,
    ResumeMatcherError,
    UnsupportedDocumentError,
)
from resume_matcher.infrastructure.logging import request_id_context

logger = logging.getLogger(__name__)


def _problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": f"urn:resume-matcher:error:{code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id_context.get(),
    }
    if errors:
        content["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(content),
        media_type="application/problem+json",
        headers=headers,
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EntityNotFoundError)
    async def not_found(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        return _problem(
            request,
            status_code=404,
            code=exc.code,
            title="Resource not found",
            detail=str(exc),
        )

    @app.exception_handler(DocumentTooLargeError)
    async def too_large(request: Request, exc: DocumentTooLargeError) -> JSONResponse:
        return _problem(
            request,
            status_code=413,
            code=exc.code,
            title="Document too large",
            detail=str(exc),
        )

    @app.exception_handler(UnsupportedDocumentError)
    async def unsupported(request: Request, exc: UnsupportedDocumentError) -> JSONResponse:
        return _problem(
            request,
            status_code=415,
            code=exc.code,
            title="Unsupported media type",
            detail=str(exc),
        )

    @app.exception_handler(InvalidDocumentError)
    async def invalid_document(request: Request, exc: InvalidDocumentError) -> JSONResponse:
        return _problem(
            request,
            status_code=400,
            code=exc.code,
            title="Invalid document",
            detail=str(exc),
        )

    @app.exception_handler(FactualIntegrityError)
    async def factual_integrity(request: Request, exc: FactualIntegrityError) -> JSONResponse:
        return _problem(
            request,
            status_code=422,
            code=exc.code,
            title="Factual integrity check failed",
            detail=str(exc),
            errors=[{"message": violation} for violation in exc.violations],
        )

    @app.exception_handler(IntelligenceProviderUnavailableError)
    async def provider_unavailable(
        request: Request, exc: IntelligenceProviderUnavailableError
    ) -> JSONResponse:
        return _problem(
            request,
            status_code=503,
            code=exc.code,
            title="AI provider unavailable",
            detail=str(exc),
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(IntelligenceProviderError)
    async def provider_error(request: Request, exc: IntelligenceProviderError) -> JSONResponse:
        return _problem(
            request,
            status_code=502,
            code=exc.code,
            title="AI provider error",
            detail=str(exc),
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return _problem(
            request,
            status_code=exc.status_code,
            code="http_error",
            title="Request rejected",
            detail=str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for item in exc.errors():
            errors.append(
                {
                    "location": [str(value) for value in item.get("loc", ())],
                    "message": item.get("msg", "Invalid value"),
                    "type": item.get("type", "validation_error"),
                }
            )
        return _problem(
            request,
            status_code=422,
            code="request_validation_error",
            title="Request validation failed",
            detail="One or more request fields are invalid",
            errors=errors,
        )

    @app.exception_handler(ResumeMatcherError)
    async def application_error(request: Request, exc: ResumeMatcherError) -> JSONResponse:
        logger.error("Unhandled application error", exc_info=exc)
        return _problem(
            request,
            status_code=500,
            code=exc.code,
            title="Application error",
            detail="The request could not be completed",
        )

    @app.exception_handler(Exception)
    async def unknown_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return _problem(
            request,
            status_code=500,
            code="internal_server_error",
            title="Internal server error",
            detail="An unexpected error occurred",
        )
