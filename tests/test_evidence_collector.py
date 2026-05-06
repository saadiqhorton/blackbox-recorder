"""Tests for the EvidenceCollector pipeline stage."""

from datetime import datetime
from unittest.mock import patch

from blackbox.models.event import ErrorEvent, EventModel, ToolUseEvent
from blackbox.models.evidence import EvidenceSet
from blackbox.pipeline.evidence_collector import EvidenceCollector

NOW = datetime(2025, 1, 1)


def test_command_evidence():
    """Bash tool_use events produce command evidence with is_error flag."""
    collector = EvidenceCollector()
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(
                timestamp=NOW,
                tool_name="Bash",
                input={"command": "pytest"},
                output="all tests passed",
                is_error=False,
            ),
            ToolUseEvent(
                timestamp=NOW,
                tool_name="Bash",
                input={"command": "failing-cmd"},
                output="error occurred",
                is_error=True,
            ),
        ],
    )

    result = collector.collect(events)

    assert len(result.commands) == 2
    assert result.commands[0].value == "pytest"
    assert result.commands[0].is_error is False
    assert result.commands[1].value == "failing-cmd"
    assert result.commands[1].is_error is True


@patch("blackbox.pipeline.evidence_collector._check_is_git_repo", return_value=True)
def test_git_diff_evidence(mock_git):
    """Edit tool_use with diff output produces git_diff evidence."""
    collector = EvidenceCollector()
    diff_output = "diff --git a/file.py b/file.py\n@@ -1 +1 @@\n-old\n+new"
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(
                timestamp=NOW,
                tool_name="Edit",
                input={"path": "file.py"},
                output=diff_output,
                is_error=False,
            ),
        ],
    )

    result = collector.collect(events)

    assert len(result.git_diffs) == 1
    assert "diff --git" in result.git_diffs[0].value
    assert result.git_diffs[0].source_tool == "Edit"
    assert len(result.file_changes) == 1
    assert result.file_changes[0].value == "file.py"


def test_no_events():
    """Empty EventModel returns EvidenceSet with total_count==0."""
    collector = EvidenceCollector()
    events = EventModel(session_id="empty", events=[])

    result = collector.collect(events)

    assert isinstance(result, EvidenceSet)
    assert result.total_count == 0
    assert result.commands == []
    assert result.git_diffs == []
    assert result.errors == []
    assert result.file_changes == []


def test_error_events_only():
    """ErrorEvent entries produce error evidence; other lists empty."""
    collector = EvidenceCollector()
    events = EventModel(
        session_id="test",
        events=[
            ErrorEvent(timestamp=NOW, error_type="ValueError", message="bad value"),
            ErrorEvent(timestamp=NOW, error_type="KeyError", message="missing key"),
        ],
    )

    result = collector.collect(events)

    assert len(result.errors) == 2
    assert "[ValueError]" in result.errors[0].value
    assert "[KeyError]" in result.errors[1].value
    assert result.commands == []
    assert result.git_diffs == []
    assert result.file_changes == []
