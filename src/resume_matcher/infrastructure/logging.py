from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

_SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+)[a-z0-9._~+/-]+|"
    r"(sk-[a-z0-9_-]{12,})|"
    r"([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})"
)


def _redact(value: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", value)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if isinstance(record.args, Mapping):
            record.args = {key: _redact(str(value)) for key, value in record.args.items()}
        elif record.args:
            record.args = tuple(_redact(str(item)) for item in record.args)
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return _redact(super().format(record))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        for key in (
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "operation",
            "provider_status",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging(*, level: str, json_output: bool) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        JsonFormatter() if json_output else RedactingFormatter("%(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def bind_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)
