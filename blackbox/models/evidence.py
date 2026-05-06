from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    """A single piece of evidence extracted from an event."""

    type: Literal["command", "git_diff", "error", "file_change"]
    source_tool: str | None = None
    source_idx: int
    value: str
    is_error: bool = False


class EvidenceSet(BaseModel):
    """Typed container for all evidence collected from an EventModel."""

    commands: list[EvidenceItem] = []
    git_diffs: list[EvidenceItem] = []
    errors: list[EvidenceItem] = []
    file_changes: list[EvidenceItem] = []

    @property
    def total_count(self) -> int:
        return len(self.commands) + len(self.git_diffs) + len(self.errors) + len(self.file_changes)
