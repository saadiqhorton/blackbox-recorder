"""Claude Code JSONL session adapter.

Reads Claude Code session export files (~/.claude/sessions/*.jsonl)
and normalizes them into EventModel instances for downstream pipeline phases.

Format: newline-delimited JSON (JSONL), one event per line.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator

from blackbox.models.event import (
    ErrorEvent,
    EventModel,
    EventUnion,
    MessageEvent,
    ToolUseEvent,
)

logger = logging.getLogger(__name__)

# JSONL event types that carry no actionable data — skipped during ingest
_SKIP_EVENT_TYPES = frozenset({
    "permission-mode",
    "file-history-snapshot",
    "last-prompt",
    "queue-operation",
})

# Content block types within assistant messages that are skipped
_SKIP_CONTENT_TYPES = frozenset({
    "thinking",
    "redacted_thinking",
})


def _parse_timestamp(raw: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp, returning None on failure."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _iter_jsonl(path: Path) -> Iterator[tuple[int, dict]]:
    """Yield (line_number, parsed_json) for each valid JSON line.

    Malformed lines are logged as warnings and skipped.
    """
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield lineno, json.loads(stripped)
            except json.JSONDecodeError:
                logger.warning("Malformed JSONL at line %d: %s", lineno, line.rstrip()[:120])


def _ingest_message(obj: dict) -> MessageEvent | None:
    """Convert a user/assistant JSONL event into a MessageEvent."""
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return None
    role = msg.get("role", "")
    if role not in ("user", "assistant"):
        return None

    ts = _parse_timestamp(obj.get("timestamp"))
    content_parts: list[str] = []

    raw_content = msg.get("content", "")
    if isinstance(raw_content, str):
        content_parts.append(raw_content)
    elif isinstance(raw_content, list):
        for block in raw_content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in _SKIP_CONTENT_TYPES:
                continue
            if block.get("type") == "tool_use":
                # Tool uses within assistant messages are handled separately
                continue
            if block.get("type") == "tool_result":
                continue
            text = block.get("text", "")
            if isinstance(text, str) and text:
                content_parts.append(text)

    if not content_parts:
        return None

    return MessageEvent(
        timestamp=ts or datetime.min,
        role=role,  # type: ignore[arg-type]
        content="\n".join(content_parts),
    )


def _ingest_tool_uses(obj: dict) -> list[ToolUseEvent]:
    """Extract ToolUseEvents from an assistant message's content blocks."""
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return []
    raw_content = msg.get("content", [])
    if not isinstance(raw_content, list):
        return []

    ts = _parse_timestamp(obj.get("timestamp"))
    results: list[ToolUseEvent] = []

    for block in raw_content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue

        tool_name = block.get("name", "unknown")
        inp = block.get("input", {})
        tool_id = block.get("id")

        results.append(ToolUseEvent(
            timestamp=ts or datetime.min,
            tool_name=tool_name,
            input=inp if isinstance(inp, dict) else {},
            tool_use_id=tool_id,
        ))

    return results


def _ingest_tool_results(obj: dict, tool_map: dict[str, ToolUseEvent]) -> None:
    """Correlate tool_result blocks with their tool_use and update output/exit_code."""
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return
    raw_content = msg.get("content", [])
    if not isinstance(raw_content, list):
        return

    for block in raw_content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_result":
            continue

        tool_use_id = block.get("tool_use_id")
        if not tool_use_id:
            continue

        # Extract text from tool_result content
        result_parts: list[str] = []
        result_content = block.get("content", "")
        if isinstance(result_content, str):
            result_parts.append(result_content)
        elif isinstance(result_content, list):
            for item in result_content:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    if isinstance(text, str):
                        result_parts.append(text)

        is_error = block.get("is_error", False)
        output = "\n".join(result_parts).strip() or None

        # Update the corresponding tool_use event
        if tool_use_id in tool_map:
            tool_map[tool_use_id].output = output
            tool_map[tool_use_id].is_error = is_error
        else:
            logger.warning("Orphan tool_result for id %s — no matching tool_use found", tool_use_id)


def _ingest_system_error(obj: dict) -> ErrorEvent | None:
    """Convert a system-level error event into an ErrorEvent."""
    if obj.get("type") != "system":
        return None

    error = obj.get("error")
    if not isinstance(error, dict):
        return None

    ts = _parse_timestamp(obj.get("timestamp"))
    return ErrorEvent(
        timestamp=ts or datetime.min,
        error_type=error.get("type", "system_error"),
        message=error.get("message", ""),
        context=error.get("context"),
    )


class ClaudeCodeAdapter:
    """Adapter for Claude Code JSONL session files.

    Reads a JSONL file line by line, normalizing each event into the
    project's internal EventModel. Handles:
    - user/assistant messages → MessageEvent
    - tool_use content blocks → ToolUseEvent (correlated with tool_result)
    - system errors → ErrorEvent
    - Malformed lines → skip with warning
    - Empty files → EventModel with zero events
    """

    def __init__(self) -> None:
        self._metadata: dict = {}

    @property
    def metadata(self) -> dict:
        return dict(self._metadata)

    def list_event_types(self) -> list[str]:
        return [
            "permission-mode", "attachment", "file-history-snapshot",
            "user", "assistant", "system", "last-prompt", "queue-operation",
        ]

    def ingest(self, path: str | Path) -> EventModel:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"No session file at {path}")

        session_id: str | None = None
        agent_type = "claude-code"
        version: str | None = None

        events: list[EventUnion] = []
        tool_map: dict[str, ToolUseEvent] = {}
        first_user_content: str | None = None
        lineno = 0

        for lineno, obj in _iter_jsonl(path):
            # Capture session-level metadata from first events
            if session_id is None:
                session_id = obj.get("sessionId")
                version = obj.get("version")

            event_type = obj.get("type", "")

            if event_type in _SKIP_EVENT_TYPES:
                continue

            if event_type == "user":
                msg_event = _ingest_message(obj)
                if msg_event is not None:
                    events.append(msg_event)
                    if first_user_content is None:
                        first_user_content = msg_event.content

            elif event_type == "assistant":
                msg_event = _ingest_message(obj)
                if msg_event is not None:
                    events.append(msg_event)

                # Extract tool_use and tool_result from content blocks
                tool_uses = _ingest_tool_uses(obj)
                for tu in tool_uses:
                    if tu.tool_use_id:
                        tool_map[tu.tool_use_id] = tu
                    events.append(tu)

                _ingest_tool_results(obj, tool_map)

            elif event_type == "system":
                err_event = _ingest_system_error(obj)
                if err_event is not None:
                    events.append(err_event)

        self._metadata = {
            "adapter": "claude-code",
            "file": str(path),
            "version": version or "",
            "total_lines": lineno,
        }

        return EventModel(
            session_id=session_id or path.stem,
            agent_type=agent_type,
            task=first_user_content,
            events=events,
            schema_version="1.0",
        )
