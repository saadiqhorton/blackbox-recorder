"""Tests for the blackbox CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from blackbox.cli import app
from blackbox.models.score import (
    ClaimVeracity,
    EvidenceCompleteness,
    LieScore,
    RiskLabel,
)

runner = CliRunner()


def _make_event_model():
    """Return a minimal EventModel-like object for mock returns."""
    from blackbox.models.event import EventModel

    return EventModel(
        session_id="test-session",
        agent_type="claude-code",
        task="Fix login validation",
        events=[],
    )


def _make_lie_score() -> LieScore:
    """Return a low-risk LieScore for mock returns."""
    return LieScore(
        evidence_completeness=EvidenceCompleteness(evidenced_claims=2, total_claims=2),
        claim_veracity=ClaimVeracity(matching_claims=2, evidenced_claims=2),
        risk_label=RiskLabel.LOW,
    )


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


@patch("blackbox.cli.ReportGenerator")
@patch("blackbox.cli.ErrorLoopDetector")
@patch("blackbox.cli.CrossReferencer")
@patch("blackbox.cli.ClaimExtractor")
@patch("blackbox.cli.EvidenceCollector")
@patch("blackbox.cli.ClaudeCodeAdapter")
@patch("blackbox.cli.RunStore")
def test_analyze_command(
    mock_store,
    mock_adapter_cls,
    mock_collector_cls,
    mock_extractor_cls,
    mock_xref_cls,
    mock_detector_cls,
    mock_generator_cls,
    tmp_path: Path,
):
    """Run `blackbox analyze` on a real JSONL file; verify exit 0 and report output."""
    # Create a real fixture file inside tmp_path so it exists
    fixture = tmp_path / "honest_session.jsonl"
    fixture.write_text(
        '{"type":"user","sessionId":"s-001","timestamp":"2026-05-04T09:00:00Z"}\n'
        '{"type":"assistant","sessionId":"s-001","timestamp":"2026-05-04T09:00:03Z"}\n'
    )

    # --- wire mock returns ---
    event_model = _make_event_model()

    mock_adapter = mock_adapter_cls.return_value
    mock_adapter.ingest.return_value = event_model

    mock_collector = mock_collector_cls.return_value
    mock_collector.collect.return_value = MagicMock()

    mock_extractor = mock_extractor_cls.return_value
    mock_extractor.extract_claims.return_value = []

    mock_xref = mock_xref_cls.return_value
    mock_xref.cross_reference.return_value = _make_lie_score()

    mock_detector = mock_detector_cls.return_value
    mock_detector.detect.return_value = []

    mock_generator = mock_generator_cls.return_value
    mock_generator.generate.return_value = {
        "markdown": "# VERIFICATION REPORT\n\nAll good.",
        "json": {"report": "dummy"},
    }

    mock_store_instance = mock_store.return_value

    result = runner.invoke(app, ["analyze", str(fixture)])
    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stdout}"
    # Output should contain the markdown report
    assert "VERIFICATION REPORT" in result.stdout or "BLACK BOX RECORDER" in result.stdout


@patch("blackbox.cli.ReportGenerator")
@patch("blackbox.cli.ErrorLoopDetector")
@patch("blackbox.cli.CrossReferencer")
@patch("blackbox.cli.ClaimExtractor")
@patch("blackbox.cli.EvidenceCollector")
@patch("blackbox.cli.ClaudeCodeAdapter")
@patch("blackbox.cli.RunStore")
def test_analyze_json_flag(
    mock_store,
    mock_adapter_cls,
    mock_collector_cls,
    mock_extractor_cls,
    mock_xref_cls,
    mock_detector_cls,
    mock_generator_cls,
    tmp_path: Path,
):
    """Run `blackbox analyze --json` — output must be valid JSON."""
    fixture = tmp_path / "honest_session.jsonl"
    fixture.write_text(
        '{"type":"user","sessionId":"s-001","timestamp":"2026-05-04T09:00:00Z"}\n'
    )

    event_model = _make_event_model()

    mock_adapter = mock_adapter_cls.return_value
    mock_adapter.ingest.return_value = event_model

    mock_collector = mock_collector_cls.return_value
    mock_collector.collect.return_value = MagicMock()

    mock_extractor = mock_extractor_cls.return_value
    mock_extractor.extract_claims.return_value = []

    mock_xref = mock_xref_cls.return_value
    mock_xref.cross_reference.return_value = _make_lie_score()

    mock_detector = mock_detector_cls.return_value
    mock_detector.detect.return_value = []

    mock_generator = mock_generator_cls.return_value
    mock_generator.generate.return_value = {
        "markdown": "# VERIFICATION REPORT",
        "json": {"report": "dummy", "risk": "low"},
    }

    mock_store_instance = mock_store.return_value

    result = runner.invoke(app, ["analyze", "--json", str(fixture)])
    assert result.exit_code == 0, f"exit_code={result.exit_code}"

    # Output should be parseable JSON
    output = result.stdout.strip()
    assert output.startswith("{"), f"expected JSON object, got: {output[:200]}"
    parsed = json.loads(output)
    assert "report" in parsed


def test_analyze_missing_file(tmp_path: Path):
    """Run `blackbox analyze` on a nonexistent file — expect non-zero exit."""
    result = runner.invoke(app, ["analyze", str(tmp_path / "nonexistent.jsonl")])
    assert result.exit_code != 0, "expected non-zero exit for missing file"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@patch("blackbox.cli.RunStore")
def test_list_command(mock_store_cls):
    """Run `blackbox list` — verify table output with run IDs."""
    mock_store = mock_store_cls.return_value
    mock_store.list_runs.return_value = [
        {
            "run_id": "abc123",
            "created_at": "2026-05-04T09:00:00",
            "agent_type": "claude-code",
            "event_count": 5,
            "status": "analyzed",
        },
        {
            "run_id": "def456",
            "created_at": "2026-05-03T10:00:00",
            "agent_type": "claude-code",
            "event_count": 3,
            "status": "recorded",
        },
    ]

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, f"exit_code={result.exit_code}"
    assert "abc123" in result.stdout
    assert "def456" in result.stdout
    # Table headers
    assert "Run ID" in result.stdout or "Black Box Runs" in result.stdout


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@patch("blackbox.cli.get_config_path")
@patch("blackbox.config.get_config_path")
def test_config_commands(mock_config_get_path, mock_cli_get_path, tmp_path: Path):
    """Test `blackbox config show` and `blackbox config init` with isolated config dir."""
    config_dir = tmp_path / ".blackbox"
    config_path = config_dir / "config.yaml"
    mock_config_get_path.return_value = config_path
    mock_cli_get_path.return_value = config_path

    # --- config init ---
    result_init = runner.invoke(app, ["config", "init"])
    assert result_init.exit_code == 0, f"exit_code={result_init.exit_code}"
    assert "Created" in result_init.stdout or "config" in result_init.stdout.lower()
    assert config_path.exists(), "config init did not create the file"

    # --- config show ---
    result_show = runner.invoke(app, ["config", "show"])
    assert result_show.exit_code == 0, f"exit_code={result_show.exit_code}"
    assert "Config file:" in result_show.stdout
    # YAML config content should be displayed (Rich may wrap long paths)
    assert "llm" in result_show.stdout.lower() or "provider" in result_show.stdout.lower()
    assert ".blackbox" in result_show.stdout
