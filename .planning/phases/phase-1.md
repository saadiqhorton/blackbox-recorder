Phase 1: Project Skeleton, Models, Config & Storage

Phase Goal

Set up the Python project foundation: package structure, build system, Pydantic models, YAML config, storage layout, and schema versioning. After this phase, the project is installable and the data model is fully defined — ready for adapters and pipeline.

Exit Criteria

- [ ] `pip install -e .` works, `blackbox --help` shows CLI with 4 commands (analyze, list, report, config)
- [ ] All Pydantic models compile and validate (event, claim, score, error_loop types)
- [ ] Config loads from `.blackbox/config.yaml` with env var overrides
- [ ] RunStore creates `.blackbox/runs/<uuid>/` with metadata.json, events.json, and writing is atomic
- [ ] Schema versioning works: write with schema_version "1.0", read validates it

Stack Context

- SPEC.md at `/home/dezignerdrugz/agentic-dev/blackbox-recorder/SPEC.md` — full spec reference (lines 68-230 for models, 214-229 for storage, 348-364 for config)
- SOUL.md — project philosophy
- Python 3.14+, Typer CLI, Pydantic v2, httpx, pyyaml
- Build: hatchling + hatch-vcs
- Package: `blackbox-recorder`, CLI entry: `blackbox`
- Storage: `.blackbox/runs/<run-id>/` with per-artifact JSON files
- Config: YAML at `.blackbox/config.yaml`

Module structure to create:
```
blackbox/
  __init__.py
  cli.py                    Typer app, 4 stub commands
  config.py                 Config loading (YAML), provider setup, env var overrides

  models/
    __init__.py
    event.py                EventModel, all event types (Pydantic)
    claim.py                Claim, Confidence, EvidenceRef
    score.py                LieScore, EvidenceCompleteness, ClaimVeracity
    error_loop.py           ErrorLoop, PatternType

  storage/
    __init__.py
    run_store.py            Read/write run artifacts with atomic writes
    schema.py               Schema version handling ("1.0")
```

GStack Role Check

No GStack roles needed — architecture is already locked by the eng review in the previous session. All decisions are documented in SPEC.md.

If during implementation it turns out the model design has ambiguities, /plan-eng-review may be needed.

Implementation Order

1. `pyproject.toml` + hatchling build config
2. `blackbox/__init__.py` (package marker + version)
3. `blackbox/models/` — all Pydantic models, no external deps beyond pydantic
4. `blackbox/config.py` — YAML loading, env var overrides, defaults
5. `blackbox/storage/schema.py` — schema version handling
6. `blackbox/storage/run_store.py` — atomic file writes, run CRUD
7. `blackbox/cli.py` — Typer app with 4 stub commands (analyze, list, report, config)
8. Verify: `pip install -e .` + `blackbox --help`

What to Commit

```
blackbox/
  __init__.py               # Package marker with __version__
  cli.py                    # Typer app, 4 stub commands
  config.py                 # Config dataclass, load/save from .blackbox/config.yaml

  models/
    __init__.py
    event.py                # EventType, CommandEvent, FileEditEvent, MessageEvent, ToolUseEvent, ErrorEvent, EventModel
    claim.py                # ClaimCategory, ConfidenceLevel, EvidenceRef, Claim
    score.py                # EvidenceCompleteness, ClaimVeracity, LieScore, RiskLabel
    error_loop.py           # PatternType, ErrorLoop, ErrorLoopReport

  storage/
    __init__.py
    run_store.py            # RunStore: save_run, load_run, list_runs, delete_run (atomic writes)
    schema.py               # SchemaVersion, validate_schema, current_schema="1.0"

pyproject.toml              # hatchling build, typer + pydantic + httpx + pyyaml deps
.blackbox/config.yaml       # Default config (LLM placeholder, storage paths, thresholds)
```
