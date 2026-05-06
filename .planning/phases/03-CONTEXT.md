# Phase 3: Claim Extraction + Evidence Collection — Context

**Gathered:** 2026-05-04
**Status:** Ready for planning
**Source:** PRD Express Path (SPEC.md)

<domain>
## Phase Boundary

Build the claim extraction and evidence collection pipeline stages. Claim extraction reads agent messages from a parsed EventModel and uses an LLM (OpenAI/Anthropic/Ollama via httpx) to extract structured claims. Evidence collection scans events for verifiable outputs: command exit codes, git diffs, error logs, and file changes. Both modules produce typed outputs consumed by Phase 4 (cross-referencing + scoring).

**What this phase delivers:**
- `blackbox/pipeline/claim_extractor.py` — LLM-based claim extraction from agent messages
- `blackbox/pipeline/evidence_collector.py` — Evidence gathering from event log
- Tests: 6 tests for claim_extractor, 4 tests for evidence_collector
</domain>

<decisions>
### Architecture (Locked by SPEC.md)

#### Claim Extractor Design
- **Decision:** Use httpx (direct HTTP, vendor-neutral) for LLM calls — supports OpenAI, Anthropic, and Ollama via compatible API schemas
- **Rationale:** SPEC.md line 76 specifies httpx for LLM calls. Vendor-neutral avoids lock-in. Ollama support enables local/offline use.
- **Consequence:** Must handle 3 different API schemas, auth methods, and base URLs. Config already has llm.provider, llm.api_key, llm.model, llm.base_url fields.
- **Source:** SPEC.md lines 34-35, 76

#### Claim Extraction Input
- **Decision:** Extract claims from all assistant messages (not just final summary). The LLM prompt receives message content and returns structured JSON matching the Claim model.
- **Rationale:** SPEC.md line 233: "extracts structured claims from the agent's final summary message and intermediate status messages"
- **Consequence:** Claim has `source_message_idx` to track which message a claim came from.
- **Source:** SPEC.md lines 230-258

#### Claim Output Schema
- **Decision:** The LLM returns JSON matching: `{"claims": [{"text": str, "category": str, "source_message_idx": int, "verifiable": bool}]}` where category is one of: test_result, outcome, scope, approach, state
- **Rationale:** SPEC.md lines 236-259 define the schema and categories explicitly.
- **Consequence:** Output parses into existing `Claim` model from `blackbox/models/claim.py`. Categories map to `ClaimCategory` StrEnum.
- **Source:** SPEC.md lines 236-258

#### Evidence Collection Scope
- **Decision:** Evidence collector scans EventModel.events and gathers 4 evidence types: command exit codes (from ToolUseEvent with tool_name="Bash"), git diffs (from ToolUseEvent with tool_name="Edit" or "Write"), error logs (from ErrorEvent), and file changes (from FileEditEvent or tool_use with tool_name="Edit"/"Write")
- **Rationale:** SPEC.md lines 36-37 define the 4 evidence types. ToolUseEvent from the adapter carries tool_name, output, and is_error fields needed for evidence extraction.
- **Consequence:** EvidenceSet will contain typed evidence entries that the cross-referencer (Phase 4) matches against claims.
- **Source:** SPEC.md lines 36-37, 262-267

#### LLM Provider Abstraction
- **Decision:** Claim extractor reads provider config (provider, api_key, model, base_url) from blackbox.config at runtime. Each provider has a different request format but the same response schema expectation.
- **Rationale:** SPEC.md lines 76, 348-363 define httpx with provider abstraction. Config already loaded by `blackbox.config.load_config()`.
- **Consequence:** Must implement request formatting for openai, anthropic, and ollama. ollama uses the same schema as OpenAI (OpenAI-compatible API).

#### Error Handling (Locked by SPEC.md)
- **Decision:** LLM API timeout → retry 1x, then skip. LLM invalid response → retry with stricter prompt. Ollama not running → clear error. No claims extracted → return empty list (not an error).
- **Rationale:** SPEC.md lines 368-377 define error handling for all pipeline stages.
- **Consequence:** ClaimExtractor must implement retry logic and produce meaningful error messages. Empty claim list is valid (session with no agent summaries).
- **Source:** SPEC.md lines 368-377

#### Git Evidence Handling
- **Decision:** If not a git repo, skip git evidence with a clear message.
- **Rationale:** SPEC.md line 376: "Not a git repo → Skip git evidence → 'Git evidence unavailable — not a git repo'"
- **Consequence:** Evidence collector checks `git rev-parse --git-dir` and produces a typed "unavailable" evidence entry, not an error.
- **Source:** SPEC.md line 376

### Claude's Discretion
- Prompt template design for the LLM claim extraction call (instruction phrasing, few-shot examples)
- EvidenceSet internal data structure (the typed container for collected evidence)
- How git diffs are extracted from tool output (parsing strategies for diff output)
- Test fixture design for claim_extractor and evidence_collector tests
- Whether to use `typing.Protocol` for the LLM client abstraction (follows adapter pattern from Phase 2)
- Retry backoff strategy (linear, exponential, fixed delay)
- How to handle tool outputs larger than the LLM context window (truncation strategy)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & Requirements
- `SPEC.md` — Locked requirements. Key sections: lines 34-37 (claim extraction + evidence collection scope), lines 76 (httpx), lines 94-101 (module structure), lines 230-258 (claim extraction detail), lines 260-287 (scoring model), lines 348-377 (config + error handling), lines 399-409 (test coverage targets)

### Existing Models
- `blackbox/models/claim.py` — Claim, EvidenceRef, ClaimCategory, ConfidenceLevel models (already exist, Phase 1)
- `blackbox/models/score.py` — EvidenceCompleteness, ClaimVeracity, LieScore, RiskLabel, compute_risk_label (already exist, Phase 1)
- `blackbox/models/event.py` — EventModel, ToolUseEvent, MessageEvent, ErrorEvent, FileEditEvent types consumed by pipeline

### Config & Storage
- `blackbox/config.py` — Config loading with llm provider, api_key, model, base_url fields
- `blackbox/storage/run_store.py` — RunStore for persisting pipeline output (used in later phases)

### Phase Definitions
- `.planning/phases/phase-3.md` — Phase exit criteria
- `.planning/phases/phase-1.md` — Completed Phase 1 (models, config, storage)
- `.planning/phases/phase-2.md` — Completed Phase 2 (JSONL adapter, test fixtures)

### Standards
- `SOUL.md` — Project craft standards

</canonical_refs>

<specifics>
## Specific Ideas

### Claim Extractor Prompt Design
The LLM prompt should instruct the model to:
1. Read the assistant message content (agent's summary of what it did)
2. Extract structured claims about test results, outcomes, scope, approach, and state
3. Return JSON matching the Claim schema
4. Mark unverifiable claims (opinions, predictions) with `verifiable: false`

### Evidence Collection Categories
- **Command evidence**: ToolUseEvent with tool_name="Bash" — extract exit code from is_error flag, stdout/stderr from output field
- **Git evidence**: ToolUseEvent with tool_name in ("Edit", "Write", "Bash") — look for git diff output in tool output
- **Error evidence**: ErrorEvent entries — extract error_type, message, context
- **File change evidence**: ToolUseEvent with tool_name in ("Edit", "Write") — extract file path from input dict, diff from output

### EvidenceSet Structure (Claude's Discretion)
An internal container grouping evidence by type, enabling the Phase 4 cross-referencer to match claims against the appropriate evidence category.

### Test Coverage Targets
- `pipeline/claim_extractor.py` → 6 tests: valid extraction, no messages, LLM timeout, bad JSON response, LLM offline, empty session
- `pipeline/evidence_collector.py` → 4 tests: commands with evidence, git evidence, no commands/events, errors only

</specifics>

<deferred>
## Deferred Ideas

None — PRD covers phase scope per SPEC.md.

Items deferred from MVP (SPEC.md lines 57-65) remain deferred: live capture, Telescope/AgentReplay adapters, CI gate, web dashboard, richer evidence types.

</deferred>

---

*Phase: 3-claim-extraction-evidence-collection*
*Context gathered: 2026-05-04 via PRD Express Path*
