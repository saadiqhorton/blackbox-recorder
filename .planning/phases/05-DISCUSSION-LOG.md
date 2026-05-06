# Phase 5: Report Generator, Run Store & CLI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 5-report-generator-run-store-cli
**Areas discussed:** Report output format, Run Store save API design, CLI analyze pipeline flow, Config command UX

---

## Report Output Format

| Option | Description | Selected |
|--------|-------------|----------|
| Match SPEC.md exactly | Follow SPEC.md sample: risk banner, scores, icon-based claims, error loops | ✓ |
| Structured tables variant | Tables for claims, collapsible error loops, cleaner risk summary | |
| Minimal/compact | Single-section, compact enough for commit messages | |

**User's choice:** Match SPEC.md exactly
**Notes:** Icon-based markdown (✅⚠️❌), risk banner, evidence completeness + claim veracity numbers, individual claim list.

---

## Run Store Save API Design

| Option | Description | Selected |
|--------|-------------|----------|
| Individual per-type methods | save_claims, save_evidence, save_score, save_error_loops, save_report | ✓ |
| Single bulk save_artifacts() | One method writes all artifacts | |
| Bulk save + individual load | Bulk save, individual load methods for regeneration | |

**User's choice:** Individual per-type methods
**Notes:** Plus individual load methods for report regeneration. Each artifact to `.blackbox/runs/<run-id>/<artifact>.json`.

---

## CLI Analyze Pipeline Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Sync full pipeline with progress | Full pipeline, Rich progress, partial on failure | ✓ |
| Multi-step (separate commands) | Split into sub-steps | |

**User's choice:** Sync full pipeline with progress
**Notes:** Progress to stderr via Rich. On LLM failure: partial report with warning. `--json` flag for machine output.

---

## Config Command UX

| Option | Description | Selected |
|--------|-------------|----------|
| Dot notation (llm.provider) | `blackbox config set llm.provider openai` | ✓ |
| Underscore flat (llm_provider) | As shown in SPEC.md | |
| Both (underscore in, dot out) | Accept both | |

**User's choice:** Dot notation (llm.provider)
**Notes:** Also: `config get`, `config show` (table), `config init` (write default YAML).

---

## Claude's Discretion

- Markdown output emoji/icons (✅⚠️❌ per SPEC.md)
- Rich vs plain text progress indicators (Rich recommended)
- `blackbox list` table columns and formatting
- JSON report schema shape
- Report generator interface (accepts Pydantic models)
- Exit code behavior for partial success

## Deferred Ideas

None — discussion stayed within phase scope.
