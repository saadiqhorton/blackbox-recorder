"""End-to-end pipeline integration tests using golden fixtures.

Tests exercise the full adapter -> evidence -> cross-ref -> report chain
with only the LLM-dependent ClaimExtractor mocked.
"""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from blackbox.cli import app

runner = CliRunner()

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "test_fixtures"

# ClaimExtractor is the only pipeline stage that requires an LLM call.
# Mock it at the cli import site to avoid API dependency in tests.
PATCH_EXTRACTOR = "blackbox.cli.ClaimExtractor"


def _assert_valid_pipeline_output(data: dict) -> None:
    """Assert pipeline JSON output has all expected top-level keys."""
    assert "session" in data, "missing session"
    assert "scores" in data, "missing scores"
    assert "claims" in data, "missing claims"
    assert "error_loops" in data, "missing error_loops"

    s = data["scores"]
    assert "evidence_completeness" in s, "missing evidence_completeness"
    assert "claim_veracity" in s, "missing claim_veracity"
    assert "risk" in s, "missing risk"

    # Type and range validation
    ec = s["evidence_completeness"]
    assert "percentage" in ec, "missing ec.percentage"
    assert isinstance(ec["percentage"], int), f"ec.percentage must be int, got {type(ec['percentage'])}"
    assert 0 <= ec["percentage"] <= 100, f"ec.percentage out of range: {ec['percentage']}"

    cv = s["claim_veracity"]
    assert "percentage" in cv, "missing cv.percentage"
    assert isinstance(cv["percentage"], int), f"cv.percentage must be int, got {type(cv['percentage'])}"
    assert 0 <= cv["percentage"] <= 100, f"cv.percentage out of range: {cv['percentage']}"

    assert "label" in s["risk"], "missing risk.label"
    assert isinstance(s["risk"]["label"], str), "risk.label must be str"
    assert s["risk"]["label"] in ("LOW", "MEDIUM", "HIGH"), f"unknown risk label: {s['risk']['label']}"


# ---------------------------------------------------------------------------
# Golden fixture tests
# ---------------------------------------------------------------------------


@patch(PATCH_EXTRACTOR)
def test_e2e_honest_session(mock_extractor_cls):
    """Full pipeline on honest_session.jsonl -- all stages complete, valid report."""
    mock_extractor_cls.return_value.extract_claims.return_value = []

    with runner.isolated_filesystem():
        result = runner.invoke(app, [
            "analyze", "--json", str(FIXTURES_DIR / "honest_session.jsonl"),
        ])

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stdout={result.stdout[:500]}"
    data = json.loads(result.stdout)
    _assert_valid_pipeline_output(data)
    # real session should parse events
    assert len(data["session"]["id"]) > 0, "expected non-empty session id"


@patch(PATCH_EXTRACTOR)
def test_e2e_dishonest_session(mock_extractor_cls):
    """Full pipeline on dishonest_session.jsonl -- evidence and report produced."""
    mock_extractor_cls.return_value.extract_claims.return_value = []

    with runner.isolated_filesystem():
        result = runner.invoke(app, [
            "analyze", "--json", str(FIXTURES_DIR / "dishonest_session.jsonl"),
        ])

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stdout={result.stdout[:500]}"
    data = json.loads(result.stdout)
    _assert_valid_pipeline_output(data)
    # Should have evidence items from collected events
    assert "evidence_completeness" in data["scores"]
    assert "claim_veracity" in data["scores"]


@patch(PATCH_EXTRACTOR)
def test_e2e_ambiguous_session(mock_extractor_cls):
    """Full pipeline on ambiguous_session.jsonl -- completes without crash."""
    mock_extractor_cls.return_value.extract_claims.return_value = []

    with runner.isolated_filesystem():
        result = runner.invoke(app, [
            "analyze", "--json", str(FIXTURES_DIR / "ambiguous_session.jsonl"),
        ])

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stdout={result.stdout[:500]}"
    data = json.loads(result.stdout)
    _assert_valid_pipeline_output(data)


@patch(PATCH_EXTRACTOR)
def test_e2e_empty_session(mock_extractor_cls):
    """Full pipeline on empty_session.jsonl -- graceful handling of zero events."""
    mock_extractor_cls.return_value.extract_claims.return_value = []

    with runner.isolated_filesystem():
        result = runner.invoke(app, [
            "analyze", "--json", str(FIXTURES_DIR / "empty_session.jsonl"),
        ])

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stdout={result.stdout[:500]}"
    data = json.loads(result.stdout)
    _assert_valid_pipeline_output(data)
    # zero events -> no evidence, no claims, no loops
    assert len(data["claims"]) == 0
    assert len(data["error_loops"]) == 0


@patch(PATCH_EXTRACTOR)
def test_e2e_corrupt_session(mock_extractor_cls):
    """Full pipeline on corrupt_session.jsonl -- malformed lines skipped, pipeline recovers."""
    mock_extractor_cls.return_value.extract_claims.return_value = []

    with runner.isolated_filesystem():
        result = runner.invoke(app, [
            "analyze", "--json", str(FIXTURES_DIR / "corrupt_session.jsonl"),
        ])

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stdout={result.stdout[:500]}"
    data = json.loads(result.stdout)
    _assert_valid_pipeline_output(data)
    # At least the valid lines should have been parsed (4+ valid events)
    assert len(data["session"].get("id", "")) > 0
