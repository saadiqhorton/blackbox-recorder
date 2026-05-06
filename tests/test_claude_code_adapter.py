"""Tests for the Claude Code JSONL adapter."""

from pathlib import Path

import pytest

from blackbox.adapters import IngestAdapter
from blackbox.adapters.claude_code import ClaudeCodeAdapter
from blackbox.models.event import EventModel


FIXTURES_DIR = Path("test_fixtures")


def test_valid_session():
    """Adapter parses a valid honest session into an EventModel."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "honest_session.jsonl")

    assert isinstance(result, EventModel)
    assert result.session_id == "honest-001"
    assert result.agent_type == "claude-code"
    assert len(result.events) >= 6
    assert any(e.type == "message" for e in result.events)
    assert any(e.type == "tool_use" for e in result.events)


def test_empty_session():
    """Adapter returns EventModel with zero events for empty file."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "empty_session.jsonl")

    assert isinstance(result, EventModel)
    assert len(result.events) == 0
    assert result.session_id is not None  # Falls back to filename stem


def test_truncated_session():
    """Adapter recovers from malformed JSONL lines, skipping them with warnings."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "corrupt_session.jsonl")

    assert isinstance(result, EventModel)
    # Should still parse valid lines before and after the malformed one
    assert len(result.events) >= 2


def test_dishonest_session_tracks_errors():
    """Adapter correctly sets is_error=True on failing tool results."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "dishonest_session.jsonl")

    tool_events = [e for e in result.events if e.type == "tool_use"]
    bash_tools = [t for t in tool_events if t.tool_name == "Bash" and t.tool_use_id == "tu-003"]

    assert len(bash_tools) >= 1
    failing_tool = bash_tools[0]
    assert failing_tool.is_error is True
    assert failing_tool.output is not None
    assert "failed" in failing_tool.output


def test_session_metadata_extracted():
    """Adapter extracts session_id, agent_type, and task from session."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "honest_session.jsonl")

    assert result.session_id == "honest-001"
    assert result.agent_type == "claude-code"
    assert result.task is not None
    assert "login" in result.task.lower()


def test_file_not_found():
    """Adapter raises FileNotFoundError for missing files."""
    adapter = ClaudeCodeAdapter()
    with pytest.raises(FileNotFoundError, match="No session file"):
        adapter.ingest("nonexistent.jsonl")


def test_list_event_types():
    """Adapter returns recognized event types."""
    adapter = ClaudeCodeAdapter()
    types = adapter.list_event_types()
    assert "user" in types
    assert "assistant" in types
    assert "system" in types


def test_adapter_metadata():
    """Adapter exposes metadata after ingest."""
    adapter = ClaudeCodeAdapter()
    adapter.ingest(FIXTURES_DIR / "honest_session.jsonl")
    meta = adapter.metadata
    assert meta["adapter"] == "claude-code"
    assert "file" in meta


def test_adapter_is_ingest_adapter():
    """ClaudeCodeAdapter satisfies the IngestAdapter protocol."""
    adapter = ClaudeCodeAdapter()
    assert isinstance(adapter, IngestAdapter)


def test_skipped_event_types_filtered():
    """Skipped event types (permission-mode, file-history-snapshot) never appear in output."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "honest_session.jsonl")
    for e in result.events:
        assert e.type in ("message", "tool_use", "error")


def test_ambiguous_session_limited_evidence():
    """Ambiguous session has only Read tool_use — no commands with exit codes."""
    adapter = ClaudeCodeAdapter()
    result = adapter.ingest(FIXTURES_DIR / "ambiguous_session.jsonl")

    tool_events = [e for e in result.events if e.type == "tool_use"]
    assert len(tool_events) >= 1
    # Only Read tool uses — no Bash/Edit that produce verifiable outcomes
    assert all(t.tool_name == "Read" for t in tool_events)
