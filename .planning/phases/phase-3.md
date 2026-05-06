Phase 3: Claim Extraction & Evidence Collection

Phase Goal

Build the LLM-based claim extraction pipeline and evidence collection pipeline stages. After this phase, the system can extract structured claims from agent messages using an LLM (OpenAI/Anthropic/Ollama) and collect 4 evidence types (commands, git diffs, errors, file changes) from EventModel events.

Exit Criteria

- [x] ClaimExtractor correctly parses LLM JSON responses into Claim objects (6 passing tests)
- [x] ClaimExtractor handles all 3 LLM providers (openai, anthropic, ollama)
- [x] EvidenceCollector extracts command evidence from Bash tool_use events
- [x] EvidenceCollector handles git repo check gracefully (detect git, produce "unavailable" item)
- [x] All 10 tests pass: `pytest tests/test_claim_extractor.py tests/test_evidence_collector.py -v`

Stack Context

- SPEC.md lines 34-37, 230-258, 262-267, 368-377, 399-409
- 03-CONTEXT.md — Locked decisions on provider abstraction, retry logic, temperature 0.0
- 03-RESEARCH.md — LLM API patterns, evidence type mapping, codebase conventions
- Existing models: Claim, EvidenceRef, ClaimCategory, EventModel, ToolUseEvent, ErrorEvent, FileEditEvent

GStack Role Check

No GStack roles needed — architecture locked by SPEC.md, CONTEXT.md, and prior reviews.

What to Commit

```
blackbox/pipeline/
  __init__.py               # Exports ClaimExtractor, EvidenceCollector
  claim_extractor.py        # ClaimExtractor with 3-provider LLM support
  evidence_collector.py     # EvidenceCollector with 4 evidence type extraction

blackbox/models/
  evidence.py               # EvidenceItem, EvidenceSet models

tests/
  test_claim_extractor.py   # 6 tests (valid, no messages, timeout, bad JSON, offline, empty)
  test_evidence_collector.py # 4 tests (commands, git, no events, errors)
```
