from enum import StrEnum
from datetime import datetime

from pydantic import BaseModel


class PatternType(StrEnum):
    REPEATED_COMMAND = "repeated_command"
    CIRCULAR_EDIT = "circular_edit"
    ERROR_SPIKE = "error_spike"


class ErrorLoop(BaseModel):
    pattern: PatternType
    description: str
    count: int
    time_range: tuple[datetime, datetime] | None = None
    details: str = ""
