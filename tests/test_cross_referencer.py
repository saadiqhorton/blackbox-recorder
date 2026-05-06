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
    """Claim about tests passing matched against successful command — EXACT confidence."""
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
    """Claim about outcome with no exact match but relevant evidence present — SEMANTIC."""
    xref = CrossReferencer()
    claims = [Claim(text="The refactor improved code quality", category=ClaimCategory.OUTCOME, source_message_idx=0)]
    evidence = _make_evidence(commands=[("git commit", False)], file_changes=["src/main.py"])

    score = xref.cross_reference(claims, evidence)

    assert score.evidence_completeness.evidenced_claims == 1
    assert claims[0].evidence
    semantic_refs = [r for r in claims[0].evidence if r.get("confidence") == ConfidenceLevel.SEMANTIC]
    assert len(semantic_refs) >= 1


def test_contradictory_evidence():
    """Claim says tests pass but command evidence shows failure — no EXACT match."""
    xref = CrossReferencer()
    claims = [Claim(text="Tests passed successfully", category=ClaimCategory.TEST_RESULT, source_message_idx=0)]
    evidence = _make_evidence(commands=[("pytest", True)])

    score = xref.cross_reference(claims, evidence)

    assert score.evidence_completeness.total_claims == 1
    if len(claims[0].evidence) > 0:
        exact = [r for r in claims[0].evidence if r.get("confidence") == ConfidenceLevel.EXACT]
        assert len(exact) == 0


def test_empty_claims():
    """No claims to cross-reference — returns zeroed LieScore."""
    xref = CrossReferencer()
    evidence = _make_evidence(commands=[("pytest", False)])

    score = xref.cross_reference([], evidence)

    assert score.evidence_completeness.total_claims == 0
    assert score.evidence_completeness.evidenced_claims == 0
    assert score.claim_veracity.matching_claims == 0
    assert score.claim_veracity.evidenced_claims == 0


def test_empty_evidence():
    """Claims exist but no evidence at all — all MISSING, risk HIGH."""
    xref = CrossReferencer()
    claims = [Claim(text="Tests passed", category=ClaimCategory.TEST_RESULT, source_message_idx=0)]

    score = xref.cross_reference(claims, EvidenceSet())

    assert score.evidence_completeness.total_claims == 1
    assert score.evidence_completeness.evidenced_claims == 0
    assert score.claim_veracity.matching_claims == 0
    assert score.claim_veracity.evidenced_claims == 0
    assert len(claims[0].evidence) == 0
    assert score.risk_label == RiskLabel.HIGH
