# Phase 5: Report Generator, Run Store & CLI - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up the complete verification pipeline into working CLI commands. Build the report generator (markdown + JSON), enhance the run store to persist all pipeline artifacts, and connect everything through the CLI. After this phase, users can run `blackbox analyze session.jsonl` and get a verification report with scores, error loops, and risk assessment.

**What this phase delivers:**
- `blackbox/pipeline/report_generator.py` — Markdown + JSON report rendering
- RunStore enhancements — per-type save/load methods for pipeline artifacts
- CLI wired up: analyze (full pipeline), list, report (regenerate), config (get/set/show/init)
- Tests: 4 report_generator + 5 run_store + 5 CLI = 14 tests total
</domain>

<decisions>
## Implementation Decisions

### Report Output Format
- **D-01:** Match SPEC.md lines 321-347 exactly. Icon-based markdown (✅⚠️❌) with risk banner, evidence completeness + claim veracity numbers, individual claim list with confidence %, and error loop section.
- **D-02:** JSON report schema follows the same structure as markdown — top-level keys for scores, claims (with evidence), error loops, risk label. Designed for CI consumption.

### Run Store Save API
- **D-03:** Individual per-type save methods: `save_claims()`, `save_evidence()`, `save_score()`, `save_error_loops()`, `save_report()`.
- **D-04:** Individual per-type load methods: `load_claims()`, `load_evidence()`, `load_score()`, `load_error_loops()`, `load_report()` — needed for `blackbox report` regeneration.
- **D-05:** Each save method writes its artifact to `.blackbox/runs/<run-id>/<artifact>.json`. Report generator writes to `.blackbox/runs/<run-id>/reports/incident_report.md` and `incident_report.json`.

### CLI Analyze Pipeline Flow
- **D-06:** `blackbox analyze <path>` runs the full pipeline synchronously.
- **D-07:** Progress printed to stderr: Ingesting... → Extracting claims... → Collecting evidence... → Cross-referencing... → Detecting error loops... → Generating report... → Saving...
- **D-08:** On LLM failure: produce partial report with remaining artifacts, emit warning. Exit code 0 on success (even partial), non-zero only on total failure (file not found, corrupt JSONL).
- **D-09:** `--json` flag outputs machine-readable JSON to stdout instead of markdown.

### Config Command UX
- **D-10:** Dot notation: `blackbox config set llm.provider openai`. Nested keys follow YAML hierarchy.
- **D-11:** Commands: `blackbox config get <key>`, `blackbox config set <key> <value>`, `blackbox config show` (table), `blackbox config init` (write default YAML if no config exists).
- **D-12:** Config reads/writes via existing `blackbox/config.py` module. Writes go to `.blackbox/config.yaml`.

### Claude's Discretion
- Emoji/icons in markdown output (✅⚠️❌ per SPEC.md)
- Rich vs plain text progress indicators (Rich recommended — already imported in CLI skeleton)
- `blackbox list` table columns and formatting
- JSON report schema shape (within the structure anchored by SPEC.md)
- How report generator receives data — accepts typed Pydantic models (LieScore, list[Claim], list[ErrorLoop]) directly
- Exit code behavior for edge cases (partial success, no claims, empty session)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & Requirements
- `SPEC.md` — Locked requirements. Key sections: lines 49-50 (report generation), lines 94-101 (module structure), lines 304-347 (CLI design + output format), lines 348-378 (config + error handling), lines 399-409 (test coverage targets)

### Existing Pipeline
- `blackbox/pipeline/cross_referencer.py` — CrossReferencer produces LieScore + populates Claim.evidence
- `blackbox/pipeline/error_loop_detector.py` — ErrorLoopDetector produces list[ErrorLoop]
- `blackbox/pipeline/claim_extractor.py` — ClaimExtractor produces list[Claim]
- `blackbox/pipeline/evidence_collector.py` — EvidenceCollector produces EvidenceSet

### Existing Models
- `blackbox/models/score.py` — LieScore, EvidenceCompleteness, ClaimVeracity, RiskLabel, compute_risk_label
- `blackbox/models/claim.py` — Claim, EvidenceRef, ClaimCategory, ConfidenceLevel
- `blackbox/models/error_loop.py` — ErrorLoop, PatternType
- `blackbox/models/evidence.py` — EvidenceSet, EvidenceItem
- `blackbox/models/event.py` — EventModel, ToolUseEvent, MessageEvent, ErrorEvent

### Storage & Config
- `blackbox/storage/run_store.py` — RunStore (create_run, load_metadata, append_event, list_runs, run_exists) — needs save/load methods for pipeline artifacts
- `blackbox/config.py` — Config loading with llm provider, api_key, model, base_url fields; save_default_config
- `blackbox/cli.py` — Current CLI skeleton with stub commands

### Phase Definitions
- `.planning/phases/phase-5.md` — Phase exit criteria (pending)
- `.planning/STATE.json` — Project phase state tracking

### Standards
- `SOUL.md` — Project craft standards

### Test Fixtures
- `test_fixtures/honest_session.jsonl` — Golden fixture for integration testing
- `test_fixtures/dishonest_session.jsonl` — Golden fixture for integration testing
- `test_fixtures/ambiguous_session.jsonl` — Golden fixture for integration testing
- `test_fixtures/corrupt_session.jsonl` — Golden fixture for integration testing
- `test_fixtures/empty_session.jsonl` — Golden fixture for integration testing
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `blackbox/config.py` — `save_default_config()` already writes default YAML. Config command can reuse directly.
- `blackbox/cli.py` — Rich Console already imported. Use Rich for progress display and table rendering.
- CrossReferencer, ErrorLoopDetector, ClaimExtractor, EvidenceCollector — all built, tested, and ready to wire together.

### Established Patterns
- Plain `def test_*`, `assert`, `unittest.mock` for externals — all tests follow this convention.
- Pydantic `model_dump()` for serialization — save methods should use this for JSON artifact serialization.
- `_atomic_write_json` pattern in RunStore — save methods should use this for safe writes.

### Integration Points
- CLI `analyze` orchestrates: adapter → extractor → collector → cross-referencer → detector → report generator → run store
- RunStore save methods write to `.blackbox/runs/<run-id>/` directory (already created by `create_run()`)
- Report generator consumes: EventModel (for metadata), LieScore, list[Claim], list[ErrorLoop]
- CLI `report` reads from RunStore: load_score(), load_claims(), load_error_loops(), load_report()
</code_context>

<specifics>
## Specific Ideas

### Report Generator Interface
Accepts typed Pydantic models directly and returns strings/dicts:
```python
generate_markdown(session: EventModel, score: LieScore, claims: list[Claim], loops: list[ErrorLoop]) -> str
generate_json(session: EventModel, score: LieScore, claims: list[Claim], loops: list[ErrorLoop]) -> dict
```

### RunStore Save/Load Interface
```python
save_claims(run_id: str, claims: list[Claim]) -> Path
save_evidence(run_id: str, evidence: EvidenceSet) -> Path
save_score(run_id: str, score: LieScore) -> Path
save_error_loops(run_id: str, loops: list[ErrorLoop]) -> Path
save_report(run_id: str, markdown: str, json_data: dict) -> tuple[Path, Path]
load_claims(run_id: str) -> list[Claim]
load_score(run_id: str) -> LieScore
load_error_loops(run_id: str) -> list[ErrorLoop]
```

### Test Coverage Targets
- `pipeline/report_generator.py` → 4 tests: markdown rendering, JSON rendering, empty claims/scores, markdown with error loops
- `storage/run_store.py` → 5 tests: save/load claims, save/load score, save/load error loops, save/load report, list_runs with artifacts
- `cli.py` → 5 tests: analyze (with mocked pipeline), analyze --json, list, report, config set/get

### CLI Progress Output Style
Use Rich Console with status spinners for each pipeline step. Example:
```
Ingesting session...                     ✓ (42 events)
Extracting claims (via Ollama)...        ✓ (3 claims)
Collecting evidence...                   ✓ (15 evidence items)
Cross-referencing...                     ✓
Detecting error loops...                 ✓ (1 loop)
Generating report...                     ✓
Saving to .blackbox/runs/abc123/...      ✓

BLACK BOX RECORDER — VERIFICATION REPORT
══════════════════════════════════════════
...
```
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

Items deferred from MVP (SPEC.md lines 57-65) remain deferred: live capture, Telescope/AgentReplay adapters, CI gate, web dashboard, richer evidence types.
</deferred>

---

*Phase: 5-report-generator-run-store-cli*
*Context gathered: 2026-05-05 via gsd-discuss-phase*
