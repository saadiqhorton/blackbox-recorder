---
phase: 1
name: "Project Skeleton, Models, Config & Storage"
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - blackbox/__init__.py
  - blackbox/models/__init__.py
  - blackbox/models/event.py
  - blackbox/models/claim.py
  - blackbox/models/score.py
  - blackbox/models/error_loop.py
  - blackbox/config.py
  - blackbox/storage/__init__.py
  - blackbox/storage/run_store.py
  - blackbox/storage/schema.py
  - blackbox/cli.py
  - .blackbox/config.yaml
autonomous: true
must_haves:
  - "pip install -e . installs without errors"
  - "blackbox --help shows 4 commands: analyze, list, report, config"
  - "All Pydantic models validate (event, claim, score, error_loop)"
  - "Config loads from .blackbox/config.yaml with env var overrides"
  - "RunStore creates .blackbox/runs/<uuid>/ with atomic writes"
---

# Phase 1 — Project Skeleton, Models, Config & Storage

## Goal

Set up the Python project foundation: package structure, build system, Pydantic models, YAML config, storage layout, and schema versioning. After this phase, the project is installable and the data model is fully defined — ready for adapters and pipeline.

---

## Task 1.1 — pyproject.toml + build config

<task_type>execute</task_type>

<read_first>
- SPEC.md (lines 68-85 for dependencies, 425-429 for packaging)
- SOUL.md (project philosophy — code quality standards)
</read_first>

<action>
Create `pyproject.toml` at project root with:

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
name = "blackbox-recorder"
description = "Forensic pre-commit verification tool for AI coding agent sessions"
requires-python = ">=3.14"
readme = "README.md"
license = "MIT"
dynamic = ["version"]

authors = [
  { name = "Agent Black Box Recorder", email = "dev@blackbox-recorder.dev" },
]

classifiers = [
  "Development Status :: 2 - Pre-Alpha",
  "Programming Language :: Python :: 3.14",
  "License :: OSI Approved :: MIT License",
]

dependencies = [
  "pydantic>=2.10",
  "typer>=0.15",
  "rich>=15.0",
  "httpx>=0.28",
  "pyyaml>=6.0",
]

[project.scripts]
blackbox = "blackbox.cli:main"

[tool.hatch.version]
source = "vcs"

[tool.hatch.build.targets.wheel]
packages = ["blackbox/"]
```

Also create `README.md` with a one-line description: "Know what your AI agent actually did — not what it said it did."
</action>

<acceptance_criteria>
- `pyproject.toml` exists with all fields above
- `README.md` exists
- Python 3.14+ required pin
- Dependencies include pydantic, typer, rich, httpx, pyyaml
- Entry point is `blackbox = "blackbox.cli:main"`
</acceptance_criteria>

---

## Task 1.2 — Package init + version

<task_type>execute</task_type>

<read_first>
- SPEC.md (module structure at lines 84-96)
- Research note: hatch-vcs derives version from git tags
</read_first>

<action>
Create `blackbox/__init__.py`:

```python
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("blackbox-recorder")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
```

Create directory: `blackbox/models/`, `blackbox/storage/`.
Create empty `blackbox/models/__init__.py` and `blackbox/storage/__init__.py` (will be populated by subsequent tasks).
</action>

<acceptance_criteria>
- `blackbox/__init__.py` exists with `__version__` using `importlib.metadata`
- `blackbox/models/__init__.py` exists (empty)
- `blackbox/storage/__init__.py` exists (empty)
- `python -c "from blackbox import __version__; print(__version__)"` works
</acceptance_criteria>

---

## Task 1.3 — Event models (Pydantic)

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 158-210 (full event model schema)
- SPEC.md lines 96-101 (model module structure)
- Research: Pydantic v2 discriminated unions with `Literal` + `Union`
</read_first>

<action>
Create `blackbox/models/event.py` with these Pydantic models following SPEC.md exactly:

**EventType** (StrEnum):
- COMMAND = "command", FILE_EDIT = "file_edit", MESSAGE = "message", TOOL_USE = "tool_use", ERROR = "error"

**CommandEvent** (BaseModel):
- `type`: Literal["command"] (acts as discriminator)
- `timestamp`: datetime
- `command`: str
- `args`: list[str]
- `exit_code`: int | None
- `stdout_snippet`: str | None
- `stderr_snippet`: str | None
- `working_directory`: str | None

**FileEditEvent** (BaseModel):
- `type`: Literal["file_edit"]
- `timestamp`: datetime
- `path`: str
- `action`: Literal["create", "edit", "delete"]
- `diff`: str | None

**MessageEvent** (BaseModel):
- `type`: Literal["message"]
- `timestamp`: datetime
- `role`: Literal["user", "assistant"]
- `content`: str

**ToolUseEvent** (BaseModel):
- `type`: Literal["tool_use"]
- `timestamp`: datetime
- `tool_name`: str
- `input`: dict
- `output`: str | None
- `duration_ms`: int | None

**ErrorEvent** (BaseModel):
- `type`: Literal["error"]
- `timestamp`: datetime
- `error_type`: str
- `message`: str
- `context`: str | None

**EventModel** (BaseModel):
- `session_id`: str
- `agent_type`: str = "claude-code"
- `task`: str | None
- `events`: list[CommandEvent | FileEditEvent | MessageEvent | ToolUseEvent | ErrorEvent]
- `schema_version`: str = "1.0"

Use `from typing import Literal, Union` for the discriminated union pattern. Pydantic auto-detects the discriminator from the Literal `type` field. Use `from datetime import datetime`.

Also export `EventUnion = Union[CommandEvent, FileEditEvent, MessageEvent, ToolUseEvent, ErrorEvent]` for downstream use.

Update `blackbox/models/__init__.py` to re-export all event models.
</action>

<acceptance_criteria>
- `from blackbox.models.event import EventModel, CommandEvent, FileEditEvent` works
- `CommandEvent(type="command", timestamp=..., command="ls", args=["-la"])` instantiates without error
- `EventModel` accepts all 5 event types in `events` list
- `model.model_dump(mode="json")` produces JSON-compatible dict (datetime→str)
- `EventType.COMMAND == "command"` is True
</acceptance_criteria>

---

## Task 1.4 — Claim models

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 231-259 (claim extraction schema and categories)
</read_first>

<action>
Create `blackbox/models/claim.py` with:

**ClaimCategory** (StrEnum):
- TEST_RESULT = "test_result", OUTCOME = "outcome", SCOPE = "scope", APPROACH = "approach", STATE = "state"

**ConfidenceLevel** (StrEnum):
- EXACT = "exact", SEMANTIC = "semantic", MISSING = "missing"

**EvidenceRef** (BaseModel):
- `source`: str  (e.g., "command:3", "file_diff:src/auth.ts")
- `type`: Literal["exit_code", "git_diff", "file_content", "error_log", "test_output"]
- `value`: str
- `confidence`: ConfidenceLevel

**Claim** (BaseModel):
- `text`: str
- `category`: ClaimCategory
- `source_message_idx`: int
- `verifiable`: bool = True
- `evidence`: list[EvidenceRef] = []

Update `blackbox/models/__init__.py` to re-export claim models.
</action>

<acceptance_criteria>
- `from blackbox.models.claim import Claim, ClaimCategory, ConfidenceLevel, EvidenceRef` works
- `Claim(text="all tests pass", category=ClaimCategory.TEST_RESULT, source_message_idx=42)` instantiates
- `ClaimCategory.TEST_RESULT == "test_result"` is True
</acceptance_criteria>

---

## Task 1.5 — Score models

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 268-283 (scoring model, formulas, risk labels)
</read_first>

<action>
Create `blackbox/models/score.py` with:

**EvidenceCompleteness** (BaseModel):
- `evidenced_claims`: int
- `total_claims`: int
- `percentage`: float  (computed: evidenced/total, 0 if total=0)

**ClaimVeracity** (BaseModel):
- `matching_claims`: int
- `evidenced_claims`: int
- `percentage`: float  (computed: matching/evidenced, 0 if evidenced=0)

**RiskLabel** (StrEnum):
- LOW = "low", MEDIUM = "medium", HIGH = "high"

**LieScore** (BaseModel):
- `evidence_completeness`: EvidenceCompleteness
- `claim_veracity`: ClaimVeracity
- `risk_label`: RiskLabel

Risk label logic:
- HIGH: completeness < 50 or veracity < 50
- MEDIUM: completeness >= 50 and veracity >= 50
- LOW: completeness >= 80 and veracity >= 80

Add a `compute_risk_label(completeness: float, veracity: float) -> RiskLabel` standalone function implementing the above logic.

Update `blackbox/models/__init__.py` to re-export score models.
</action>

<acceptance_criteria>
- `from blackbox.models.score import LieScore, EvidenceCompleteness, ClaimVeracity, RiskLabel` works
- `compute_risk_label(90, 90) == RiskLabel.LOW`
- `compute_risk_label(60, 60) == RiskLabel.MEDIUM`
- `compute_risk_label(40, 90) == RiskLabel.HIGH`
- `compute_risk_label(90, 40) == RiskLabel.HIGH`
</acceptance_criteria>

---

## Task 1.6 — Error loop models

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 290-301 (error loop detection patterns)
</read_first>

<action>
Create `blackbox/models/error_loop.py` with:

**PatternType** (StrEnum):
- REPEATED_COMMAND = "repeated_command"
- CIRCULAR_EDIT = "circular_edit"
- ERROR_SPIKE = "error_spike"

**ErrorLoop** (BaseModel):
- `pattern`: PatternType
- `description`: str
- `count`: int
- `time_range`: tuple[datetime, datetime] | None
- `details`: str  (command name, file path, error type — depending on pattern)

Update `blackbox/models/__init__.py` to re-export error loop models.
</action>

<acceptance_criteria>
- `from blackbox.models.error_loop import ErrorLoop, PatternType` works
- `PatternType.REPEATED_COMMAND == "repeated_command"` is True
- `ErrorLoop(pattern=PatternType.REPEATED_COMMAND, description="npm test failed 5x", count=5, details="Cannot find 'auth'")` instantiates
</acceptance_criteria>

---

## Task 1.7 — Config loader

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 348-364 (config schema)
- Research: pyyaml safe_load, env var overrides, Pydantic validation
- CONTEXT.md: default provider=ollama, model=gemma4:31b-cloud, base_url=http://localhost:11434/v1
</read_first>

<action>
Create `blackbox/config.py` with:

**BlackboxConfig** (BaseModel with all defaults matching CONTEXT.md decisions):
- `llm`: nested model with provider="ollama", model="gemma4:31b-cloud", base_url="http://localhost:11434/v1", api_key=None
- `storage`: nested model with runs_dir=".blackbox/runs"
- `thresholds`: nested model with min_completeness=50, min_veracity=50

**Functions:**

`get_config_path() -> Path`:
- Check `BLACKBOX_CONFIG` env var, fall back to `.blackbox/config.yaml` in CWD

`load_config() -> BlackboxConfig`:
1. Start with BlackboxConfig defaults
2. If YAML file exists at config_path, load with `yaml.safe_load`, deep-merge into defaults
3. Apply env var overrides: `BLACKBOX_LLM_PROVIDER`, `BLACKBOX_LLM_MODEL`, `BLACKBOX_LLM_BASE_URL`, `BLACKBOX_LLM_API_KEY`, `BLACKBOX_STORAGE_RUNS_DIR`, `BLACKBOX_MIN_COMPLETENESS`, `BLACKBOX_MIN_VERACITY`
4. Validate final merged dict through BlackboxConfig.model_validate()
5. Return validated config

`save_default_config(path: Path | None = None)`:
- Write default config YAML to the given path or config_path
- Include helpful comments in the YAML

`_deep_merge(base: dict, override: dict) -> dict`:
- Recursive dict merge helper

`_apply_env_overrides(config: dict) -> dict`:
- Map env var names to nested config keys
- Coerce int types for threshold values
</action>

<acceptance_criteria>
- `from blackbox.config import load_config, BlackboxConfig` works
- `load_config()` returns BlackboxConfig with defaults when no file exists
- Setting `BLACKBOX_LLM_MODEL=test` env var overrides the config value
- Setting `BLACKBOX_MIN_COMPLETENESS=70` coerces to int
- Default config has provider="ollama", model="gemma4:31b-cloud"
</acceptance_criteria>

---

## Task 1.8 — Schema versioning

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 214-229 (storage layout, schema version)
</read_first>

<action>
Create `blackbox/storage/schema.py`:

**SchemaVersion** (BaseModel):
- `version`: str = "1.0"
- `description`: str = "Initial schema"

**Constants:**
- `CURRENT_SCHEMA = "1.0"`
- `SUPPORTED_VERSIONS = ["1.0"]`

**Functions:**

`validate_schema(data: dict) -> bool`:
- Check `data.get("schema_version")` is in SUPPORTED_VERSIONS
- Return True if valid, False otherwise

`assert_schema(data: dict) -> None`:
- Like validate_schema but raises ValueError with message like "Unsupported schema version: {version}. Supported: {SUPPORTED_VERSIONS}"

Update `blackbox/storage/__init__.py` to re-export schema items.
</action>

<acceptance_criteria>
- `from blackbox.storage.schema import CURRENT_SCHEMA, validate_schema` works
- `validate_schema({"schema_version": "1.0"})` returns True
- `validate_schema({"schema_version": "0.5"})` returns False
- `assert_schema({"schema_version": "0.5"})` raises ValueError
</acceptance_criteria>

---

## Task 1.9 — Run store (atomic file storage)

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 214-229 (storage layout)
- Research: atomic write pattern — .tmp + os.fsync + os.replace
- Research: JSONL for events, JSON for metadata
</read_first>

<action>
Create `blackbox/storage/run_store.py` with:

**RunMetadata** (BaseModel):
- `run_id`: str
- `created_at`: datetime
- `agent_type`: str = "claude-code"
- `task`: str | None
- `event_count`: int = 0
- `status`: Literal["recorded", "analyzed", "reported"] = "recorded"

**RunStore class:**

Constructor takes `base_dir: Path` (default: Path(".blackbox") / "runs").

`_run_path(run_id: str) -> Path`:
- Returns `{base_dir}/{run_id}/`

`_atomic_write_json(filepath: Path, data: dict) -> None`:
1. Create parent directory with `parents=True, exist_ok=True`
2. Write to `filepath.with_suffix(".tmp")` with json.dump(indent=2)
3. `f.flush()` + `os.fsync(f.fileno())` for crash safety
4. `os.replace(tmp_path, filepath)` for atomic rename
5. On exception: clean up temp file, re-raise
Use PID in temp filename for concurrent-writer safety: `{stem}_{os.getpid()}.tmp`

`_read_json(filepath: Path) -> dict`:
- Standard json.load, raise FileNotFoundError if missing

`create_run(metadata: RunMetadata) -> Path`:
1. Create run directory with `exist_ok=False`
2. Write metadata.json via _atomic_write_json
3. Initialize events.jsonl (empty file)
4. Return run directory Path

`load_metadata(run_id: str) -> dict`:
- Read and return metadata.json

`append_event(run_id: str, event: dict) -> None`:
- Append one JSON line to events.jsonl (simple append, not atomic per-line)
- Update metadata.json event_count

`list_runs() -> list[dict]`:
- Scan base_dir for UUID-named subdirectories
- Load metadata.json from each
- Return sorted by created_at descending

`run_exists(run_id: str) -> bool`:
- Check if run directory exists

Handle errors:
- `create_run`: if directory already exists, raise FileExistsError with clear message
- `load_metadata`: if run not found, raise FileNotFoundError with "No run at {path}"

Update `blackbox/storage/__init__.py` to re-export RunStore and RunMetadata.
</action>

<acceptance_criteria>
- `from blackbox.storage.run_store import RunStore, RunMetadata` works
- `RunStore().create_run(RunMetadata(run_id="test-1", created_at=datetime.now()))` creates directory with metadata.json
- `append_event("test-1", {"type": "command", "command": "ls"})` appends line to events.jsonl
- `list_runs()` returns non-empty list after creating a run
- `RunStore(base_dir=Path("/tmp/test-blackbox")).create_run(...)` works with custom base_dir
</acceptance_criteria>

---

## Task 1.10 — CLI with 4 stub commands

<task_type>execute</task_type>

<read_first>
- SPEC.md lines 305-318 (CLI commands and output format)
- Research: Typer patterns, Rich integration
</read_first>

<action>
Create `blackbox/cli.py` with:

```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="blackbox",
    help="Agent Black Box Recorder — forensic pre-commit verification",
    no_args_is_help=True,
)
console = Console()


@app.command()
def analyze(
    path: str = typer.Argument(..., help="Path to session JSONL file"),
    json: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
):
    """Analyze a session file for claims, evidence, and verification scores."""
    console.print(f"[yellow]Analyze[/yellow] command — not yet implemented")
    console.print(f"  Path: {path}")
    console.print(f"  JSON: {json}")


@app.command()
def list(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of runs to show"),
):
    """List previously analyzed runs."""
    table = Table(title="Black Box Runs")
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="green")
    table.add_column("Agent", style="blue")
    table.add_column("Events", style="yellow")
    console.print(table)


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run ID to regenerate report for"),
):
    """Regenerate a verification report for a previously analyzed run."""
    console.print(f"[yellow]Report[/yellow] command — not yet implemented")
    console.print(f"  Run ID: {run_id}")


@app.command()
def config(
    key: str = typer.Argument(None, help="Config key to get/set (e.g. llm.provider)"),
    value: str = typer.Argument(None, help="Value to set"),
):
    """Manage configuration (LLM provider, keys, model)."""
    if key and value:
        console.print(f"[green]Set[/green] {key} = {value}")
    elif key:
        console.print(f"[yellow]Get[/yellow] {key} — not yet implemented")
    else:
        console.print("[yellow]Config[/yellow] command — not yet implemented")


def main():
    app()
```

4 stub commands: `analyze`, `list`, `report`, `config`. Each prints a placeholder message showing it was called. The `list` command renders an empty Rich Table. The `config` command accepts optional key/value args for eventual get/set.
</action>

<acceptance_criteria>
- `from blackbox.cli import app` works
- `app` is a typer.Typer instance
- 4 @app.command() decorated functions: analyze, list, report, config
- `main()` function calls `app()`
- `blackbox --help` (via pip install -e) shows all 4 commands
</acceptance_criteria>

---

## Task 1.11 — Default config file

<task_type>execute</task_type>

<read_first>
- CONTEXT.md: config defaults decisions
- SPEC.md lines 348-364
</read_first>

<action>
Create `.blackbox/config.yaml`:

```yaml
# Agent Black Box Recorder Configuration

llm:
  provider: ollama          # openai | anthropic | ollama | custom
  model: gemma4:31b-cloud   # provider-specific model name
  base_url: http://localhost:11434/v1  # custom endpoint (Ollama default)
  api_key: null             # set via BLACKBOX_LLM_API_KEY env var

storage:
  runs_dir: .blackbox/runs

thresholds:
  min_completeness: 50      # below this → HIGH risk
  min_veracity: 50          # below this → HIGH risk
```

Also add `.blackbox/` to a `.gitignore` at project root (runs directory contains session data).
</action>

<acceptance_criteria>
- `.blackbox/config.yaml` exists with provider=ollama, model=gemma4:31b-cloud
- `.gitignore` contains `.blackbox/runs/` entry
</acceptance_criteria>

---

## Verification

After all tasks complete:

1. `pip install -e .` — clean install
2. `blackbox --help` — shows all 4 commands
3. `python -c "from blackbox import __version__; print(__version__)"` — prints version
4. `python -c "from blackbox.models.event import EventModel, CommandEvent, FileEditEvent, MessageEvent, ToolUseEvent, ErrorEvent; print('event models ok')"`
5. `python -c "from blackbox.models.claim import Claim, ClaimCategory; print('claim models ok')"`
6. `python -c "from blackbox.models.score import compute_risk_label; print(compute_risk_label(90, 90))"` — prints "low"
7. `python -c "from blackbox.models.error_loop import ErrorLoop, PatternType; print('error loop models ok')"`
8. `python -c "from blackbox.config import load_config; c = load_config(); print(c.llm.model)"` — prints "gemma4:31b-cloud"
9. `python -c "from blackbox.storage.run_store import RunStore, RunMetadata; from datetime import datetime; rs = RunStore(); rs.create_run(RunMetadata(run_id='verify-1', created_at=datetime.now())); print(len(rs.list_runs()))"` — creates run dir
10. `blackbox analyze test.jsonl` — prints placeholder message
11. `blackbox list` — prints table header
</acceptance_criteria>
