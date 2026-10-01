import json
import logging

from app.logging.setup import JsonFormatter, request_id_var


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.makeLogRecord({"msg": message, "levelname": "INFO", "name": "t"})
    record.__dict__.update(extra)
    return record


def test_json_formatter_emits_request_id_and_extras() -> None:
    token = request_id_var.set("req-123")
    try:
        payload = json.loads(JsonFormatter().format(_record("hello", latency_ms=12)))
    finally:
        request_id_var.reset(token)
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-123"
    assert payload["latency_ms"] == 12
    assert payload["level"] == "INFO"


def test_json_formatter_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record("failed")
        record.exc_info = sys.exc_info()
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]
