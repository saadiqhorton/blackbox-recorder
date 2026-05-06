# Phase 2 Research: Claude Code JSONL Adapter + Test Fixtures

## Research Complete

### 1. Claude Code JSONL Format

Session files are stored at `~/.claude/sessions/<uuid>.jsonl` and `~/.claude/projects/<project-path>/<uuid>.jsonl`. Each line is a standalone JSON object (newline-delimited JSON).

#### Event Types Found in Real Sessions

| Type | Frequency | Fields | Maps To |
|------|-----------|--------|---------|
| `permission-mode` | 2/session | type, permissionMode, sessionId | Skipped (session metadata only) |
| `attachment` | 4-6/session | type, uuid, timestamp, attachment{type, content, ...}, version, sessionId, cwd | Extracted for metadata; attachment types: hook_success, hook_additional_context, mcp_instructions_delta, skill_listing, todo_reminder |
| `file-history-snapshot` | 2/session | type, messageId, snapshot{trackedFileBackups, timestamp}, isSnapshotUpdate | Skipped (internal file tracking) |
| `user` | varies | type, uuid, timestamp, message{role:"user", content}, sessionId, cwd, parentUuid | MessageEvent(role="user") — content is always a string |
| `assistant` | varies | type, uuid, timestamp, message{role:"assistant", content[array]}, sessionId, cwd | MessageEvent + ToolUseEvent |
| `system` | rare | type, level, error{type, message}, retryAttempt, timestamp | ErrorEvent (when level=error) |
| `last-prompt` | 1/session | type, lastPrompt, sessionId | Skipped (internal state) |
| `queue-operation` | 2/session | type, operation, ... | Skipped (internal queue mgmt) |

#### Assistant Message Content Blocks

Assistant messages have a `content` array (not a string). Each block has a `type`:

**text** blocks → MessageEvent(role="assistant", content=text)
**thinking** blocks → Skipped (internal reasoning, not user-facing)
**tool_use** blocks → ToolUseEvent(name, input, id)
**tool_result** blocks → Matched to corresponding tool_use via `tool_use_id`, contains output content + is_error flag

#### Tool Use Structure

tool_use block:
```json
{
  "type": "tool_use",
  "id": "toolu_abc123",
  "name": "Bash",
  "input": {
    "command": "ls -la",
    "description": "List files"
  }
}
```

tool_result block (paired, same parent message):
```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_abc123",
  "content": [{"type": "text", "text": "stdout output..."}],
  "is_error": false
}
```

Key insight: tool_use + tool_result are always in the same assistant message. The tool_use is the request (what was called, with what input), the tool_result is the response (what came back, exit code/output). These are paired and correlated via `id` ↔ `tool_use_id`.

#### Bash Tool Inputs

Bash tool_use has `input.command` (the shell command) and `input.description`. The exit code is NOT directly in the JSONL — it's inferred from `is_error` on the tool_result. When `is_error=true`, exit_code is non-zero.

#### Common Fields

Nearly all events share:
- `uuid` — unique event ID
- `timestamp` — ISO 8601 format (e.g., "2026-04-23T17:14:13.983Z")
- `sessionId` — session UUID (same across all lines in a file)
- `version` — Claude Code version (e.g., "2.1.118")
- `cwd` — working directory at time of event

### 2. Adapter Design

#### IngestAdapter Protocol

```python
class IngestAdapter(Protocol):
    def ingest(self, path: str | Path) -> EventModel: ...
    def list_event_types(self) -> list[str]: ...
    @property
    def metadata(self) -> dict: ...
```

#### ClaudeCodeAdapter Implementation Plan

1. Open file, read line by line
2. For each line: `json.loads()` → parse into internal representation
3. Map events:
   - `user` → MessageEvent(role="user", content=message.content)
   - `assistant` text blocks → MessageEvent(role="assistant", content=text)
   - `assistant` tool_use blocks → ToolUseEvent(tool_name=name, input=input, ...)
   - `assistant` tool_result blocks → correlate to previous tool_use via id, set output + exit_code inference
   - `system` with level=error → ErrorEvent
4. Collect session metadata from first events (sessionId, version, cwd)
5. Skip: permission-mode, file-history-snapshot, last-prompt, queue-operation, thinking blocks

#### Edge Cases

- **Tool result matching**: tool_use + tool_result may be in the same assistant content array. Use tool_use id → tool_result.tool_use_id correlation.
- **Missing tool_result**: Some tool_use blocks may never get a tool_result (truncated session). Emit ToolUseEvent with output=None.
- **Orphan tool_result**: tool_result without matching tool_use in same session. Log warning, emit as ToolUseEvent with tool_name="unknown".
- **Line-by-line parsing**: `file.readline()` with try/except per line, skip malformed, accumulate warnings.
- **Partial last line**: If final line is truncated (no newline after valid JSON), the last valid line is still processed.
- **Empty file**: Return EventModel with events=[].
- **Very large files**: Claude Code session files can be 10K+ lines. Adapter should not load entire file into memory (line-by-line iteration).

### 3. Test Fixture Design

Five fixtures matching SPEC.md spec:

#### honest_session.jsonl (~30 lines)
- 1 permission-mode event
- 2 user messages with simple queries
- 2 assistant responses with tool_use + tool_result pairs
- Commands succeed (exit 0)
- Agent claims match what actually happened
- Claims extractable: "tests pass", "file created", "no errors"

#### dishonest_session.jsonl (~35 lines)
- Similar structure to honest
- Agent summary claims "all tests pass" but command exit code is non-zero
- Agent claims "minimal change" but diff shows large file edits
- Evidence contradicts claims

#### ambiguous_session.jsonl (~20 lines)
- Few tool_use events (limited evidence)
- Agent makes claims but little tool output to verify
- Designed for low evidence_completeness score

#### corrupt_session.jsonl (~18 lines)
- First 15 lines valid JSONL
- Line 16: truncated (missing closing brace)
- Valid lines should still parse
- Warnings generated for malformed lines

#### empty_session.jsonl (0 lines)
- Empty file
- Adapter returns EventModel with events=[], no crash

#### JSONL Line Format for Fixtures

Each fixture uses a simplified JSONL format that is structurally similar to real Claude Code exports but hand-crafted for test scenarios:

```jsonl
{"type":"permission-mode","permissionMode":"bypassPermissions","sessionId":"honest-001"}
{"parentUuid":null,"isSidechain":false,"type":"user","uuid":"u-001","timestamp":"2026-05-04T10:00:00Z","message":{"role":"user","content":"Fix the login bug"}}
{"parentUuid":"u-001","isSidechain":false,"type":"assistant","uuid":"a-001","timestamp":"2026-05-04T10:00:05Z","message":{"role":"assistant","content":[{"type":"text","text":"Let me look at the login code."},{"type":"tool_use","id":"tu-001","name":"Bash","input":{"command":"cd /repo && grep -r 'login' src/","description":"Find login code"}}]}}
```

### 4. Key Planning Inputs

Files to create (in order):
1. `blackbox/adapters/__init__.py` — IngestAdapter protocol
2. `blackbox/adapters/claude_code.py` — ClaudeCodeAdapter class
3. `test_fixtures/honest_session.jsonl`
4. `test_fixtures/dishonest_session.jsonl`
5. `test_fixtures/ambiguous_session.jsonl`
6. `test_fixtures/corrupt_session.jsonl`
7. `test_fixtures/empty_session.jsonl`

Tests (deferred to Phase 6 per SPEC.md test strategy section, or write alongside adapter):

The SPEC.md says `adapters/claude_code.py → 4 tests (valid, malformed, empty, truncated)`. These should be created as part of this phase or deferred to Phase 6 depending on project test strategy. Given Phase 2's purpose is to build the adapter, tests should be included.

### 5. Dependencies

- No new runtime dependencies (uses stdlib `json`, `pathlib`)
- Test dependencies: pytest, pytest-mock (from dev deps)
- Existing models from Phase 1 (EventModel, ToolUseEvent, etc.)
