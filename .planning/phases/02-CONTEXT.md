# Phase 2 Context: Claude Code JSONL Adapter + Test Fixtures

## Domain
Build the Claude Code JSONL ingest adapter and hand-crafted test fixtures. This is the data ingestion layer — transforms raw Claude Code session exports into normalized EventModel instances that downstream pipeline phases consume.

## Spec Lock
Requirements are locked by SPEC.md. SPEC.md lines 32-33 ("Claude Code JSONL ingest — read Claude Code session exports"), lines 84-96 (module structure with adapters/), and lines 388-397 (fixtures and test coverage) define the scope.

## Decisions

### IngestAdapter Protocol Pattern
- **Decision:** Use `typing.Protocol` for the adapter interface (structural subtyping, not ABC inheritance)
- **Rationale:** Protocol allows duck-typing — any object with the right signature is an adapter. No forced inheritance hierarchy. Matches Python 3.14's progressive typing philosophy.
- **Consequence:** New adapters (Telescope, AgentReplay) implement the protocol without needing to import adapter base classes.

### Line-by-Line JSONL Parsing
- **Decision:** Parse one line at a time with `for line in file:` (lazy iteration), try/except per line
- **Rationale:** Session files can be 10K+ lines. Loading entire file into memory is wasteful and fragile.
- **Consequence:** Malformed lines are skipped with a warning, valid lines before/after are processed normally.

### Tool Use ↔ Tool Result Correlation
- **Decision:** Pair tool_use + tool_result within the same assistant message by matching `id` → `tool_use_id`. A tool_use without a tool_result still emits a ToolUseEvent with output=None.
- **Rationale:** The `id`/`tool_use_id` pairing is the only reliable correlation mechanism. Not all tool uses have results (truncated sessions).
- **Consequence:** Orphan tool_results (no matching tool_use) emit a ToolUseEvent with tool_name="unknown" and a warning log.

### Exit Code Inference
- **Decision:** Infer non-zero exit code from `tool_result.is_error == true`. Exit code 0 is the default for successful tool results.
- **Rationale:** The JSONL doesn't store raw exit codes — only a boolean error flag. Exact exit codes are not recoverable from the log format.
- **Consequence:** CommandEvent exit_code will be 0 or 1 (boolean), not the original process exit code. This is a known limitation of the log format.

### Session Metadata Extraction
- **Decision:** Extract session_id, agent_type, version from the first few events' common fields. Use the first user message's content for `task` field.
- **Rationale:** All events share sessionId/version fields. The first user message is the task prompt.
- **Consequence:** task field is best-effort (may be empty if no user message).

### Test Fixture Format
- **Decision:** Use simplified JSONL (same structure as real Claude Code exports but with synthetic, deterministic UUIDs and known content)
- **Rationale:** Fixtures must be human-readable, inspectable, and have known ground truth for test assertions.
- **Consequence:** Fixtures are valid JSONL but not byte-for-byte identical to real exports. They test the adapter's behavior with realistic structure.

### Fixture Session IDs
- **Decision:** Deterministic, descriptive session IDs: "honest-001", "dishonest-002", "ambiguous-003", "corrupt-004", "empty-005"
- **Rationale:** Tests can reference fixtures by predictable session IDs. Avoids magic UUIDs.

### Adapter Tests in This Phase vs Phase 6
- **Decision:** Write adapter tests in this phase (not deferred to Phase 6)
- **Rationale:** SPEC.md allocates `adapters/claude_code.py → 4 tests` in the test coverage table. Phase 2 is the adapter phase; tests validate the adapter works. Deferring tests breaks the pattern from Phase 1 where models were tested inline.
- **Consequence:** 4 tests for claude_code.py: valid session, malformed line, empty file, truncated file.

## Boundaries
- No pipeline code (claim extraction, evidence collection — Phase 3)
- No cross-referencing or scoring (Phase 4)
- No report generation (Phase 5)
- No PyPI packaging or CI (Phase 6)
- Adapter only handles Claude Code JSONL (not Telescope, AgentReplay, or live capture)

## Canonical Refs
- `SPEC.md` — Locked requirements, MUST read
- `SOUL.md` — Project craft standards
- `blackbox/models/event.py` — EventModel types consumed by adapter
- `.planning/phases/02-RESEARCH.md` — Technical research on JSONL format
- `.planning/phases/phase-2.md` — Phase definition and exit criteria

## Codebase Context
- Phase 1 complete: models, config, storage, CLI stubs exist
- `blackbox/adapters/` directory needs creation
- `test_fixtures/` directory needs creation
- Existing code uses Pydantic v2, Python 3.14+ patterns
