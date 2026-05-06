"""Tests for the ReportGenerator pipeline stage."""

from datetime import datetime

from blackbox.models.claim import Claim, ClaimCategory, ConfidenceLevel, EvidenceRef
from blackbox.models.error_loop import ErrorLoop, PatternType
from blackbox.models.score import (
    ClaimVeracity,
    EvidenceCompleteness,
    LieScore,
    RiskLabel,
    compute_risk_label,
)
from blackbox.pipeline.report_generator import ReportGenerator


SESSION_INFO = {
    "session_id": "test-session-001",
    "agent_type": "claude",
    "task": "implement login feature",
    "duration": "12m 34s",
    "analyzed_at": "2025-01-15T10:30:00Z",
}


def _make_full_score() -> LieScore:
    """80% completeness, 75% veracity, MEDIUM risk."""
    ec = EvidenceCompleteness(evidenced_claims=4, total_claims=5)
    cv = ClaimVeracity(matching_claims=3, evidenced_claims=4)
    return LieScore(evidence_completeness=ec, claim_veracity=cv, risk_label=RiskLabel.MEDIUM)


def _make_claims() -> list[Claim]:
    """Two claims: one exact, one semantic."""
    return [
        Claim(
            text="Tests passed successfully",
            category=ClaimCategory.TEST_RESULT,
            source_message_idx=0,
            evidence=[
                EvidenceRef(
                    source="pytest",
                    type="command",
                    value="pytest --passed",
                    confidence=ConfidenceLevel.EXACT,
                )
            ],
        ),
        Claim(
            text="The refactor improved code quality",
            category=ClaimCategory.OUTCOME,
            source_message_idx=1,
            evidence=[
                EvidenceRef(
                    source="code review",
                    type="diff",
                    value="positive diff output",
                    confidence=ConfidenceLevel.SEMANTIC,
                )
            ],
        ),
    ]


def _make_error_loops() -> list[ErrorLoop]:
    return [
        ErrorLoop(
            pattern=PatternType.REPEATED_COMMAND,
            description="Repeated pytest invocation",
            count=3,
            time_range=(datetime(2025, 1, 15, 10, 0), datetime(2025, 1, 15, 10, 5)),
            details="pytest ran 3 times in 5 minutes",
        )
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_report_all_data():
    """Generate with full data — verify markdown and JSON content."""
    generator = ReportGenerator()
    score = _make_full_score()
    claims = _make_claims()
    error_loops = _make_error_loops()

    result = generator.generate(SESSION_INFO, score, claims, error_loops)

    md = result["markdown"]
    js = result["json"]

    # Markdown structure
    assert "VERIFICATION REPORT" in md
    assert "EVIDENCE COMPLETENESS: 80%" in md
    assert "CLAIM VERACITY: 75%" in md
    assert "RISK: MEDIUM" in md
    assert "review before accepting" in md

    # Claim texts appear (truncated to 30 chars in markdown)
    assert "Tests passed successfully" in md
    assert "The refactor improved code qua" in md

    # Error loop
    assert "Repeated pytest invocation" in md

    # JSON keys
    assert "markdown" in result
    assert "json" in result
    assert "scores" in js
    assert "claims" in js
    assert "error_loops" in js


def test_report_no_claims():
    """Empty claims list — 0% scores, verify compute_risk_label result."""
    generator = ReportGenerator()
    ec = EvidenceCompleteness(evidenced_claims=0, total_claims=0)
    cv = ClaimVeracity(matching_claims=0, evidenced_claims=0)
    risk = compute_risk_label(0, 0)  # both < 50 → HIGH
    score = LieScore(evidence_completeness=ec, claim_veracity=cv, risk_label=risk)
    error_loops = _make_error_loops()

    result = generator.generate(SESSION_INFO, score, [], error_loops)

    md = result["markdown"]
    js = result["json"]

    # compute_risk_label(0, 0) yields HIGH
    assert risk == RiskLabel.HIGH

    # Score shows 0%
    assert "0%" in md
    assert "0/0" in md

    # No claim text appears
    assert "Tests passed" not in md

    # Error loops still rendered
    assert "Repeated pytest invocation" in md

    # JSON empty claims list
    assert js["claims"] == []


def test_report_empty_session():
    """Empty claims, empty error loops, zeroed score — basic structure remains."""
    generator = ReportGenerator()
    ec = EvidenceCompleteness(evidenced_claims=0, total_claims=0)
    cv = ClaimVeracity(matching_claims=0, evidenced_claims=0)
    score = LieScore(
        evidence_completeness=ec,
        claim_veracity=cv,
        risk_label=compute_risk_label(0, 0),
    )

    result = generator.generate(SESSION_INFO, score, [], [])

    md = result["markdown"]
    js = result["json"]

    # Basic scaffolding survives
    assert "VERIFICATION REPORT" in md
    assert "RISK:" in md
    assert "0%" in md
    assert md.count("0%") >= 2  # completeness and veracity

    # No CLAIMS section body for empty list — but "CLAIMS:" heading exists
    assert "CLAIMS:" in md

    # No error loops
    assert "ERROR LOOPS:" not in md

    # JSON is not None
    assert js is not None
    assert js["claims"] == []
    assert js["error_loops"] == []


def test_report_json_output():
    """Verify JSON structure matches expected schema."""
    generator = ReportGenerator()
    score = _make_full_score()
    claims = _make_claims()
    error_loops = _make_error_loops()

    js = generator.generate(SESSION_INFO, score, claims, error_loops)["json"]

    # --- session ---
    sess = js["session"]
    assert sess["id"] == "test-session-001"
    assert sess["agent"] == "claude"
    assert sess["task"] == "implement login feature"
    assert sess["duration"] == "12m 34s"
    assert sess["analyzed_at"] == "2025-01-15T10:30:00Z"

    # --- scores ---
    scores = js["scores"]
    ec = scores["evidence_completeness"]
    assert ec["percentage"] == 80
    assert ec["evidenced_claims"] == 4
    assert ec["total_claims"] == 5

    cv = scores["claim_veracity"]
    assert cv["percentage"] == 75
    assert cv["matching_claims"] == 3
    assert cv["evidenced_claims"] == 4

    risk = scores["risk"]
    assert risk["label"] == "MEDIUM"
    assert risk["message"] == "review before accepting"

    # --- claims ---
    assert len(js["claims"]) == 2
    c1 = js["claims"][0]
    assert c1["text"] == "Tests passed successfully"
    assert c1["category"] == "test_result"
    assert c1["confidence"] == "exact"
    assert len(c1["evidence"]) == 1
    assert c1["evidence"][0]["source"] == "pytest"
    assert c1["evidence"][0]["type"] == "command"
    assert c1["evidence"][0]["value"] == "pytest --passed"
    assert c1["evidence"][0]["confidence"] == "exact"

    c2 = js["claims"][1]
    assert c2["text"] == "The refactor improved code quality"
    assert c2["category"] == "outcome"
    assert c2["confidence"] == "semantic"
    assert len(c2["evidence"]) == 1
    assert c2["evidence"][0]["confidence"] == "semantic"

    # --- error_loops ---
    assert len(js["error_loops"]) == 1
    el = js["error_loops"][0]
    assert el["pattern"] == "repeated_command"
    assert el["description"] == "Repeated pytest invocation"
    assert el["count"] == 3
    assert el["details"] == "pytest ran 3 times in 5 minutes"
