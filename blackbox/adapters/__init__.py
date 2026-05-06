from typing import Protocol, runtime_checkable
from pathlib import Path


@runtime_checkable
class IngestAdapter(Protocol):
    """Protocol for session file ingest adapters.

    Any object with these methods is an adapter — no inheritance required.
    """

    def ingest(self, path: str | Path) -> "EventModel":
        """Parse a session file into a normalized EventModel."""
        ...

    def list_event_types(self) -> list[str]:
        """Return the JSONL event types this adapter recognizes."""
        ...

    @property
    def metadata(self) -> dict:
        """Adapter metadata: name, version, supported formats."""
        ...
