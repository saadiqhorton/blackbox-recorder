import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from blackbox.adapters.claude_code import ClaudeCodeAdapter
from blackbox.config import (
    get_config_path,
    load_config,
    save_default_config,
)
from blackbox.discovery import find_latest_sessions, resolve_project_dir
from blackbox.pipeline.claim_extractor import ClaimExtractor
from blackbox.pipeline.cross_referencer import CrossReferencer
from blackbox.pipeline.error_loop_detector import ErrorLoopDetector
from blackbox.pipeline.evidence_collector import EvidenceCollector
from blackbox.pipeline.report_generator import ReportGenerator
from blackbox.storage.run_store import RunMetadata, RunStore

app = typer.Typer(
    name="blackbox",
    help="Agent Black Box Recorder -- forensic pre-commit verification",
    no_args_is_help=True,
)
console = Console()


@dataclass
class AnalysisResult:
    session_info: dict
    score: object
    claims: list
    evidence_set: object
    error_loops: list
    report: dict
    event_count: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_get(config: dict, key: str):
    parts = key.split(".")
    for part in parts:
        if isinstance(config, dict) and part in config:
            config = config[part]
        else:
            return None
    return config


def _config_set(config: dict, key: str, value):
    parts = key.split(".")
    for part in parts[:-1]:
        config = config.setdefault(part, {})
    config[parts[-1]] = value


# ---------------------------------------------------------------------------
# Pipeline helper (shared by single-session and --latest paths)
# ---------------------------------------------------------------------------

def _run_pipeline(session_path: Path, progress: Progress) -> AnalysisResult:
    """Execute the full analysis pipeline on a single session file."""
    # 1. Parse JSONL
    progress.update(
        progress.add_task("Parsing session file...", total=None),
        description=f"Parsing {session_path.name}...",
    )
    adapter = ClaudeCodeAdapter()
    event_model = adapter.ingest(session_path)

    # 2. Collect evidence
    progress.update(
        progress.add_task("Collecting evidence...", total=None),
        description="Collecting evidence...",
    )
    collector = EvidenceCollector()
    evidence_set = collector.collect(event_model)

    # 3. Extract claims (may fail -- LLM unavailable)
    progress.update(
        progress.add_task("Extracting claims with LLM...", total=None),
        description="Extracting claims with LLM...",
    )
    try:
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(event_model)
    except Exception as e:
        console.print(f"[yellow]Warning: LLM claim extraction failed ({e})[/yellow]")
        console.print("[yellow]Continuing with partial report (no claims)[/yellow]")
        claims = []

    # 4. Cross-reference
    progress.update(
        progress.add_task("Cross-referencing claims against evidence...", total=None),
        description="Cross-referencing claims against evidence...",
    )
    xref = CrossReferencer()
    score = xref.cross_reference(claims, evidence_set)

    # 5. Detect error loops
    progress.update(
        progress.add_task("Detecting error loops...", total=None),
        description="Detecting error loops...",
    )
    detector = ErrorLoopDetector()
    error_loops = detector.detect(event_model)

    # 6. Session info
    analyzed_at = datetime.now(timezone.utc).isoformat()
    duration = ""
    if event_model.events:
        first_ts = event_model.events[0].timestamp
        last_ts = event_model.events[-1].timestamp
        if isinstance(first_ts, datetime) and isinstance(last_ts, datetime):
            elapsed = (last_ts - first_ts).total_seconds()
            duration = f"{elapsed:.0f}s"

    session_info = {
        "session_id": event_model.session_id,
        "agent_type": event_model.agent_type,
        "task": event_model.task or "",
        "duration": duration,
        "analyzed_at": analyzed_at,
    }

    # 7. Generate report
    progress.update(
        progress.add_task("Generating report...", total=None),
        description="Generating report...",
    )
    generator = ReportGenerator()
    report = generator.generate(session_info, score, claims, error_loops)

    return AnalysisResult(
        session_info=session_info,
        score=score,
        claims=claims,
        evidence_set=evidence_set,
        error_loops=error_loops,
        report=report,
        event_count=len(event_model.events),
    )


def _save_run(result: AnalysisResult, progress: Progress) -> str:
    """Persist analysis results and return the run_id."""
    run_id = uuid.uuid4().hex[:8]
    progress.update(
        progress.add_task("Saving results...", total=None),
        description="Saving results...",
    )
    store = RunStore()
    metadata = RunMetadata(
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        agent_type=result.session_info.get("agent_type", ""),
        task=result.session_info.get("task", ""),
        event_count=result.event_count,
        status="analyzed",
    )
    store.create_run(metadata)
    store.save_evidence(run_id, result.evidence_set)
    store.save_claims(run_id, result.claims)
    store.save_score(run_id, result.score)
    store.save_error_loops(run_id, result.error_loops)
    store.save_report(run_id, result.report["json"])
    return run_id


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

@app.command()
def analyze(
    path: str = typer.Argument(None, help="Path to session JSONL file"),
    latest: bool = typer.Option(False, "--latest", "-l", help="Auto-discover most recent session(s)"),
    sessions_count: int = typer.Option(1, "--sessions", "-n", help="Number of recent sessions (with --latest)"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
):
    """Analyze a session file for claims, evidence, and verification scores."""
    # --- Resolve session paths ---
    session_paths: list[Path] = []

    if latest:
        cfg = load_config()
        claude_dir = cfg.session.claude_dir
        project_dir = resolve_project_dir(claude_dir)
        session_paths = find_latest_sessions(project_dir, sessions_count)

        if not session_paths:
            console.print(f"[red]No Claude Code sessions found for this project.[/red]")
            console.print(f"[yellow]Checked: {project_dir}[/yellow]")
            raise SystemExit(1)
    elif path:
        p = Path(path)
        if not p.exists():
            console.print(f"[red]No session file at {path}[/red]")
            raise SystemExit(1)
        session_paths = [p]
    else:
        console.print("[red]Provide a session path or use --latest to auto-discover.[/red]")
        raise SystemExit(1)

    # --- Run pipeline ---
    results: list[AnalysisResult] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        for sp in session_paths:
            try:
                result = _run_pipeline(sp, progress)
                _save_run(result, progress)
                results.append(result)
            except FileNotFoundError:
                console.print(f"[red]Session file not found: {sp}[/red]")
                raise SystemExit(1)
            except Exception as e:
                console.print(f"[red]Error analyzing {sp.name}: {e}[/red]")
                raise SystemExit(1)

        progress.update(
            progress.add_task("[green]Done!", total=None),
            description="[green]Done!",
        )

    # --- Display results ---
    if json_output:
        if len(results) == 1:
            console.print(json.dumps(results[0].report["json"], indent=2), markup=False)
        else:
            summary = _build_multi_summary(results)
            console.print(json.dumps(summary, indent=2), markup=False)
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_session_header(result)
            console.print(result.report["markdown"])


def _build_multi_summary(results: list[AnalysisResult]) -> dict:
    """Build a compact JSON summary across multiple sessions."""
    return {
        "sessions_analyzed": len(results),
        "results": [
            {
                "session_id": r.session_info.get("session_id"),
                "task": r.session_info.get("task"),
                "score": {
                    "evidence_completeness": r.score.evidence_completeness.evidenced_claims / r.score.evidence_completeness.total_claims if r.score.evidence_completeness.total_claims > 0 else 0,
                    "claim_veracity": r.score.claim_veracity.matching_claims / r.score.claim_veracity.evidenced_claims if r.score.claim_veracity.evidenced_claims > 0 else 0,
                    "risk_label": r.score.risk_label.value if r.score.risk_label else "unknown",
                },
            }
            for r in results
        ],
    }


def _print_session_header(result: AnalysisResult) -> None:
    """Print a separator header for multi-session output."""
    sid = result.session_info.get("session_id", "?")
    task = result.session_info.get("task", "")
    console.print(f"\n[bold cyan]── Session: {sid}[/bold cyan]")
    if task:
        console.print(f"[dim]{task}[/dim]")
    console.print("")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command()
def list(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of runs to show"),
):
    """List previously analyzed runs."""
    store = RunStore()
    runs = store.list_runs()

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(title="Black Box Runs")
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="green")
    table.add_column("Agent", style="blue")
    table.add_column("Events", style="yellow")
    table.add_column("Status", style="magenta")

    for run in runs[:limit]:
        table.add_row(
            run.get("run_id", "?"),
            run.get("created_at", "?")[:19] if run.get("created_at") else "?",
            run.get("agent_type", "?"),
            str(run.get("event_count", 0)),
            run.get("status", "?"),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run ID to regenerate report for"),
):
    """Regenerate a verification report for a previously analyzed run."""
    store = RunStore()

    if not store.run_exists(run_id):
        console.print(f"[red]No run found: {run_id}[/red]")
        raise SystemExit(1)

    try:
        metadata = store.load_metadata(run_id)
        claims_data = store.load_claims(run_id)
        evidence_data = store.load_evidence(run_id)
        score_data = store.load_score(run_id)
        loops_data = store.load_error_loops(run_id)
    except FileNotFoundError as e:
        console.print(f"[red]Run artifacts missing: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error loading run data: {e}[/red]")
        raise SystemExit(1)

    # Reconstruct simple dicts for ReportGenerator
    # The generator expects LieScore, list[Claim], list[ErrorLoop] objects
    # but we stored them as dicts. Rehydrate from the raw dicts.
    from blackbox.models.claim import Claim
    from blackbox.models.error_loop import ErrorLoop
    from blackbox.models.score import LieScore, EvidenceCompleteness, ClaimVeracity, RiskLabel

    try:
        claims = [Claim(**c) for c in claims_data]
        error_loops = [ErrorLoop(**l) for l in loops_data]

        ec = EvidenceCompleteness(
            evidenced_claims=score_data["evidence_completeness"]["evidenced_claims"],
            total_claims=score_data["evidence_completeness"]["total_claims"],
        )
        cv = ClaimVeracity(
            matching_claims=score_data["claim_veracity"]["matching_claims"],
            evidenced_claims=score_data["claim_veracity"]["evidenced_claims"],
        )
        score = LieScore(
            evidence_completeness=ec,
            claim_veracity=cv,
            risk_label=RiskLabel(score_data["risk_label"]),
        )
    except (KeyError, ValueError) as e:
        console.print(f"[red]Corrupted run data: {e}[/red]")
        raise SystemExit(1)

    session_info = {
        "session_id": metadata.get("run_id", run_id),
        "agent_type": metadata.get("agent_type", ""),
        "task": metadata.get("task", ""),
        "duration": "",
        "analyzed_at": metadata.get("created_at", ""),
    }

    generator = ReportGenerator()
    report = generator.generate(session_info, score, claims, error_loops)

    console.print(report["markdown"])


# ---------------------------------------------------------------------------
# config  (subcommand group)
# ---------------------------------------------------------------------------

config_app = typer.Typer(help="Manage configuration.")
app.add_typer(config_app, name="config")


@config_app.command()
def get(
    key: str = typer.Argument(..., help="Config key (dot notation, e.g. llm.provider)"),
):
    """Get a config value by key (dot notation)."""
    cfg = load_config()
    cfg_dict = cfg.model_dump()
    value = _config_get(cfg_dict, key)
    if value is None:
        console.print(f"[yellow]Unknown key: {key}[/yellow]")
    else:
        console.print(f"{key} = {value}")


@config_app.command()
def set(
    key: str = typer.Argument(..., help="Config key (dot notation, e.g. llm.provider)"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a config value by key (dot notation)."""
    cfg_path = get_config_path()
    if cfg_path.is_file():
        with open(cfg_path) as f:
            cfg_data = yaml.safe_load(f) or {}
    else:
        cfg_data = {}

    # Coerce common types
    typed_value: str | int | None = value
    if value.lower() == "true":
        typed_value = True
    elif value.lower() == "false":
        typed_value = False
    elif value.lower() == "null" or value.lower() == "none":
        typed_value = None
    else:
        try:
            typed_value = int(value)
        except ValueError:
            typed_value = value

    # Warn on sensitive credential keys (CSO F1)
    if "api_key" in key or "secret" in key.lower() or "password" in key.lower() or "token" in key.lower():
        console.print("[yellow]Warning: Setting credentials via CLI exposes them in process listings and shell history.[/yellow]")
        console.print("[yellow]Consider using the BLACKBOX_LLM_API_KEY environment variable instead.[/yellow]")

    _config_set(cfg_data, key, typed_value)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.dump(cfg_data, f, default_flow_style=False)

    console.print(f"[green]Set[/green] {key} = {typed_value}")


@config_app.command()
def show():
    """Show full configuration."""
    cfg = load_config()
    cfg_path = get_config_path()
    console.print(f"Config file: {cfg_path}")
    console.print()
    cfg_dict = cfg.model_dump()
    console.print(yaml.dump(cfg_dict, default_flow_style=False).strip())


@config_app.command()
def init():
    """Create default config file."""
    save_default_config()
    console.print("[green]Created .blackbox/config.yaml[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app()
