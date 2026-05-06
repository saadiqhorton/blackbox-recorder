# Phase 3: Claim Extraction + Evidence Collection

**Waves:** 2
**Plans:** 2

---

## Plan 3.1: Claim Extractor (Wave 1)

**Wave:** 1
**Depends on:** None (Wave 1)
**Files to create:**
- `blackbox/pipeline/__init__.py`
- `blackbox/pipeline/claim_extractor.py`
- `blackbox/models/evidence.py`
- `tests/test_claim_extractor.py`
**Files to modify:**
- `blackbox/models/__init__.py`

<task id="p3-1-1">
<read_first>
- `blackbox/adapters/__init__.py` — existing init style for patterns
- `blackbox/models/__init__.py` — existing export pattern
- `SPEC.md` lines 94-101 — canonical module structure defining `blackbox/pipeline/` path
</read_first>

<action>
Create `blackbox/pipeline/__init__.py`:

```python
"""Pipeline stages for claim extraction, evidence collection, and scoring."""
from blackbox.pipeline.claim_extractor import ClaimExtractor

__all__ = ["ClaimExtractor"]
```
</action>

<acceptance_criteria>
- `from blackbox.pipeline import ClaimExtractor` does not raise `ImportError`
- File is valid Python 3.14+ syntax
- Matches existing init style (absolute imports, `__all__` list)
</acceptance_criteria>
</task>

<task id="p3-1-2">
<read_first>
- `blackbox/models/claim.py` — existing Pydantic model style (BaseModel, StrEnum)
- `.planning/phases/03-RESEARCH.md` section 2.4 — EvidenceSet structure
</read_first>

<action>
Create `blackbox/models/evidence.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    """A single piece of evidence extracted from an event."""
    type: Literal["command", "git_diff", "error", "file_change"]
    source_tool: str | None = None
    source_idx: int
    value: str
    is_error: bool = False


class EvidenceSet(BaseModel):
    """Typed container for all evidence collected from an EventModel."""
    commands: list[EvidenceItem] = []
    git_diffs: list[EvidenceItem] = []
    errors: list[EvidenceItem] = []
    file_changes: list[EvidenceItem] = []

    @property
    def total_count(self) -> int:
        return len(self.commands) + len(self.git_diffs) + len(self.errors) + len(self.file_changes)
```

Then update `blackbox/models/__init__.py` to export:
```python
from blackbox.models.evidence import EvidenceItem, EvidenceSet
```
</action>

<acceptance_criteria>
- `from blackbox.models.evidence import EvidenceItem, EvidenceSet` succeeds
- `EvidenceSet().total_count == 0`
- `EvidenceItem` accepts all 4 type literals
- `EvidenceSet` fields default to `[]` when not provided
</acceptance_criteria>
</task>

<task id="p3-1-3">
<read_first>
- `SPEC.md` lines 230-258 — claim extraction schema
- `SPEC.md` lines 368-377 — error handling
- `.planning/phases/03-RESEARCH.md` sections 1, 4 — LLM API patterns
- `blackbox/config.py` — config access pattern (load_config)
- `blackbox/models/claim.py` — Claim, ClaimCategory
- `blackbox/models/event.py` — EventModel, MessageEvent
- `.planning/phases/03-CONTEXT.md` — decisions section
</read_first>

<action>
Create `blackbox/pipeline/claim_extractor.py` with `ClaimExtractor` class.

Architecture:
- Constructor takes no args (reads config from `load_config()` internally)
- `extract_claims(events: EventModel) -> list[Claim]`:
  1. Filter events to `MessageEvent` where `role == "assistant"` with non-empty content
  2. If none found, return `[]`
  3. Build LLM prompt from message contents with `source_message_idx` tracking
  4. Format request based on provider (openai / anthropic / ollama)
  5. Call LLM via `httpx.Client` with `timeout = httpx.Timeout(60.0, connect=15.0)`
  6. On timeout: retry 1x with 1s backoff, log warning, return partial
  7. Parse JSON into `list[Claim]` using Pydantic
  8. On invalid JSON: retry 1x with stricter prompt, skip message on fail
  9. On connection refused: raise `ConnectionError("...not running...")`

Provider request formats — **must include `temperature=0.0`** in every request body for deterministic extraction:
- **OpenAI/Ollama**: `POST {base_url}/chat/completions`, `Authorization: Bearer {api_key}`, body with `messages: [system, user]`, `response_format: {"type": "json_object"}`, `"temperature": 0.0`
- **Anthropic**: `POST {base_url}/v1/messages`, `x-api-key: {api_key}`, `anthropic-version: 2023-06-01`, body with `system` string, `messages: [user]`, `max_tokens: 1024`, `"temperature": 0.0`

System prompt (shared):
```
Extract structured claims from the following agent message.
Categories: test_result, outcome, scope, approach, state.
Return JSON: {"claims": [{"text": str, "category": str, "verifiable": bool}]}
```

Response parsing:
- OpenAI/Ollama: `response.json()["choices"][0]["message"]["content"]`
- Anthropic: `response.json()["content"][0]["text"]`
- Parse with `json.loads()` then validate each claim with Pydantic `Claim` model
</action>

<acceptance_criteria>
- `extract_claims()` takes `EventModel` and returns `list[Claim]`
- Empty EventModel returns `[]`
- Valid assistant messages produce correctly parsed `Claim` objects
- Categories map to `ClaimCategory` enum
- `source_message_idx` set to original event position
- Timeout triggers 1 retry
- Invalid JSON triggers retry with stricter prompt
- Connection refused raises `ConnectionError` with provider name
</acceptance_criteria>
</task>

<task id="p3-1-4">
<read_first>
- `tests/test_claude_code_adapter.py` — existing test patterns
- `blackbox/pipeline/claim_extractor.py` — implementation to test
</read_first>

<action>
Create `tests/test_claim_extractor.py` with 6 tests, mocking `httpx.Client`:

1. `test_valid_extraction` — mock LLM returns valid JSON, assert `Claim` objects correct
2. `test_no_assistant_messages` — EventModel with only user messages, assert `[]`
3. `test_llm_timeout` — first call raises `httpx.TimeoutException`, second succeeds, assert 2 calls
4. `test_bad_json_response` — first returns invalid JSON, second succeeds, assert retried
5. `test_llm_offline` — raises `httpx.ConnectError`, assert `ConnectionError`
6. `test_empty_session` — zero events, assert `[]`

Mock helper:
```python
class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
    def json(self):
        return self._json_data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=MagicMock(), response=self)
```
</action>

<acceptance_criteria>
- All 6 tests pass with `pytest tests/test_claim_extractor.py -v`
- No real HTTP calls (httpx fully mocked via `unittest.mock.patch`)
- Follows Phase 2 conventions (plain `def test_*`, `assert`, no classes)
</acceptance_criteria>
</task>

---

## Plan 3.2: Evidence Collector (Wave 2 — blocked on Wave 1)

**Wave:** 2
**Depends on:** Plan 3.1 task p3-1-2 (EvidenceSet model)
**Files to create:**
- `blackbox/pipeline/evidence_collector.py`
- `tests/test_evidence_collector.py`
**Files to modify:**
- `blackbox/pipeline/__init__.py`

<task id="p3-2-1">
<read_first>
- `SPEC.md` lines 36-37, 262-267 — evidence collection scope
- `.planning/phases/03-RESEARCH.md` section 2 — evidence types mapping
- `blackbox/models/event.py` — all event types (ToolUseEvent, ErrorEvent, CommandEvent, FileEditEvent)
- `blackbox/models/evidence.py` — EvidenceSet, EvidenceItem
</read_first>

<action>
Create `blackbox/pipeline/evidence_collector.py` with `EvidenceCollector` class.

`collect(events: EventModel) -> EvidenceSet`:
- Iterate `events.events`, classify each event:
  - `ToolUseEvent(tool_name="Bash")` → command evidence (exit code from `is_error`); also scan `output` for git diff patterns
  - `ToolUseEvent(tool_name in ("Edit", "Write"))` → file change evidence from `input["path"]`; scan output for diffs
  - `ErrorEvent` → error evidence from `error_type`, `message`, `context`
  - `CommandEvent` → command evidence (direct `exit_code`)
  - `FileEditEvent` → file change evidence (direct `diff`, `path`)
- Git repo check: `subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, timeout=5.0)` once per collect() call, cached
- If not a git repo → insert into `git_diffs` list: `EvidenceItem(type="git_diff", source_idx=0, value="Git evidence unavailable -- not a git repo")`
- Git diff heuristic: scan output for `diff --git`, `+`/`-` line prefixes, `@@` hunk markers
</action>

<acceptance_criteria>
- `collect()` takes `EventModel`, returns `EvidenceSet`
- Bash `is_error=True` produces command evidence with `is_error=True`
- Edit/Write tool_use produces file_change evidence
- ErrorEvent produces error evidence
- Git check runs once, cached per collection
- Non-git-repo produces "Git evidence unavailable" item
- Empty EventModel returns `EvidenceSet(total_count=0)`
</acceptance_criteria>
</task>

<task id="p3-2-2">
<read_first>
- `blackbox/pipeline/evidence_collector.py` — implementation to test
- `blackbox/models/event.py` — event construction
- `blackbox/models/evidence.py` — EvidenceSet assertions
</read_first>

<action>
Create `tests/test_evidence_collector.py` with 4 tests:

1. `test_command_evidence` — EventModel with 2 Bash ToolUseEvents (one passing, one failing), assert command evidence extracted correctly with `is_error` and exit code values
2. `test_git_diff_evidence` — EventModel with Edit tool_use containing diff output, mock git check succeeds, assert git_diffs populated
3. `test_no_events` — empty EventModel, assert `total_count == 0`
4. `test_error_events_only` — EventModel with 2 ErrorEvents, assert errors list populated, other lists empty

Mock `subprocess.run` for test 2 to simulate git repo available.
</action>

<acceptance_criteria>
- All 4 tests pass with `pytest tests/test_evidence_collector.py -v`
- Test 1 distinguishes zero vs non-zero exit codes
- Test 2 handles git diff extraction with mocked git repo
- Test 3 returns empty EvidenceSet
- Test 4 extracts only error evidence from ErrorEvent-only session
</acceptance_criteria>
</task>

<task id="p3-2-3">
<read_first>
- `blackbox/pipeline/__init__.py` — current exports
- `SPEC.md` lines 94-101 — canonical module structure (pipeline/ path)
</read_first>

<action>
Update `blackbox/pipeline/__init__.py`:

```python
"""Pipeline stages for claim extraction, evidence collection, and scoring."""
from blackbox.pipeline.claim_extractor import ClaimExtractor
from blackbox.pipeline.evidence_collector import EvidenceCollector

__all__ = ["ClaimExtractor", "EvidenceCollector"]
```
</action>

<acceptance_criteria>
- `from blackbox.pipeline import EvidenceCollector` succeeds
- No circular import errors
</acceptance_criteria>
</task>

---

## Verification

```bash
pytest tests/test_claim_extractor.py tests/test_evidence_collector.py -v
# Expected: 10 passed
```

## Exit Criteria

- [ ] ClaimExtractor correctly parses LLM JSON responses into Claim objects (6 tests)
- [ ] ClaimExtractor handles all 3 LLM providers (openai, anthropic, ollama)
- [ ] EvidenceCollector extracts command evidence from Bash tool_use events
- [ ] EvidenceCollector handles git repo check gracefully (detect git, produce "unavailable" item)
- [ ] All 10 tests pass

## Must-haves

- [ ] ClaimExtractor correctly parses LLM JSON responses into Claim objects
- [ ] ClaimExtractor handles all 3 LLM providers (openai, anthropic, ollama)
- [ ] EvidenceCollector extracts command evidence from Bash tool_use events
- [ ] EvidenceCollector handles git repo check gracefully
- [ ] 10 tests pass

## Stack Context

- Models: `blackbox/models/claim.py` (Claim, EvidenceRef, ClaimCategory), `blackbox/models/evidence.py` (EvidenceSet, EvidenceItem), `blackbox/models/event.py` (EventModel, ToolUseEvent, MessageEvent, ErrorEvent, FileEditEvent, CommandEvent)
- Config: `blackbox/config.py` — `load_config()` returns `Config` with `llm.provider`, `llm.api_key`, `llm.model`, `llm.base_url`
- Existing pipeline: none yet (Phase 3 creates `blackbox/pipeline/`)
- Tests follow Phase 2 conventions: plain functions, `assert`, `unittest.mock` for external calls
- httpx already in dependencies per SPEC.md line 76
- pytest-mock may need to be added to dev dependencies for `mocker` fixture
- **Pipeline tests use inline EventModel construction** (not golden JSONL fixtures) because:
  - EventModel construction is already validated in Phase 2 adapter tests
  - Pipeline tests need fine-grained control over exact event types and combinations
  - Inline construction is more readable for test scenarios than parsing fixtures
