# Phase 3 Research: Claim Extraction + Evidence Collection

**Researched:** 2026-05-04
**Status:** Ready for planning
**Sources:** OpenAI API docs, Anthropic API docs, Ollama docs, httpx docs, existing codebase

---

## 1. LLM API Integration Patterns

### 1.1 Provider API Formats (httpx, no SDK)

All three providers are accessed via httpx `POST` requests. The config already has the fields: `provider`, `api_key`, `model`, `base_url`.

#### OpenAI (`POST {base_url}/chat/completions`)
- **Auth header:** `Authorization: Bearer {api_key}`
- **Request body:**
  ```json
  {
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "Extract claims from agent messages."},
      {"role": "user", "content": "Agent message text here..."}
    ],
    "response_format": { "type": "json_object" },
    "temperature": 0.0
  }
  ```
- **JSON mode requires** the word "json" in the system prompt or API rejects it.
- **Response parse path:** `response.json()["choices"][0]["message"]["content"]`
- `finish_reason` check: if `"length"` → truncated output, handle gracefully.

#### Anthropic (`POST {base_url}/v1/messages`)
- **Auth header:** `x-api-key: {api_key}` (not Bearer)
- **Required header:** `anthropic-version: 2023-06-01`
- **Request body:**
  ```json
  {
    "model": "claude-opus-4-7",
    "max_tokens": 1024,
    "system": "Extract claims from agent messages.",
    "messages": [
      {"role": "user", "content": "Agent message text here..."}
    ]
  }
  ```
- **No JSON mode** for non-tool responses in MVP — rely on prompt instructing JSON output.
- **Structured Outputs** (`output_config`) exists but requires newer models — skip for MVP, use prompt-based JSON.
- **Response parse path:** `response.json()["content"][0]["text"]`
- `stop_reason`: `"end_turn"` = complete, `"max_tokens"` = truncated.

#### Ollama (OpenAI-compatible, `POST {base_url}/chat/completions`)
- Same format as OpenAI but `api_key` is required by client yet ignored by server.
- Supports `response_format: { "type": "json_object" }`.
- Default base_url: `http://localhost:11434/v1`
- Response parse path: same as OpenAI.

### 1.2 httpx Patterns

Already a dependency (`httpx>=0.28`). Use `httpx.Client` (sync is fine for CLI tool, no need for async).

**Recommended pattern:**
```python
import httpx
from blackbox.config import load_config

config = load_config()
headers = {}
if config.llm.provider == "openai":
    headers["Authorization"] = f"Bearer {config.llm.api_key}"
elif config.llm.provider == "anthropic":
    headers["x-api-key"] = config.llm.api_key
    headers["anthropic-version"] = "2023-06-01"

timeout = httpx.Timeout(60.0, connect=15.0)
with httpx.Client(timeout=timeout, headers=headers) as client:
    resp = client.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
```

**Error handling per SPEC.md (lines 368-377):**
- Timeout → retry 1x, then skip → `"Claim analysis timed out — limited results"`
- Invalid JSON response → retry with stricter prompt
- Connection refused (Ollama not running) → `"Ollama not found — start with 'ollama serve'"`
- No claims extracted → return empty list (not an error)

### 1.3 Key Design Decisions from SPEC.md + 03-CONTEXT.md

| Decision | Detail |
|----------|--------|
| Provider abstraction | `if/elif` on config.llm.provider — 3 request formaters, same response parser |
| JSON parsing | Use `json.loads()` on response content, validate with Pydantic `Claim` model |
| Temperature | Set to 0.0 for deterministic extraction |
| Retry | 1 retry on timeout; linear backoff (1s) is simpler than exponential for MVP |
| Empty result | Empty claim list is valid return (not an error) |

---

## 2. Evidence Collection from Claude Code Events

### 2.1 Event Model Inventory (from `blackbox/models/event.py`)

| Event type | Fields relevant to evidence |
|---|---|
| `ToolUseEvent` | `tool_name` (str), `input` (dict), `output` (str\|None), `is_error` (bool) |
| `CommandEvent` | `exit_code` (int\|None), `stdout_snippet`, `stderr_snippet` (but Phase 2 adapter only produces ToolUseEvent for Bash) |
| `FileEditEvent` | `path`, `action`, `diff` (but Phase 2 adapter does NOT produce FileEditEvent — files are edited via tool_use with tool_name="Edit"/"Write") |
| `ErrorEvent` | `error_type`, `message`, `context` |
| `MessageEvent` | agent's text claims (input to claim_extractor, not evidence_collector) |

### 2.2 Evidence Types Mapping (per SPEC.md lines 36-37)

**1. Command exit codes** — from `ToolUseEvent` where `tool_name == "Bash"`
- `is_error` flag → exit code inference: `is_error=True` ≈ non-zero exit, `is_error=False` ≈ exit 0
- `output` field → stdout/stderr text
- `input["command"]` or `input` dict → the command string
- Note: No direct `exit_code` field on ToolUseEvent — must infer from `is_error`.

**2. Git diffs** — from `ToolUseEvent` with `tool_name in ("Edit", "Write", "Bash")`
- Parse `output` for diff-like content (lines starting with `+`, `-`, `@@`)
- `input["path"]` or `input["file_path"]` → file being edited
- If tool_name is "Bash", check `output` for `git diff` command output

**3. Error logs** — from `ErrorEvent`
- Direct mapping: `error_type`, `message`, `context`

**4. File changes** — from `ToolUseEvent` with `tool_name in ("Edit", "Write")`
- `input` dict contains the file path (key varies: `path`, `file_path`, `target`)
- `output` may contain the applied diff
- Action inference: create vs edit from whether `input` contains `content` vs `old_string`/`new_string`

### 2.3 Git Evidence Handling (SPEC.md line 376)

`git rev-parse --git-dir` check using `subprocess.run`. If non-zero exit, produce typed "unavailable" entry. If available, scan ToolUseEvent outputs for diff content.

### 2.4 EvidenceSet Structure (Claude's Discretion per 03-CONTEXT.md)

Recommend using a Pydantic model:
```python
class EvidenceItem(BaseModel):
    type: Literal["command", "git_diff", "error", "file_change"]
    source_tool: str | None = None
    source_idx: int  # index into EventModel.events
    value: str       # the evidence payload
    is_error: bool = False

class EvidenceSet(BaseModel):
    commands: list[EvidenceItem] = []
    git_diffs: list[EvidenceItem] = []
    errors: list[EvidenceItem] = []
    file_changes: list[EvidenceItem] = []
```

---

## 3. Existing Codebase Patterns

### 3.1 Pydantic Model Style (Phase 1 patterns)

- **Inherit from `BaseModel`** (pydantic v2). No model_config or extra settings unless needed.
- **Use `StrEnum`** for enums (`from enum import StrEnum`).
- **`from __future__ import annotations`** — used in adapter, optional in pipeline.
- **Union type syntax:** `list[CommandEvent | FileEditEvent | MessageEvent | ToolUseEvent | ErrorEvent]` (Python 3.10+ pipe-union, available in 3.14).
- **Literal types** for discriminated unions: `type: Literal["command"] = "command"`.
- **Optional fields:** `field: str | None = None` (no `Optional[]` wrapper).
- **`model_validator(mode='after')`** for post-validation mutations (see `score.py` cap pattern).
- **`@property`** for computed fields (see `percentage` in score.py).

**Python 3.14 specifics to follow:**
- No walrus anti-pattern.
- Pipe union everywhere (not `Union[]`).
- Type annotations on all function signatures (project convention from Phase 2 adapter).

### 3.2 Module Organization

```
blackbox/pipeline/
  claim_extractor.py      ← NEW: LLM-based extraction
  evidence_collector.py   ← NEW: evidence gathering
  cross_referencer.py     ← Phase 4
  error_loop_detector.py  ← Phase 4
  report_generator.py     ← Phase 4
```

Pipeline modules import from `blackbox.models.*` and `blackbox.config`. They do NOT import from `blackbox.cli` or `blackbox.adapters`. Data flows forward: adapter → pipeline → storage.

### 3.3 Testing Patterns (from Phase 2 tests)

- **File:** `tests/test_claude_code_adapter.py` — one file per module under test.
- **Framework:** pytest with plain `def test_*` functions (no classes).
- **Fixture path constant:** `FIXTURES_DIR = Path("test_fixtures")` at module level.
- **Assert style:** plain `assert` statements (not `self.assert*`).
- **Error case:** `with pytest.raises(FileNotFoundError, match="No session file"):`.
- No pytest fixtures yet — Phase 2 tests construct adapters inline.
- **10 tests** for the adapter module.

**Test targets for Phase 3 (from 03-CONTEXT.md):**
- `claim_extractor.py` → **6 tests**: valid extraction, no messages (empty), LLM timeout, bad JSON response, LLM offline (connection refused), empty session (no events).
- `evidence_collector.py` → **4 tests**: commands with evidence present, git evidence scanning, no commands/events (empty output), errors only (ErrorEvent present).

### 3.4 Import Convention

```python
from blackbox.config import load_config
from blackbox.models.event import EventModel, ToolUseEvent, ErrorEvent
from blackbox.models.claim import Claim, ClaimCategory
```

Relative imports avoided (adapter uses absolute). Logger via `logging.getLogger(__name__)`.

### 3.5 Config Access Pattern

```python
from blackbox.config import load_config

config = load_config()
# config.llm.provider   → "openai" | "anthropic" | "ollama"
# config.llm.api_key    → str | None
# config.llm.model      → str
# config.llm.base_url   → str (default: "http://localhost:11434/v1")
```

Env var overrides apply automatically via `load_config()` (e.g., `BLACKBOX_LLM_PROVIDER`).

---

## 4. Specific Implementation Guidance

### 4.1 Claim Extractor Architecture

```
Input:  EventModel (specifically MessageEvent where role="assistant")
Flow:   1. Filter events to assistant messages with content
         2. For each assistant message, build LLM prompt
         3. Call provider via httpx (deterministic, temp=0)
         4. Parse JSON response into list[Claim]
         . Append original text to each Claim
Output: list[Claim] (sorted by source_message_idx)

Format prompt (per SPEC.md lines 236-258):
  "Extract structured claims from this agent message.
   Categories: test_result, outcome, scope, approach, state.
   Return JSON: {\"claims\": [{\"text\": str, \"category\": str, \"verifiable\": bool}]}"
```

**Error cases to handle:**
| Case | Behavior |
|------|----------|
| No assistant messages | Return `[]` |
| LLM timeout | Retry 1x, log warning, return partial |
| LLM returns invalid JSON | Retry with stricter prompt ("Return ONLY valid JSON"), fail → log + skip |
| LLM offline (connection refused) | Raise clear error message |
| LLM returns empty claims array | Valid result — return `[]` |

### 4.2 Evidence Collector Architecture

```
Input:  EventModel
Flow:   1. Iterate EventModel.events
         2. Classify each event into evidence category
         3. Extract structured evidence from relevant fields
         4. Check git repo status (subprocess)
Output: EvidenceSet (Pydantic model, 4 categories)
```

**Event classification table:**
| Event type | tool_name / other | Evidence category |
|---|---|---|
| ToolUseEvent | "Bash" | Command (exit code from is_error) |
| ToolUseEvent | "Edit" or "Write" | File change |
| ToolUseEvent | "Bash" with git diff in output | Git diff |
| ToolUseEvent | "Edit" or "Write" with diff in output | Git diff |
| ErrorEvent | any | Error |
| CommandEvent | any | Command (direct exit_code) |
| FileEditEvent | any | File change (direct diff field) |

The adapter can produce both ToolUseEvent and CommandEvent/FileEditEvent depending on the source. Evidence collector should handle both.

### 4.3 Prompt Design Guidance

**System prompt principles:**
- Instruct JSON output format explicitly (needed for OpenAI JSON mode compliance).
- Define 5 categories with examples.
- Instruct to mark opinions/predictions as `verifiable: false`.
- Temperature = 0.0 for consistency.
- Token limit: ~500-1000 for extraction responses (claims are short).

**Truncation strategy (Claude's Discretion):**
- If message content > ~8000 tokens, truncate to 6000 tokens with `...[truncated]` suffix.
- Use token counting via character estimation (~4 chars per token) as a reasonable proxy for MVP (no tokenizer dependency).

### 4.4 Dependency Considerations

- **httpx** already in `pyproject.toml`.
- No new runtime dependencies needed.
- **pytest-mock** for dev — may want for mocking httpx in tests. Not currently in pyproject.toml but listed in SPEC.md line 384. Add during planning.

---

## 5. Key Design Decisions for the Planner

1. **EvidenceSet location:** `blackbox/models/evidence.py` (new file) or inline in `evidence_collector.py`. Recommend models file for reusability in Phase 4.

2. **LLM client abstraction:** Can use a simple `if/elif` on provider string (simpler than `typing.Protocol`). Three request-formatting functions, one response parser.

3. **Exit code inference:** ToolUseEvent has no direct `exit_code` field. Use `is_error` bool. `True → non-zero`, `False → zero`. This is a simplification — true exit code would require parsing the adapter differently.

4. **git diff detection:** Heuristic-based (parse tool output for `diff` patterns). Not a formal `git diff` call during evidence collection (though a `git rev-parse` check is needed for the "skip git evidence" behavior).

5. **EvidenceSet vs flat list:** Recommend `EvidenceSet` (Pydantic) with four typed lists. Cleaner for Phase 4 cross-referencing.

6. **Empty/null handling:** Per SPEC.md: empty claims array → "No claims found to verify". Empty evidence → "No evidence found." Neither is an error.

7. **No shared pipeline state:** claim_extractor and evidence_collector operate independently on the same EventModel. They do not share state. Phase 4 cross-referencer consumes both outputs.
