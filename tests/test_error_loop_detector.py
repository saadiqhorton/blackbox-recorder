"""Tests for the ErrorLoopDetector pipeline stage."""

from datetime import datetime, timedelta

from blackbox.models.error_loop import PatternType
from blackbox.models.event import ErrorEvent, EventModel, ToolUseEvent
from blackbox.pipeline.error_loop_detector import ErrorLoopDetector

NOW = datetime(2025, 1, 1, 12, 0, 0)


def test_repeated_command_detected():
    """Same command failing 3+ times triggers REPEATED_COMMAND."""
    detector = ErrorLoopDetector()
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(timestamp=NOW, tool_name="Bash", input={"command": "failing-cmd"}, is_error=True),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=1), tool_name="Bash", input={"command": "failing-cmd"}, is_error=True),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=2), tool_name="Bash", input={"command": "failing-cmd"}, is_error=True),
        ],
    )

    loops = detector.detect(events)

    assert len(loops) >= 1
    repeated = [l for l in loops if l.pattern == PatternType.REPEATED_COMMAND]
    assert len(repeated) == 1
    assert repeated[0].count >= 3


def test_circular_edit_detected():
    """4+ edits toggling between files triggers CIRCULAR_EDIT."""
    detector = ErrorLoopDetector()
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(timestamp=NOW, tool_name="Edit", input={"path": "file_a.py"}),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=1), tool_name="Edit", input={"path": "file_b.py"}),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=2), tool_name="Edit", input={"path": "file_a.py"}),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=3), tool_name="Edit", input={"path": "file_b.py"}),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=4), tool_name="Write", input={"path": "file_a.py"}),
        ],
    )

    loops = detector.detect(events)

    assert len(loops) >= 1
    circular = [l for l in loops if l.pattern == PatternType.CIRCULAR_EDIT]
    assert len(circular) == 1


def test_error_spike_detected():
    """5+ ErrorEvents within 60 seconds triggers ERROR_SPIKE."""
    detector = ErrorLoopDetector()
    events = EventModel(
        session_id="test",
        events=[
            ErrorEvent(timestamp=NOW + timedelta(seconds=i * 5), error_type="SyntaxError", message=f"error {i}")
            for i in range(6)
        ],
    )

    loops = detector.detect(events)

    assert len(loops) >= 1
    spike = [l for l in loops if l.pattern == PatternType.ERROR_SPIKE]
    assert len(spike) == 1
    assert spike[0].count >= 5


def test_normal_session_no_loops():
    """Normal session with passing commands returns empty list."""
    detector = ErrorLoopDetector()
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(timestamp=NOW, tool_name="Bash", input={"command": "pytest"}, is_error=False),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=1), tool_name="Edit", input={"path": "file.py"}),
            ToolUseEvent(timestamp=NOW + timedelta(seconds=2), tool_name="Bash", input={"command": "git commit"}, is_error=False),
        ],
    )

    loops = detector.detect(events)

    assert len(loops) == 0


def test_single_failure_no_false_positive():
    """Single failure does not trigger any loop pattern."""
    detector = ErrorLoopDetector()
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(timestamp=NOW, tool_name="Bash", input={"command": "failing-cmd"}, is_error=True),
            ErrorEvent(timestamp=NOW + timedelta(seconds=1), error_type="RuntimeError", message="single error"),
        ],
    )

    loops = detector.detect(events)

    assert len(loops) == 0
