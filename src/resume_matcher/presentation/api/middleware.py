from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from resume_matcher.infrastructure.logging import (
    bind_request_id,
    request_id_context,
    reset_request_id,
)

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = self._request_id(request.headers.get("x-request-id"))
        token = bind_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "Request completed",
                extra={
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": locals().get("response", Response(status_code=500)).status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)

    @staticmethod
    def _request_id(value: str | None) -> str:
        if value:
            try:
                return str(UUID(value))
            except ValueError:
                pass
        return str(uuid4())


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        return response


class ContentLengthLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    code="invalid_content_length",
                    detail="Content-Length must be a non-negative integer",
                )
                return
            if length < 0:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    code="invalid_content_length",
                    detail="Content-Length must be a non-negative integer",
                )
                return
            if length > self.max_bytes:
                await self._reject_too_large(scope, receive, send)
                return

        buffered: deque[Message] = deque()
        received_bytes = 0
        while True:
            message = await receive()
            buffered.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            received_bytes += len(message.get("body", b""))
            if received_bytes > self.max_bytes:
                await self._reject_too_large(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        async def replay_receive() -> Message:
            if buffered:
                return buffered.popleft()
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

    async def _reject_too_large(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._reject(
            scope,
            receive,
            send,
            status_code=413,
            code="request_too_large",
            detail=f"Request body exceeds the {self.max_bytes}-byte limit",
        )

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
        detail: str,
    ) -> None:
        path = str(scope.get("path", ""))
        response = JSONResponse(
            status_code=status_code,
            content={
                "type": f"urn:resume-matcher:error:{code}",
                "title": "Request rejected",
                "status": status_code,
                "detail": detail,
                "instance": path,
                "code": code,
                "request_id": request_id_context.get(),
            },
            media_type="application/problem+json",
        )
        await response(scope, receive, send)
