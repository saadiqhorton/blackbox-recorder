from __future__ import annotations

import logging
import subprocess
from typing import ClassVar

from blackbox.models.event import (
    CommandEvent,
    ErrorEvent,
    EventModel,
    FileEditEvent,
    ToolUseEvent,
)
from blackbox.models.evidence import EvidenceItem, EvidenceSet

logger = logging.getLogger(__name__)

GIT_DIFF_PATTERNS: set[str] = {"diff --git", "\n@@ ", "\n--- ", "\n+++ "}

_GIT_CACHE: bool | None = None


def _check_is_git_repo() -> bool:
    """Check if cwd is a git repo, cached per process."""
    global _GIT_CACHE
    if _GIT_CACHE is not None:
        return _GIT_CACHE
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=5.0,
        )
        _GIT_CACHE = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _GIT_CACHE = False
    return _GIT_CACHE


def _contains_diff(output: str) -> bool:
    """Heuristic: check if output contains git diff patterns."""
    return any(pattern in output for pattern in GIT_DIFF_PATTERNS)


class EvidenceCollector:
    """Collects evidence from an EventModel by classifying events."""

    GIT_DIFF_KEYWORDS: ClassVar[set[str]] = GIT_DIFF_PATTERNS

    def __init__(self) -> None:
        self._needs_git_check = True

    def collect(self, events: EventModel) -> EvidenceSet:
        """Iterate events and classify into evidence types."""
        result = EvidenceSet()

        for idx, event in enumerate(events.events):
            if isinstance(event, ToolUseEvent):
                self._handle_tool_use(event, idx, result)
            elif isinstance(event, CommandEvent):
                result.commands.append(
                    EvidenceItem(
                        type="command",
                        source_tool="command",
                        source_idx=idx,
                        value=event.command,
                        is_error=(event.exit_code is not None and event.exit_code != 0),
                    )
                )
            elif isinstance(event, FileEditEvent):
                result.file_changes.append(
                    EvidenceItem(
                        type="file_change",
                        source_tool="file_edit",
                        source_idx=idx,
                        value=event.diff or event.path,
                    )
                )
            elif isinstance(event, ErrorEvent):
                result.errors.append(
                    EvidenceItem(
                        type="error",
                        source_tool="error",
                        source_idx=idx,
                        value=f"[{event.error_type}] {event.message}",
                    )
                )

        # Git repo check (once per collect)
        if self._needs_git_check:
            self._needs_git_check = False
            if not _check_is_git_repo():
                result.git_diffs.append(
                    EvidenceItem(
                        type="git_diff",
                        source_idx=0,
                        value="Git evidence unavailable -- not a git repo",
                    )
                )

        return result

    def _handle_tool_use(self, event: ToolUseEvent, idx: int, result: EvidenceSet) -> None:
        if event.tool_name == "Bash":
            cmd_str = event.input.get("command") or event.input.get("text", "")
            result.commands.append(
                EvidenceItem(
                    type="command",
                    source_tool="Bash",
                    source_idx=idx,
                    value=cmd_str,
                    is_error=event.is_error,
                )
            )
            if event.output and _contains_diff(event.output):
                result.git_diffs.append(
                    EvidenceItem(
                        type="git_diff",
                        source_tool="Bash",
                        source_idx=idx,
                        value=event.output,
                    )
                )
        elif event.tool_name in ("Edit", "Write"):
            file_path = event.input.get("path") or event.input.get("file_path", "")
            diff_output = event.output or ""
            result.file_changes.append(
                EvidenceItem(
                    type="file_change",
                    source_tool=event.tool_name,
                    source_idx=idx,
                    value=file_path,
                )
            )
            if _contains_diff(diff_output):
                result.git_diffs.append(
                    EvidenceItem(
                        type="git_diff",
                        source_tool=event.tool_name,
                        source_idx=idx,
                        value=diff_output,
                    )
                )
