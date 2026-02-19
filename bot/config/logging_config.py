from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone


REDACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"https://api\.telegram\.org/bot\d{8,12}:[A-Za-z0-9_-]{25,}"),
        "https://api.telegram.org/bot[REDACTED_BOT_TOKEN]",
    ),
    (
        re.compile(r"bot\d{8,12}:[A-Za-z0-9_-]{25,}"),
        "bot[REDACTED_BOT_TOKEN]",
    ),
    (
        re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{25,}\b"),
        "[REDACTED_BOT_TOKEN]",
    ),
    (
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "[REDACTED_OPENAI_KEY]",
    ),
    (
        re.compile(r"(?i)\b(BOT_TOKEN|OPENAI_API_KEY|TRON_PRIVATE_KEY)\s*=\s*[^\s,;]+"),
        r"\1=[REDACTED]",
    ),
)


def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern, replacement in REDACT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_sensitive(record.getMessage()),
        }
        if record.exc_info:
            payload["exc_info"] = redact_sensitive(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=True)


class DropNoisyLoggers(logging.Filter):
    BLOCKED_PREFIXES = ("httpx", "httpcore")

    def filter(self, record: logging.LogRecord) -> bool:
        return not any(
            record.name == prefix or record.name.startswith(f"{prefix}.")
            for prefix in self.BLOCKED_PREFIXES
        )



def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(DropNoisyLoggers())

    root.handlers = [handler]
