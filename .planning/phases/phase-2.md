Phase 2: Claude Code JSONL Adapter + Test Fixtures

Phase Goal

Build the Claude Code JSONL ingest adapter and five hand-crafted test fixture sessions. After this phase, the system can parse real Claude Code session exports into the normalized EventModel and has known-ground-truth fixtures for pipeline testing.

Exit Criteria

- [x] IngestAdapter protocol defines the adapter interface (ingest, list_event_types, metadata)
- [x] ClaudeCodeAdapter reads any real Claude Code JSONL file and returns a valid EventModel
- [x] Adapter handles all JSONL event types: permission-mode, attachment, file-history-snapshot, user, assistant, system, last-prompt, queue-operation
- [x] Adapter extracts tool results (tool_use + tool_result pairs) into ToolUseEvent with output/error
- [x] Error events (system-level errors) mapped to ErrorEvent model
- [x] Malformed JSONL lines are skipped with warnings (not fatal)
- [x] Empty files return EventModel with 0 events (no crash)
- [x] Truncated files (partial last line) handled gracefully
- [x] Session metadata extracted: session_id, agent_type, task from JSONL
- [x] 5 test fixture JSONL files created with known ground truth
- [x] Fixtures match SPEC.md spec: honest, dishonest, ambiguous, corrupt, empty
- [x] Each fixture is valid JSONL (verified with `json.loads` per line)

Stack Context

- SPEC.md — lines 126-127 (module structure), lines 32 (Claude Code JSONL ingest), lines 93-94 (adapter module)
- Phase 1 models — EventModel, CommandEvent, FileEditEvent, MessageEvent, ToolUseEvent, ErrorEvent
- Real Claude Code JSONL format analyzed from ~/.claude/sessions/ — events have types: permission-mode, attachment, file-history-snapshot, user, assistant, system, last-prompt, queue-operation
- Tool use in assistant messages: content array with type=tool_use (name, id, input) and type=tool_result (tool_use_id, content, is_error)
- `python -m json.tool` available for JSON validation
- `.blackbox/runs/` is gitignored (from Phase 1)

GStack Role Check

No GStack roles needed — adapter architecture and JSONL format are well-understood from SPEC.md and real session analysis.

What to Commit

```
blackbox/adapters/
  __init__.py               IngestAdapter protocol
  claude_code.py            ClaudeCodeAdapter implementation

test_fixtures/
  honest_session.jsonl      Claims match evidence
  dishonest_session.jsonl   Claims contradict evidence
  ambiguous_session.jsonl   Limited evidence
  corrupt_session.jsonl     Truncated at line 15
  empty_session.jsonl       0 events
```
