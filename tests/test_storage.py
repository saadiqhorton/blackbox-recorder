"""Tests for RunStore save/load round-trips."""

from datetime import datetime

from blackbox.models.claim import Claim, ClaimCategory
from blackbox.models.error_loop import ErrorLoop, PatternType
from blackbox.models.evidence import EvidenceItem, EvidenceSet
from blackbox.models.score import EvidenceCompleteness, ClaimVeracity, LieScore, RiskLabel
from blackbox.storage.run_store import RunMetadata, RunStore

NOW = datetime(2025, 6, 1)


def test_save_and_load_claims(tmp_path):
    """Save a list of Claim objects, then load them back as dicts with correct fields."""
    store = RunStore(base_dir=tmp_path)
    run_id = "test-claims"
    store.create_run(RunMetadata(run_id=run_id, created_at=NOW))

    claims = [
        Claim(text="Tests passed", category=ClaimCategory.TEST_RESULT, source_message_idx=0),
        Claim(text="Refactored core module", category=ClaimCategory.OUTCOME, source_message_idx=1),
    ]

    result_path = store.save_claims(run_id, claims)
    assert result_path.exists()
    assert result_path.name == "claims.json"

    loaded = store.load_claims(run_id)
    assert len(loaded) == 2
    assert loaded[0]["text"] == "Tests passed"
    assert loaded[0]["category"] == "test_result"
    assert loaded[1]["text"] == "Refactored core module"
    assert loaded[1]["category"] == "outcome"


def test_save_and_load_score(tmp_path):
    """Save a LieScore, then load it back with correct percentages and risk_label."""
    store = RunStore(base_dir=tmp_path)
    run_id = "test-score"
    store.create_run(RunMetadata(run_id=run_id, created_at=NOW))

    score = LieScore(
        evidence_completeness=EvidenceCompleteness(evidenced_claims=3, total_claims=4),
        claim_veracity=ClaimVeracity(matching_claims=2, evidenced_claims=3),
        risk_label=RiskLabel.MEDIUM,
    )

    result_path = store.save_score(run_id, score)
    assert result_path.exists()
    assert result_path.name == "score.json"

    loaded = store.load_score(run_id)
    assert loaded["evidence_completeness"]["evidenced_claims"] == 3
    assert loaded["evidence_completeness"]["total_claims"] == 4
    assert loaded["claim_veracity"]["matching_claims"] == 2
    assert loaded["claim_veracity"]["evidenced_claims"] == 3
    assert loaded["risk_label"] == "medium"


def test_save_and_load_error_loops(tmp_path):
    """Save a list of ErrorLoop objects, then load them back as matching dicts."""
    store = RunStore(base_dir=tmp_path)
    run_id = "test-error-loops"
    store.create_run(RunMetadata(run_id=run_id, created_at=NOW))

    loops = [
        ErrorLoop(
            pattern=PatternType.REPEATED_COMMAND,
            description="npm install ran 5 times",
            count=5,
            details="Same install command triggered repeatedly",
        ),
        ErrorLoop(
            pattern=PatternType.ERROR_SPIKE,
            description="TypeError spiked 12 times",
            count=12,
            details="Multiple TypeError exceptions in sequence",
        ),
    ]

    result_path = store.save_error_loops(run_id, loops)
    assert result_path.exists()
    assert result_path.name == "error_loops.json"

    loaded = store.load_error_loops(run_id)
    assert len(loaded) == 2
    assert loaded[0]["pattern"] == "repeated_command"
    assert loaded[0]["count"] == 5
    assert loaded[0]["description"] == "npm install ran 5 times"
    assert loaded[1]["pattern"] == "error_spike"
    assert loaded[1]["count"] == 12


def test_save_and_load_report(tmp_path):
    """Save a report dict, then load it back unchanged."""
    store = RunStore(base_dir=tmp_path)
    run_id = "test-report"
    store.create_run(RunMetadata(run_id=run_id, created_at=NOW))

    report = {
        "summary": "Analysis complete",
        "total_claims": 10,
        "high_risk_claims": 2,
        "recommendations": ["Review error handling", "Add more tests"],
    }

    result_path = store.save_report(run_id, report)
    assert result_path.exists()
    assert result_path.name == "report.json"

    loaded = store.load_report(run_id)
    assert loaded == report
    assert loaded["summary"] == "Analysis complete"
    assert loaded["recommendations"] == ["Review error handling", "Add more tests"]


def test_list_runs_after_save(tmp_path):
    """Multiple runs with saves appear in list_runs sorted by created_at desc."""
    store = RunStore(base_dir=tmp_path)

    run_a = "run-alpha"
    run_b = "run-beta"
    run_c = "run-gamma"

    store.create_run(RunMetadata(run_id=run_a, created_at=NOW, task="First run"))
    store.create_run(RunMetadata(run_id=run_b, created_at=datetime(2025, 7, 1), task="Second run"))
    store.create_run(RunMetadata(run_id=run_c, created_at=datetime(2025, 8, 1), task="Third run"))

    store.save_claims(run_a, [Claim(text="Alpha claim", category=ClaimCategory.STATE, source_message_idx=0)])
    store.save_score(run_b, LieScore(
        evidence_completeness=EvidenceCompleteness(evidenced_claims=1, total_claims=1),
        claim_veracity=ClaimVeracity(matching_claims=1, evidenced_claims=1),
        risk_label=RiskLabel.LOW,
    ))
    store.save_report(run_c, {"summary": "Gamma report"})

    runs = store.list_runs()
    assert len(runs) == 3

    # Verify descending created_at order
    assert runs[0]["run_id"] == "run-gamma"
    assert runs[1]["run_id"] == "run-beta"
    assert runs[2]["run_id"] == "run-alpha"

    # Verify tasks are preserved
    assert runs[2]["task"] == "First run"
    assert runs[1]["task"] == "Second run"
    assert runs[0]["task"] == "Third run"

    # Verify all runs exist
    assert store.run_exists(run_a)
    assert store.run_exists(run_b)
    assert store.run_exists(run_c)
