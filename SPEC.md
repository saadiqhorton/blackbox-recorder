# Agent Black Box Recorder — Specification

> A forensic pre-commit verification tool for AI coding agent sessions.
> Core differentiator: the **lie detector** — extracts claims from agent session data
> and cross-references them against empirical evidence before changes land.

## Product Vision

### One-line pitch
Know what your AI agent actually did — not what it said it did.

### Core differentiator
The lie detector. Most agent tools show you *what happened*. Black Box Recorder
tells you *whether the agent is telling the truth about what happened*. It extracts
claims from the agent's own summaries ("all tests pass", "minimal change", "no side
effects") and cross-references them against empirical evidence — exit codes, git
diffs, error logs, command history.

### Strategic posture
**Pre-commit verification**, not postmortem forensics. Verify the agent's claims
BEFORE their changes land in your repo. The output is a trust report that tells you
what to review, what to reject, and what the evidence actually shows.

### Target user
Individual developers using AI coding agents (Claude Code first). Architecture
supports team/CI use as the tool matures.

## MVP Scope

### In scope (build this)

1. **Claude Code JSONL ingest** — read Claude Code session exports (`~/.claude/sessions/*.jsonl`)
2. **Single adapter** — Claude Code only. Prove the verification loop before expanding.
3. **Claim extraction** — LLM-based (user API key or Ollama). Extract structured claims from agent summaries.
4. **Evidence collection** — command exit codes, git diffs, error logs, file changes
5. **Cross-referencing** — match claims to evidence, produce two independent scores:
   - **Evidence completeness**: % of claims with supporting evidence
   - **Claim veracity**: of evidenced claims, % that match
6. **Confidence levels:**
   - **Exact**: evidence directly confirms (exit code, file match)
   - **Semantic**: evidence consistent but not proven
   - *(No LLM-judged level — circular to use one LLM to judge another)*
7. **Error loop detection** — 3 patterns:
   - Repeated failing commands (same command, non-zero exit, 3+ times)
   - Circular file edits (file edited back-and-forth)
   - Error spikes (5+ consecutive tool errors)
8. **Incident report generation** — human-readable markdown + machine-readable JSON
9. **CLI commands:**
   - `blackbox analyze <path>` — analyze a session JSONL file
   - `blackbox list` — list previously analyzed runs
   - `blackbox report <run-id>` — regenerate a report
   - `blackbox config` — manage configuration (LLM provider, keys, model)
10. **Storage** — file-based in `.blackbox/runs/<id>/` with per-artifact JSON files
11. **Config** — YAML config file at `.blackbox/config.yaml`

### Deferred (not in MVP)

| Item | Why deferred |
|------|-------------|
| Live capture (`blackbox run`) | PTY/signals/cross-platform complexity. Prove analysis loop first. |
| Telescope adapter | Prove Claude JSONL loop first. Add adapters after validation. |
| AgentReplay adapter | Same — prove loop first. |
| CI gate / GitHub Action | Natural follow-up after verification loop is proven. |
| Local web dashboard | CLI + markdown reports sufficient for MVP. |
| Richer evidence (cached tests, partial runs) | Start simple, enrich from user feedback. |

## Technical Architecture

### Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.14+ | Widely available, great ecosystem |
| CLI framework | Typer | Type-hint-driven, Rich integration, 2026 best practice |
| Event model | Pydantic v2 | Typed, validated, self-documenting |
| LLM calls | httpx (direct HTTP) | Vendor-neutral — works with OpenAI, Anthropic, Ollama |
| Testing | pytest + pytest-mock | Standard Python testing |
| Storage | JSON files per artifact | Simple, debuggable, grep-able |
| Packaging | PyPI via hatchling | `pip install blackbox-recorder` |
| Config | YAML | Human-readable, standard |

### Module structure

```
blackbox/
  __init__.py
  cli.py                    Typer app, command definitions
  config.py                 Config loading (YAML), provider setup

  adapters/
    __init__.py             IngestAdapter protocol
    claude_code.py          ClaudeCode JSONL adapter

  models/
    __init__.py
    event.py                EventModel, event types (Pydantic)
    claim.py                Claim, Confidence, EvidenceRef
    score.py                LieScore, EvidenceCompleteness, ClaimVeracity
    error_loop.py           ErrorLoop, PatternType

  pipeline/
    claim_extractor.py      LLM-based claim extraction
    evidence_collector.py   Gather evidence from events
    cross_referencer.py     Match claims to evidence → scores
    error_loop_detector.py  Pattern detection (3 patterns)
    report_generator.py     Markdown + JSON report rendering

  storage/
    run_store.py            Read/write run artifacts
    schema.py               Schema version handling

test_fixtures/
  honest_session.jsonl      Claims match evidence
  dishonest_session.jsonl   Claims contradict evidence
  ambiguous_session.jsonl   Limited evidence
  corrupt_session.jsonl     Malformed data
  empty_session.jsonl       0 events
```

### Data flow

```
JSONL file
    │
    ▼
ClaudeCodeAdapter.ingest()
    │  Parses JSONL line by line
    │  Skips malformed lines with warnings
    │  Returns EventModel
    ▼
ClaimExtractor.extract_claims(events)
    │  LLM call (OpenAI/Anthropic/Ollama)
    │  Extracts structured claims from agent summaries
    │  Returns list[Claim]
    ▼
EvidenceCollector.collect(events)
    │  Gathers: exit codes, git diffs, error logs, file changes
    │  Returns EvidenceSet
    ▼
CrossReferencer.cross_reference(claims, evidence)
    │  Matches each claim to evidence
    │  Computes: evidence completeness + claim veracity
    │  Returns LieScore
    ▼
ErrorLoopDetector.detect(events)
    │  Detects: repeated commands, circular edits, error spikes
    │  Returns list[ErrorLoop]
    ▼
ReportGenerator.generate(session, score, loops)
    │  Renders: incident_report.md + incident_report.json
    ▼
RunStore.save_run(run_id, artifacts)
    │  Writes to .blackbox/runs/<run-id>/
```

### Event model (Pydantic)

```python
class EventType(StrEnum):
    COMMAND = "command"
    FILE_EDIT = "file_edit"
    MESSAGE = "message"
    TOOL_USE = "tool_use"
    ERROR = "error"

class CommandEvent(BaseModel):
    type: EventType = EventType.COMMAND
    timestamp: datetime
    command: str
    args: list[str]
    exit_code: int | None
    stdout_snippet: str | None
    stderr_snippet: str | None
    working_directory: str | None

class FileEditEvent(BaseModel):
    type: EventType = EventType.FILE_EDIT
    timestamp: datetime
    path: str
    action: Literal["create", "edit", "delete"]
    diff: str | None

class MessageEvent(BaseModel):
    type: EventType = EventType.MESSAGE
    timestamp: datetime
    role: Literal["user", "assistant"]
    content: str

class ToolUseEvent(BaseModel):
    type: EventType = EventType.TOOL_USE
    timestamp: datetime
    tool_name: str
    input: dict
    output: str | None
    duration_ms: int | None

class ErrorEvent(BaseModel):
    type: EventType = EventType.ERROR
    timestamp: datetime
    error_type: str
    message: str
    context: str | None

class EventModel(BaseModel):
    session_id: str
    agent_type: str = "claude-code"
    task: str | None
    events: list[CommandEvent | FileEditEvent | MessageEvent |
                  ToolUseEvent | ErrorEvent]
    schema_version: str = "1.0"
```

### Storage layout

```
.blackbox/
  config.yaml                    LLM provider, key, model, thresholds
  runs/
    <run-id>/                    UUID-based
      metadata.json              Session metadata
      events.json                Normalized event model
      claims.json                Extracted claims with confidence
      evidence.json              Collected evidence
      lie_score.json             Evidence completeness + claim veracity
      error_loops.json           Detected error loops
      reports/
        incident_report.md       Human-readable
        incident_report.json     Machine-readable (for CI)
```

### Claim extraction

The LLM prompt extracts structured claims from the agent's final summary message
and intermediate status messages. Output schema:

```json
{
  "claims": [
    {
      "text": "All tests pass",
      "category": "test_result",
      "source_message_idx": 42,
      "verifiable": true
    },
    {
      "text": "Fixed the login bug",
      "category": "outcome",
      "source_message_idx": 45,
      "verifiable": true
    },
    {
      "text": "No side effects",
      "category": "scope",
      "source_message_idx": 45,
      "verifiable": true
    }
  ]
}
```

Claim categories:
- `test_result` — claims about test outcomes (most verifiable)
- `outcome` — claims about task completion
- `scope` — claims about what was changed
- `approach` — claims about what was attempted
- `state` — claims about system state

### Scoring model

Two independent sub-scores:

```python
evidence_completeness = evidenced_claims / total_claims
    # % of claims that have supporting evidence

claim_veracity = matching_claims / evidenced_claims
    # of evidenced claims, % that match the evidence

risk_label = lookup(evidence_completeness, claim_veracity)
    # HIGH: completeness < 50% or veracity < 50%
    # MEDIUM: completeness >= 50% and veracity >= 50%
    # LOW: completeness >= 80% and veracity >= 80%
```

Per-claim confidence:
- **Exact** (high): evidence directly confirms (exit code 0, git diff matches)
- **Semantic** (medium): evidence consistent but not proven (no contradiction found)
- **Missing** (low): no evidence found either way

### Error loop detection

Three pattern detectors:

1. **Repeated command**: same `command` string appears 3+ times with non-zero
   `exit_code`. Reports: command, count, time range, stderr snippet.

2. **Circular edit**: same file path edited 4+ times where diffs toggle between
   similar states (addition → removal → addition). Reports: file, edit count,
   time range.

3. **Error spike**: 5+ consecutive ErrorEvents within 60 seconds. Reports:
   error type, count, time range.

## CLI Design

### Commands

```
$ blackbox analyze session.jsonl          ← analyze a session
$ blackbox analyze --json session.jsonl   ← machine-readable output
$ blackbox list                           ← list analyzed runs
$ blackbox report <run-id>                ← regenerate report
$ blackbox config set llm_provider openai ← configure LLM
$ blackbox config set llm_key sk-...      ← set API key
$ blackbox config set llm_model gpt-4o    ← set model
$ blackbox config get llm_provider        ← read config
```

### Output format (human)

```markdown
BLACK BOX RECORDER — VERIFICATION REPORT
═══════════════════════════════════════════════════════════
SESSION:     7c3a1f2e | Claude Code | "Fix login tests"
DURATION:    4m 32s
ANALYZED:    2026-05-03 19:35:00 UTC

EVIDENCE COMPLETENESS: 80% ⚠️
  8/10 claims have supporting evidence
  2 claims: no evidence found

CLAIM VERACITY: 75% ⚠️
  6/8 evidenced claims match the evidence
  2 claims: evidence contradicts the claim

CLAIMS:
  ✅ All tests pass          (exact, 95%)    exit code 0
  ⚠️ Fixed the login bug     (semantic, 60%) missing repro run
  ❌ No side effects          (exact, 10%)   file changed outside scope

ERROR LOOPS:
  ⚠️ npm test failed 5×      (same error: "Cannot find 'auth'")
  ⚠️ src/auth.ts edited 4×   (oscillating)

RISK: MEDIUM — review before accepting
```

## Configuration

```yaml
# .blackbox/config.yaml
llm:
  provider: openai       # openai | anthropic | ollama | custom
  model: gpt-4o          # provider-specific model name
  api_key: null          # set via `blackbox config set` or env var
  base_url: null         # custom endpoint (for Ollama: http://localhost:11434/v1)

storage:
  runs_dir: .blackbox/runs

thresholds:
  min_completeness: 50   # below this → HIGH risk
  min_veracity: 50       # below this → HIGH risk
```

## Error handling

| Failure mode | Behavior | User sees |
|-------------|----------|-----------|
| File not found | Clear error | "No session file at <path>" |
| Malformed JSONL line | Skip line, continue | Warning with line number |
| Empty file | Return empty session | "No events found" |
| LLM API timeout | Retry 1x, then skip | "Claim analysis timed out — limited results" |
| LLM invalid response | Retry with stricter prompt | (transparent) |
| Ollama not running | Clear error | "Ollama not found — start with 'ollama serve'" |
| Not a git repo | Skip git evidence | "Git evidence unavailable — not a git repo" |
| No claims extracted | N/A score | "No claims found to verify" |
| Disk full during write | Graceful shutdown | "Could not write run data — disk full" |
| Corrupt config YAML | Fall back to defaults | Warning with parse error |

## Testing strategy

### Test framework
- pytest + pytest-mock for unit tests
- typer.testing.CliRunner for CLI integration tests
- 35 planned tests covering all code paths

### Golden fixtures
Five hand-crafted JSONL sessions with known ground truth:

| Fixture | Purpose |
|---------|---------|
| `honest_session.jsonl` | Claims match evidence. Expect: high completeness + veracity. |
| `dishonest_session.jsonl` | Claims contradict evidence. Expect: high completeness + low veracity. |
| `ambiguous_session.jsonl` | Limited evidence. Expect: low completeness. |
| `corrupt_session.jsonl` | Truncated at line 15. Expect: partial recovery + warnings. |
| `empty_session.jsonl` | 0 events. Expect: "no events found". |

### Test coverage diagram

```
[+] adapters/claude_code.py         → 4 tests (valid, malformed, empty, truncated)
[+] pipeline/claim_extractor.py     → 6 tests (valid, no messages, timeout, bad JSON, offline, empty)
[+] pipeline/evidence_collector.py  → 4 tests (commands, git, no commands, errors)
[+] pipeline/cross_referencer.py    → 5 tests (exact, semantic, contradiction, missing, mixed)
[+] pipeline/error_loop_detector.py → 5 tests (repeat, cycle, spike, normal, single)
[+] pipeline/report_generator.py    → 4 tests (all data, no claims, empty, JSON)
[+] storage/run_store.py           → 5 tests (save, atomic, disk full, load, missing, list)
[+] cli.py                          → 5 tests (analyze, analyze --json, list, config set, config get)
```

## Dependencies

### Runtime
- `typer` — CLI framework
- `pydantic` — typed event model
- `httpx` — HTTP client for LLM API calls
- `pyyaml` — config file parsing

### Development
- `pytest` — test framework
- `pytest-mock` — mocking
- `hatchling` + `hatch-vcs` — build system

## Distribution

- Package name: `blackbox-recorder`
- Published to PyPI
- Install: `pip install blackbox-recorder` or `pipx install blackbox-recorder`
- CLI entry point: `blackbox`
- GitHub Actions: publish to PyPI on tag push

## Future considerations

### Phase 2 candidates
- Live capture: `blackbox run <command>` with PTY, git watcher, file snapper
- Telescope adapter: ingest from Project Telescope's SQLite or JSON output
- AgentReplay adapter: ingest OpenTelemetry spans
- Richer evidence: parse test output for passed/failed counts, detect cached runs

### Post-MVP candidates (when demand emerges)
- CI gate: `blackbox analyze --fail-below <score>` for GitHub Actions
- Local web dashboard: browse runs, compare reports, score trends
- Cross-session analytics: which agents lie most, common failure patterns
- Rollback automation: `blackbox rollback <run-id>` to revert changes

---

*Generated by /plan-ceo-review + /plan-eng-review on 2026-05-03.*
*Outside voice: Codex plan review — 6 tension points surfaced, all resolved via user decisions.*
