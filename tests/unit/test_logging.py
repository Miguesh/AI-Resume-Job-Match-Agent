from __future__ import annotations

import json
import logging
import sys

from resume_matcher.infrastructure.logging import (
    JsonFormatter,
    RedactingFilter,
    RedactingFormatter,
)


def _exception_record() -> logging.LogRecord:
    try:
        raise RuntimeError("provider rejected sk-super-secret-token for user@example.com")
    except RuntimeError:
        return logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Request for %s failed",
            args=("user@example.com",),
            exc_info=sys.exc_info(),
        )


def test_json_formatter_redacts_message_arguments_and_exception() -> None:
    record = _exception_record()
    RedactingFilter().filter(record)

    payload = json.loads(JsonFormatter().format(record))
    rendered = json.dumps(payload)

    assert "user@example.com" not in rendered
    assert "sk-super-secret-token" not in rendered
    assert rendered.count("[REDACTED]") >= 2


def test_text_formatter_redacts_exception_even_without_filter() -> None:
    rendered = RedactingFormatter("%(levelname)s %(message)s").format(_exception_record())

    assert "user@example.com" not in rendered
    assert "sk-super-secret-token" not in rendered
    assert "[REDACTED]" in rendered


def test_filter_preserves_mapping_style_log_arguments() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Request from %(email)s",
        args=({"email": "user@example.com"},),
        exc_info=None,
    )

    RedactingFilter().filter(record)

    assert record.getMessage() == "Request from [REDACTED]"
