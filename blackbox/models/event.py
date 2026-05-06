from enum import StrEnum
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EventType(StrEnum):
    COMMAND = "command"
    FILE_EDIT = "file_edit"
    MESSAGE = "message"
    TOOL_USE = "tool_use"
    ERROR = "error"


class CommandEvent(BaseModel):
    type: Literal["command"] = "command"
    timestamp: datetime
    command: str
    args: list[str] = []
    exit_code: int | None = None
    stdout_snippet: str | None = None
    stderr_snippet: str | None = None
    working_directory: str | None = None


class FileEditEvent(BaseModel):
    type: Literal["file_edit"] = "file_edit"
    timestamp: datetime
    path: str
    action: Literal["create", "edit", "delete"]
    diff: str | None = None


class MessageEvent(BaseModel):
    type: Literal["message"] = "message"
    timestamp: datetime
    role: Literal["user", "assistant"]
    content: str


class ToolUseEvent(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    timestamp: datetime
    tool_name: str
    input: dict = {}
    output: str | None = None
    duration_ms: int | None = None
    tool_use_id: str | None = None
    is_error: bool = False


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    timestamp: datetime
    error_type: str
    message: str
    context: str | None = None


EventUnion = CommandEvent | FileEditEvent | MessageEvent | ToolUseEvent | ErrorEvent


class EventModel(BaseModel):
    session_id: str
    agent_type: str = "claude-code"
    task: str | None = None
    events: list[EventUnion] = []
    schema_version: str = "1.0"
