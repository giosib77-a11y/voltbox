"""The shape of a crash report from the browser.

Everything here arrives from a client nobody controls, so every field is capped
and nothing is optional-but-unbounded. A log line is a place an attacker would
happily write a megabyte of anything.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.base import ApiRequest

#: Long enough for a real React error and its component stack, short enough
#: that a thousand of them do not fill a disk.
MAX_MESSAGE = 300
MAX_STACK = 2000
MAX_PATH = 300


class ClientErrorReport(ApiRequest):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    path: str = Field(default="", max_length=MAX_PATH)
    stack: str = Field(default="", max_length=MAX_STACK)

    @field_validator("message", "path", "stack")
    @classmethod
    def one_line(cls, value: str) -> str:
        """Newlines and control characters, flattened.

        A log line is one line. A report containing "\\n{"level":"ERROR"...}"
        would otherwise appear in the log as a second, forged entry - the
        oldest trick there is against a log a human reads.
        """
        return "".join(" " if character < " " else character for character in value).strip()
