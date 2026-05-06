# Phase 4: Cross-Referencer, Scoring & Error Loop Detection

**Waves:** 1
**Plans:** 1

---

## Plan 4.1: Cross-Referencer & Error Loop Detector (Wave 1)

**Wave:** 1
**Depends on:** None (Wave 1)
**Files to create:**
- `blackbox/pipeline/cross_referencer.py`
- `blackbox/pipeline/error_loop_detector.py`
- `tests/test_cross_referencer.py`
- `tests/test_error_loop_detector.py`
**Files to modify:**
- `blackbox/pipeline/__init__.py`

<task id="p4-1-1">
<read_first>
- `SPEC.md` lines 38-50 (cross-referencing), 52-55 (confidence levels), 56-65 (error loop detection), 267-285 (scoring), 290-303 (error loop details)
- `blackbox/models/claim.py` — Claim, EvidenceRef, ClaimCategory, ConfidenceLevel
- `blackbox/models/evidence.py` — EvidenceSet, EvidenceItem
- `blackbox/models/score.py` — LieScore, EvidenceCompleteness, ClaimVeracity, RiskLabel, compute_risk_label
- `blackbox/models/event.py` — ToolUseEvent, ErrorEvent
- `blackbox/models/error_loop.py` — ErrorLoop, PatternType
- `blackbox/pipeline/evidence_collector.py` — existing pipeline patterns
</read_first>

<action>
Create `blackbox/pipeline/cross_referencer.py`:

```python
from __future__ import annotations

from blackbox.models.claim import Claim, ClaimCategory, ConfidenceLevel
from blackbox.models.evidence import EvidenceSet
from blackbox.models.score import (
    ClaimVeracity,
    EvidenceCompleteness,
    LieScore,
    RiskLabel,
    compute_risk_label,
)


class CrossReferencer:
    """Matches claims against evidence and produces LieScore."""

    def cross_reference(self, claims: list[Claim], evidence: EvidenceSet) -> LieScore:
        """Match each claim against relevant evidence, populate claim.evidence, return LieScore."""
        if not claims or evidence.total_count == 0:
            # Edge case: no claims or no evidence — everything is MISSING
            completeness = EvidenceCompleteness(evidenced_claims=0, total_claims=len(claims))
            veracity = ClaimVeracity(matching_claims=0, evidenced_claims=0)
            risk = compute_risk_label(completeness.percentage, veracity.percentage)
            return LieScore(
                evidence_completeness=completeness,
                claim_veracity=veracity,
                risk_label=risk,
            )

        for claim in claims:
            refs = self._match(claim, evidence)
            claim.evidence = refs

        evidenced_claims = sum(1 for c in claims if len(c.evidence) > 0)
        matching_claims = sum(
            1 for c in claims
            if any(r.confidence == ConfidenceLevel.EXACT for r in c.evidence)
        )

        completeness = EvidenceCompleteness(
            evidenced_claims=evidenced_claims,
            total_claims=len(claims),
        )
        veracity = ClaimVeracity(
            matching_claims=matching_claims,
            evidenced_claims=evidenced_claims,
        )
        risk = compute_risk_label(completeness.percentage, veracity.percentage)

        return LieScore(
            evidence_completeness=completeness,
            claim_veracity=veracity,
            risk_label=risk,
        )

    def _match(self, claim: Claim, evidence: EvidenceSet) -> list:
        """Scan relevant evidence by claim category and return EvidenceRef list."""
        refs: list = []
        category = claim.category

        # Select relevant evidence channels per category
        if category == ClaimCategory.TEST_RESULT:
            refs.extend(self._match_commands(claim, evidence.commands))
            refs.extend(self._match_git_diffs(claim, evidence.git_diffs))

        elif category == ClaimCategory.OUTCOME:
            refs.extend(self._match_commands(claim, evidence.commands))
            refs.extend(self._match_file_changes(claim, evidence.file_changes))

        elif category == ClaimCategory.SCOPE:
            refs.extend(self._match_file_changes(claim, evidence.file_changes))
            refs.extend(self._match_git_diffs(claim, evidence.git_diffs))

        elif category == ClaimCategory.APPROACH:
            refs.extend(self._match_commands(claim, evidence.commands))

        elif category == ClaimCategory.STATE:
            refs.extend(self._match_errors(claim, evidence.errors))
            refs.extend(self._match_commands(claim, evidence.commands))

        # Fallback: if nothing matched but evidence exists in relevant categories, mark SEMANTIC
        if not refs:
            for _ in self._relevant_evidence_items(claim, evidence):
                refs.append({
                    "source": "evidence",
                    "type": category.value,
                    "value": "semantic",
                    "confidence": ConfidenceLevel.SEMANTIC,
                })
                break

        return refs

    def _relevant_evidence_items(self, claim: Claim, evidence: EvidenceSet) -> list:
        """Yield relevant evidence items for the claim's category."""
        if claim.category == ClaimCategory.TEST_RESULT:
            return evidence.commands + evidence.git_diffs
        elif claim.category == ClaimCategory.OUTCOME:
            return evidence.commands + evidence.file_changes
        elif claim.category == ClaimCategory.SCOPE:
            return evidence.file_changes + evidence.git_diffs
        elif claim.category == ClaimCategory.APPROACH:
            return evidence.commands
        elif claim.category == ClaimCategory.STATE:
            return evidence.errors + evidence.commands
        return []

    def _match_commands(self, claim: Claim, commands: list) -> list:
        """Match claim text against command evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for cmd in commands:
            if cmd.is_error is False and ("pass" in claim_lower or "succeed" in claim_lower):
                refs.append({
                    "source": f"command:{cmd.source_idx}",
                    "type": "command",
                    "value": cmd.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
            elif cmd.is_error and ("fail" in claim_lower or "error" in claim_lower):
                refs.append({
                    "source": f"command:{cmd.source_idx}",
                    "type": "command",
                    "value": cmd.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and commands:
            refs.append({
                "source": "commands",
                "type": "command",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs

    def _match_git_diffs(self, claim: Claim, diffs: list) -> list:
        """Match claim text against git diff evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for diff in diffs:
            if claim_lower in diff.value.lower():
                refs.append({
                    "source": f"git_diff:{diff.source_idx}",
                    "type": "git_diff",
                    "value": diff.value[:100],
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and diffs:
            refs.append({
                "source": "git_diffs",
                "type": "git_diff",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs

    def _match_file_changes(self, claim: Claim, changes: list) -> list:
        """Match claim text against file change evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for change in changes:
            if claim_lower in change.value.lower():
                refs.append({
                    "source": f"file_change:{change.source_idx}",
                    "type": "file_change",
                    "value": change.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and changes:
            refs.append({
                "source": "file_changes",
                "type": "file_change",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs

    def _match_errors(self, claim: Claim, errors: list) -> list:
        """Match claim text against error evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for err in errors:
            if claim_lower in err.value.lower():
                refs.append({
                    "source": f"error:{err.source_idx}",
                    "type": "error",
                    "value": err.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and errors:
            refs.append({
                "source": "errors",
                "type": "error",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs
```

</action>

<acceptance_criteria>
- `CrossReferencer.cross_reference(claims, evidence)` returns `LieScore`
- Populates `claim.evidence` with list of `EvidenceRef`-compatible dicts per claim
- Confidence levels: EXACT (direct match), SEMANTIC (category match, no direct), MISSING (no evidence)
- Edge cases handled: empty claims, empty evidence, contradictory evidence
</acceptance_criteria>
</task>

<task id="p4-1-2">
<read_first>
- `blackbox/pipeline/cross_referencer.py` — implementation to test
- `blackbox/models/claim.py` — Claim, ClaimCategory, ConfidenceLevel construction
- `blackbox/models/evidence.py` — EvidenceSet, EvidenceItem construction
- `blackbox/models/score.py` — LieScore, RiskLabel
- `tests/test_evidence_collector.py` — existing test patterns (plain def, assert, no classes)
</read_first>

<action>
Create `tests/test_cross_referencer.py` with 5 tests:

```python
"""Tests for the CrossReferencer pipeline stage."""

from datetime import datetime

from blackbox.models.claim import Claim, ClaimCategory, ConfidenceLevel
from blackbox.models.evidence import EvidenceItem, EvidenceSet
from blackbox.models.score import RiskLabel
from blackbox.pipeline.cross_referencer import CrossReferencer

NOW = datetime(2025, 1, 1)


def _make_evidence(
    commands: list[tuple[str, bool]] | None = None,
    diffs: list[str] | None = None,
    errors: list[str] | None = None,
    file_changes: list[str] | None = None,
) -> EvidenceSet:
    return EvidenceSet(
        commands=[
            EvidenceItem(type="command", source_idx=i, value=cmd, is_error=is_err)
            for i, (cmd, is_err) in enumerate((commands or []))
        ],
        git_diffs=[
            EvidenceItem(type="git_diff", source_idx=i, value=d)
            for i, d in enumerate(diffs or [])
        ],
        errors=[
            EvidenceItem(type="error", source_idx=i, value=e)
            for i, e in enumerate(errors or [])
        ],
        file_changes=[
            EvidenceItem(type="file_change", source_idx=i, value=f)
            for i, f in enumerate(file_changes or [])
        ],
    )


def test_exact_match_test_result():
    """Claim about tests passing matched against successful command."""
    xref = CrossReferencer()
    claims = [Claim(text="Tests passed successfully", category=ClaimCategory.TEST_RESULT, source_message_idx=0)]
    evidence = _make_evidence(commands=[("pytest", False)])

    score = xref.cross_reference(claims, evidence)

    assert score.evidence_completeness.evidenced_claims == 1
    assert score.evidence_completeness.total_claims == 1
    assert score.claim_veracity.matching_claims == 1
    assert score.claim_veracity.evidenced_claims == 1
    assert score.risk_label == RiskLabel.LOW
    assert len(claims[0].evidence) >= 1
    exact_refs = [r for r in claims[0].evidence if r.get("confidence") == ConfidenceLevel.EXACT]
    assert len(exact_refs) >= 1


def test_semantic_match_outcome():
    """Claim about outcome with no exact match but relevant evidence."""
    xref = CrossReferencer()
    claims = [Claim(text="The refactor improved code quality", category=ClaimCategory.OUTCOME, source_message_idx=0)]
    evidence = _make_evidence(commands=[("git commit", False)], file_changes=["src/main.py"])

    score = xref.cross_reference(claims, evidence)

    assert score.evidence_completeness.evidenced_claims == 1
    assert claims[0].evidence
    semantic_refs = [r for r in claims[0].evidence if r.get("confidence") == ConfidenceLevel.SEMANTIC]
    assert len(semantic_refs) >= 1


def test_contradictory_evidence():
    """Claim says tests pass but command evidence shows failure."""
    xref = CrossReferencer()
    claims = [Claim(text="Tests passed successfully", category=ClaimCategory.TEST_RESULT, source_message_idx=0)]
    evidence = _make_evidence(commands=[("pytest", True)])

    score = xref.cross_reference(claims, evidence)

    # Contradictory: "pass" in claim but is_error=True — no exact match
    assert len(claims[0].evidence) >= 0  # May get semantic match
    if len(claims[0].evidence) > 0:
        exact = [r for r in claims[0].evidence if r.get("confidence") == ConfidenceLevel.EXACT]
        assert len(exact) == 0  # No exact match for contradictory evidence


def test_empty_claims():
    """No claims to cross-reference."""
    xref = CrossReferencer()
    evidence = _make_evidence(commands=[("pytest", False)])

    score = xref.cross_reference([], evidence)

    assert score.evidence_completeness.total_claims == 0
    assert score.evidence_completeness.evidenced_claims == 0
    assert score.claim_veracity.matching_claims == 0
    assert score.claim_veracity.evidenced_claims == 0


def test_empty_evidence():
    """Claims exist but no evidence at all."""
    xref = CrossReferencer()
    claims = [Claim(text="Tests passed", category=ClaimCategory.TEST_RESULT, source_message_idx=0)]

    score = xref.cross_reference(claims, EvidenceSet())

    assert score.evidence_completeness.total_claims == 1
    assert score.evidence_completeness.evidenced_claims == 0
    assert score.claim_veracity.matching_claims == 0
    assert score.claim_veracity.evidenced_claims == 0
    assert len(claims[0].evidence) == 0
    assert score.risk_label == RiskLabel.HIGH
```
</action>

<acceptance_criteria>
- All 5 tests pass with `pytest tests/test_cross_referencer.py -v`
- Tests cover: exact match, semantic match, contradictory evidence, empty claims, empty evidence
- Uses inline EvidenceSet/Claim construction (same pattern as Phase 3 tests)
</acceptance_criteria>
</task>

<task id="p4-1-3">
<read_first>
- `SPEC.md` lines 56-65 (error loop detection), 290-303 (error loop details)
- `blackbox/models/event.py` — ToolUseEvent, ErrorEvent
- `blackbox/models/error_loop.py` — ErrorLoop, PatternType
- `blackbox/pipeline/cross_referencer.py` — existing pipeline patterns
</read_first>

<action>
Create `blackbox/pipeline/error_loop_detector.py`:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from blackbox.models.error_loop import ErrorLoop, PatternType
from blackbox.models.event import ErrorEvent, EventModel, ToolUseEvent


class ErrorLoopDetector:
    """Detects three error loop patterns in an EventModel."""

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
        """Detect repeated failing commands (same command, non-zero exit, 3+ times)."""
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

                time_range = (
                    occurrences[0].timestamp,
                    occurrences[-1].timestamp,
                ) if occurrences[0].timestamp else None

                return ErrorLoop(
                    pattern=PatternType.REPEATED_COMMAND,
                    description=f"Command '{cmd[:80]}' failed {len(occurrences)} times",
                    count=len(occurrences),
                    time_range=time_range,
                    details=stderr,
                )

        return None

    def _detect_circular_edits(self, events: EventModel) -> ErrorLoop | None:
        """Detect oscillating edits (4+ edits toggling between states)."""
        edit_paths: list[str] = []

        for event in events.events:
            if isinstance(event, ToolUseEvent) and event.tool_name in ("Edit", "Write"):
                path = event.input.get("path") or event.input.get("file_path", "")
                if path:
                    edit_paths.append(path)

        if len(edit_paths) < self.CIRCULAR_EDIT_THRESHOLD:
            return None

        # Detect oscillation: same path appearing non-consecutively
        seen_first: set[str] = set()
        for path in edit_paths:
            if path in seen_first:
                time_range = None
                # Find timestamps
                timestamps = [
                    e.timestamp for e in events.events
                    if isinstance(e, ToolUseEvent) and e.tool_name in ("Edit", "Write")
                    and (e.input.get("path") or e.input.get("file_path", "")) == path
                ]
                timestamps = [t for t in timestamps if t is not None]
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
        """Detect error spikes (5+ ErrorEvents within 60 seconds)."""
        error_events: list[ErrorEvent] = [
            e for e in events.events if isinstance(e, ErrorEvent) and e.timestamp
        ]

        if len(error_events) < self.ERROR_SPIKE_THRESHOLD:
            return None

        # Use type_counts to check for spike window
        error_events_sorted = sorted(error_events, key=lambda e: e.timestamp)

        for i in range(len(error_events_sorted) - self.ERROR_SPIKE_THRESHOLD + 1):
            window_events = error_events_sorted[i:i + self.ERROR_SPIKE_THRESHOLD]
            window_start = window_events[0].timestamp
            window_end = window_events[-1].timestamp

            if isinstance(window_start, datetime) and isinstance(window_end, datetime):
                if (window_end - window_start) <= timedelta(seconds=self.ERROR_SPIKE_WINDOW_SECONDS):
                    # Count error types in window
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
                        time_range=(first_ts, last_ts),
                        details=f"Error types in window: {dict(type_counts)}",
                    )

        return None
```
</action>

<acceptance_criteria>
- `detect()` returns `list[ErrorLoop]`
- RepeatedCommandDetector: catches 3+ same failing command
- CircularEditDetector: catches 4+ edits toggling between files
- ErrorSpikeDetector: catches 5+ ErrorEvents within 60 seconds
- Normal sessions return `[]`
- Single-failure sessions return `[]`
</acceptance_criteria>
</task>

<task id="p4-1-4">
<read_first>
- `blackbox/pipeline/error_loop_detector.py` — implementation to test
- `blackbox/models/event.py` — ToolUseEvent, ErrorEvent, EventModel construction
- `blackbox/models/error_loop.py` — ErrorLoop, PatternType
- `tests/test_evidence_collector.py` — existing test patterns
</read_first>

<action>
Create `tests/test_error_loop_detector.py` with 5 tests:

```python
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
    """Normal session with no error patterns returns empty list."""
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
    """Single failure (only 1 error) does not trigger error spike."""
    detector = ErrorLoopDetector()
    events = EventModel(
        session_id="test",
        events=[
            ToolUseEvent(timestamp=NOW, tool_name="Bash", input={"command": "failing-cmd"}, is_error=True),
            ErrorEvent(timestamp=NOW + timedelta(seconds=1), error_type="RuntimeError", message="single error"),
        ],
    )

    loops = detector.detect(events)

    # Single failure should not trigger any loop pattern
    assert len(loops) == 0
```
</action>

<acceptance_criteria>
- All 5 tests pass with `pytest tests/test_error_loop_detector.py -v`
- Tests cover: repeated command, circular edit, error spike, normal session, single failure
- Uses inline EventModel construction (same pattern as Phase 3 tests)
</acceptance_criteria>
</task>

<task id="p4-1-5">
<read_first>
- `blackbox/pipeline/__init__.py` — current exports
</read_first>

<action>
Update `blackbox/pipeline/__init__.py`:

```python
"""Pipeline stages for claim extraction, evidence collection, and scoring."""
from blackbox.pipeline.claim_extractor import ClaimExtractor
from blackbox.pipeline.cross_referencer import CrossReferencer
from blackbox.pipeline.error_loop_detector import ErrorLoopDetector
from blackbox.pipeline.evidence_collector import EvidenceCollector

__all__ = [
    "ClaimExtractor",
    "EvidenceCollector",
    "CrossReferencer",
    "ErrorLoopDetector",
]
```
</action>

<acceptance_criteria>
- `from blackbox.pipeline import CrossReferencer` succeeds
- `from blackbox.pipeline import ErrorLoopDetector` succeeds
- No circular import errors
</acceptance_criteria>
</task>

---

## Verification

```bash
pytest tests/test_cross_referencer.py tests/test_error_loop_detector.py -v
# Expected: 10 passed (5 cross_referencer + 5 error_loop_detector)
```

## Exit Criteria

- [ ] CrossReferencer correctly matches claims to evidence and produces LieScore
- [ ] CrossReferencer assigns per-claim confidence: exact, semantic, missing
- [ ] CrossReferencer handles all edge cases: no claims, no evidence, empty session, all contradictory
- [ ] ErrorLoopDetector detects all 3 patterns: repeated commands, circular edits, error spikes
- [ ] ErrorLoopDetector handles normal sessions (no loops), single-failure sessions (no false positive)
- [ ] 10 tests pass

## Must-haves

- [ ] CrossReferencer correctly matches claims to evidence and produces LieScore
- [ ] CrossReferencer assigns per-claim confidence levels
- [ ] ErrorLoopDetector detects all 3 patterns
- [ ] ErrorLoopDetector handles normal sessions (no false positives)
- [ ] 10 tests pass

## Stack Context

- Models: `blackbox/models/claim.py` (Claim, EvidenceRef, ClaimCategory, ConfidenceLevel), `blackbox/models/evidence.py` (EvidenceSet, EvidenceItem), `blackbox/models/score.py` (LieScore, EvidenceCompleteness, ClaimVeracity, RiskLabel, compute_risk_label), `blackbox/models/error_loop.py` (ErrorLoop, PatternType)
- Events: `blackbox/models/event.py` (EventModel, ToolUseEvent, ErrorEvent)
- Existing pipeline: `blackbox/pipeline/claim_extractor.py`, `blackbox/pipeline/evidence_collector.py`
- Tests follow established patterns: plain `def test_*`, `assert`, inline EventModel construction
</task>
</plan>
