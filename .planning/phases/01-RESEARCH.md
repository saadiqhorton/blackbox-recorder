# Phase 1 Research: Project Skeleton, Models, Config & Storage

## Research Complete

### 1. Python 3.14+ Hatchling Setup

- `hatchling` 1.29.0, `hatch-vcs` 0.5.0 — latest stable
- `pyproject.toml` uses `dynamic = ["version"]` with `[tool.hatch.version] source = "vcs"`
- Entry points via `[project.scripts]` — `blackbox = "blackbox_recorder.cli:main"`
- Source layout: `sources = ["src"]` under `[tool.hatch.build.targets.wheel]`
- Python 3.14 PEP 649 (deferred annotations) benefits Pydantic — no `from __future__ import annotations` needed
- `uuid.uuid7()` available for time-ordered UUIDs (RFC 9562) but we're using `uuid.uuid4()` per decisions

### 2. Pydantic v2 Patterns

- **Discriminated unions**: Each event type has `event_type: Literal["command", "file_edit", ...]` — Pydantic auto-detects discriminator with `Union[...]`
- **Serialization**: `model_dump(mode="json")` → JSON-compatible dict, `model_validate(data)` → from dict, `model_dump_json()` → JSON string
- **Cross-file structure**: One file per domain model, re-export via `__init__.py`
- **Literal + Union** is preferred over explicit `Field(discriminator=...)` — Pydantic 2.12+ auto-detects

### 3. Typer CLI Patterns

- `app = typer.Typer(name="blackbox", no_args_is_help=True)`
- Subcommands via `@app.command()` decorator
- Arguments: `typer.Argument(...)`, Options: `typer.Option(...)`
- Rich integration: `console = Console()`, use `rich.table.Table`, `rich.panel.Panel`, `rich.markdown.Markdown`
- Entry point: `def main(): app()` → wired in pyproject.toml

### 4. Atomic File Writes

- **Pattern**: Write `.tmp` file in same directory → `os.fsync()` → `os.replace()` (atomic rename)
- **Crash safety**: `os.fsync(f.fileno())` ensures data reaches disk before rename
- **Same filesystem**: Write temp file in same directory as target (cross-filesystem rename is NOT atomic)
- **Run directory**: `base_dir / "runs" / str(uuid4())`, created with `exist_ok=False`
- **JSONL vs JSON**: JSONL for events (append-efficient), JSON for metadata/scores/claims
- **Concurrent writers**: Include PID in temp filename to avoid collisions

### 5. Python YAML Config Loading

- **Always use `yaml.safe_load()`** — prevents code execution from YAML
- **Config path**: `~/.blackbox/config.yaml` default, overridable via `BLACKBOX_CONFIG` env var
- **Env var overrides**: `BLACKBOX_{SECTION}_{KEY}` convention, highest priority
- **Pydantic validation**: Use `BaseModel` for type-validated config after merge
- **Default config**: Fully functional with Ollama defaults (`gemma4:31b-cloud`)

## Key Planning Inputs

Files to create (in order):
1. `pyproject.toml` — build config, deps, entry point
2. `src/blackbox_recorder/__init__.py` — package init, version
3. `src/blackbox_recorder/models/__init__.py` — re-exports
4. `src/blackbox_recorder/models/event.py` — EventModel + discriminated union
5. `src/blackbox_recorder/models/claim.py` — Claim, Confidence, EvidenceRef
6. `src/blackbox_recorder/models/score.py` — LieScore, EvidenceCompleteness, ClaimVeracity
7. `src/blackbox_recorder/models/error_loop.py` — ErrorLoop, PatternType
8. `src/blackbox_recorder/config.py` — YAML load, env overrides, Config model
9. `src/blackbox_recorder/storage.py` — RunStore, atomic writes, schema
10. `src/blackbox_recorder/cli.py` — Typer app, 4 stub commands
11. `.blackbox/config.yaml` — default config file
