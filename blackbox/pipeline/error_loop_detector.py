from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from blackbox.models.error_loop import ErrorLoop, PatternType
from blackbox.models.event import ErrorEvent, EventModel, ToolUseEvent


class ErrorLoopDetector:
    """Detects three error loop patterns in an EventModel.

    Patterns detected:
    1. RepeatedCommand — same bash command failing 3+ times
    2. CircularEdit — 4+ edits toggling between files
    3. ErrorSpike — 5+ ErrorEvents within a 60-second window
    """

    REPEATED_COMMAND_THRESHOLD = 3
    CIRCULAR_EDIT_THRESHOLD = 4
    ERROR_SPIKE_THRESHOLD = 5
    ERROR_SPIKE_WINDOW_SECONDS = 60

    def detect(self, events: EventModel) -> list[ErrorLoop]:
        """Run all three detectors and return aggregated results."""
        loops: list[ErrorLoop] = []

        repeated = self._detect_repeated_commands(events)
        if repeated:
            loops.append(repeated)

        circular = self._detect_circular_edits(events)
        if circular:
            loops.append(circular)

        spike = self._detect_error_spikes(events)
        if spike:
            loops.append(spike)

        return loops

    def _detect_repeated_commands(self, events: EventModel) -> ErrorLoop | None:
        """Detect repeated failing commands (same command string, 3+ occurrences, is_error=True)."""
        cmd_groups: dict[str, list[ToolUseEvent]] = defaultdict(list)

        for event in events.events:
            if isinstance(event, ToolUseEvent) and event.tool_name == "Bash" and event.is_error:
                cmd = event.input.get("command") or event.input.get("text", "")
                cmd_groups[cmd].append(event)

        for cmd, occurrences in cmd_groups.items():
            if len(occurrences) >= self.REPEATED_COMMAND_THRESHOLD:
                stderr = ""
                for occ in occurrences:
                    if occ.output:
                        stderr = occ.output[:200]
                        break

                time_range = None
                if occurrences[0].timestamp:
                    time_range = (occurrences[0].timestamp, occurrences[-1].timestamp)

                return ErrorLoop(
                    pattern=PatternType.REPEATED_COMMAND,
                    description=f"Command '{cmd[:80]}' failed {len(occurrences)} times",
                    count=len(occurrences),
                    time_range=time_range,
                    details=stderr,
                )

        return None

    def _detect_circular_edits(self, events: EventModel) -> ErrorLoop | None:
        """Detect oscillating edits: same filepath appearing non-consecutively with 4+ total edits."""
        edit_paths: list[str] = []

        for event in events.events:
            if isinstance(event, ToolUseEvent) and event.tool_name in ("Edit", "Write"):
                path = event.input.get("path") or event.input.get("file_path", "")
                if path:
                    edit_paths.append(path)

        if len(edit_paths) < self.CIRCULAR_EDIT_THRESHOLD:
            return None

        seen_first: set[str] = set()
        for path in edit_paths:
            if path in seen_first:
                timestamps = [
                    e.timestamp for e in events.events
                    if isinstance(e, ToolUseEvent) and e.tool_name in ("Edit", "Write")
                    and (e.input.get("path") or e.input.get("file_path", "")) == path
                ]
                timestamps = [t for t in timestamps if t is not None]
                time_range = None
                if len(timestamps) >= 2:
                    time_range = (timestamps[0], timestamps[-1])

                return ErrorLoop(
                    pattern=PatternType.CIRCULAR_EDIT,
                    description=f"Circular edits detected on '{path}' — edited {edit_paths.count(path)} times across {len(edit_paths)} total edits",
                    count=edit_paths.count(path),
                    time_range=time_range,
                    details=f"Edit sequence: {' → '.join(edit_paths)}",
                )
            seen_first.add(path)

        return None

    def _detect_error_spikes(self, events: EventModel) -> ErrorLoop | None:
        """Detect 5+ ErrorEvents within a 60-second sliding window."""
        error_events: list[ErrorEvent] = [
            e for e in events.events if isinstance(e, ErrorEvent) and e.timestamp
        ]

        if len(error_events) < self.ERROR_SPIKE_THRESHOLD:
            return None

        error_events_sorted = sorted(error_events, key=lambda e: e.timestamp)

        for i in range(len(error_events_sorted) - self.ERROR_SPIKE_THRESHOLD + 1):
            window_events = error_events_sorted[i:i + self.ERROR_SPIKE_THRESHOLD]
            window_start = window_events[0].timestamp
            window_end = window_events[-1].timestamp

            if isinstance(window_start, datetime) and isinstance(window_end, datetime):
                if (window_end - window_start) <= timedelta(seconds=self.ERROR_SPIKE_WINDOW_SECONDS):
                    type_counts: dict[str, int] = defaultdict(int)
                    for ev in window_events:
                        type_counts[ev.error_type] += 1
                    top_type = max(type_counts, key=type_counts.get)

                    first_ts = error_events_sorted[0].timestamp
                    last_ts = error_events_sorted[-1].timestamp

                    return ErrorLoop(
                        pattern=PatternType.ERROR_SPIKE,
                        description=f"Error spike: {len(window_events)} '{top_type}' errors in {(window_end - window_start).total_seconds():.0f}s",
                        count=len(window_events),
                        time_range=(first_ts, last_ts) if first_ts else None,
                        details=f"Error types in window: {dict(type_counts)}",
                    )

        return None
