# Phase 1 Context: Project Skeleton, Models, Config & Storage

## Domain
Python package foundation: project skeleton, Pydantic event models, YAML config, file-based storage with schema versioning. This is the base layer everything else builds on.

## Spec Lock
Requirements are locked by SPEC.md (`.spec.md`). Agents MUST read SPEC.md before planning — it defines the full event model schema, storage layout, config schema, and CLI commands. This context captures only implementation decisions from discussion.

## Decisions

### Model Layout
- **Decision:** Separate files per model class (`event.py`, `claim.py`, `score.py`, `error_loop.py`)
- **Rationale:** Cleaner imports, isolated testing, matches SPEC.md module structure exactly
- **Consequence:** Package structure follows SPEC.md line 90-95

### Config Defaults
- **Decision:** Default provider is `ollama`, default model is `gemma4:31b-cloud`, default base URL `http://localhost:11434/v1`
- **Rationale:** Zero setup for local dev; user chose Gemma 4 31B cloud as the test model
- **Consequence:** First `blackbox analyze` works without API key if Ollama is running

### Run ID Format
- **Decision:** UUID4 strings for run directory identifiers
- **Rationale:** Globally unique, no collisions, language-agnostic, matches SPEC.md examples
- **Consequence:** `.blackbox/runs/<uuid4>/` directory structure

### Threshold Defaults
- **Decision:** SPEC.md defaults — min_completeness: 50, min_veracity: 50
  - HIGH risk: completeness < 50% or veracity < 50%
  - MEDIUM risk: both >= 50%
  - LOW risk: both >= 80%
- **Rationale:** Reasonable starting point, users can tune via config

### Python Version
- **Decision:** Python 3.14+ (as specified in SPEC.md)
- **Rationale:** Leverage latest Python features, match spec commitment

### Atomic Write Strategy
- **Decision:** Write to `.tmp` file, then `os.rename()` for atomic replacement
- **Rationale:** Standard approach, works on Linux/WSL2 (primary target), prevents partial reads

## Boundaries
- No adapter code (Phase 2)
- No pipeline code (Phases 3-4)
- No report generation (Phase 5)
- No test fixtures yet (Phase 2)
- No PyPI publishing (Phase 6)

## Canonical Refs
- `SPEC.md` — Locked requirements, MUST read before planning
- `SOUL.md` — Project philosophy, code quality standards
- `.planning/phases/phase-1.md` — Phase plan with implementation order and file manifest

## Codebase Context
- Empty project (only SOUL.md and SPEC.md exist)
- No existing Python code or reusable assets
- Fresh hatchling build from scratch
