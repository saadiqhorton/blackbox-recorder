Phase 5 Prompt — Report Generator, Run Store & CLI

Phase Goal

Wire up the complete verification pipeline into working CLI commands. Build the report generator (markdown + JSON), enhance the run store to persist all pipeline artifacts, and connect everything through the CLI. After this phase, users can run `blackbox analyze session.jsonl` and get a verification report.

Exit Criteria

• [ ] ReportGenerator renders incident_report.md matching SPEC.md format (risk banner, scores, icon-based claims, error loops)
• [ ] ReportGenerator renders incident_report.json with same data for CI consumption
• [ ] RunStore has per-type save/load methods: save_claims, save_evidence, save_score, save_error_loops, save_report + corresponding load methods
• [ ] CLI `blackbox analyze <path>` runs full pipeline synchronously with Rich progress output
• [ ] CLI `blackbox analyze --json <path>` outputs machine-readable JSON to stdout
• [ ] CLI `blackbox list` shows previously analyzed runs in a table
• [ ] CLI `blackbox report <run-id>` regenerates report from stored artifacts
• [ ] CLI `blackbox config` supports get, set (dot notation), show, init
• [ ] 14 tests pass: 4 report_generator + 5 run_store + 5 CLI

Stack Context

- SPEC.md lines 49-50 (report gen), 94-101 (module structure), 304-347 (CLI + output), 348-378 (config + error handling), 399-409 (test targets)
- Existing pipeline: CrossReferencer → LieScore, ErrorLoopDetector → list[ErrorLoop], ClaimExtractor → list[Claim], EvidenceCollector → EvidenceSet
- `blackbox/cli.py` — Typer skeleton with Rich Console imported
- `blackbox/storage/run_store.py` — RunStore with create_run, load_metadata, append_event, list_runs, run_exists
- `blackbox/config.py` — load_config(), save_default_config(), env var overrides
- All models: score.py (LieScore), claim.py (Claim), error_loop.py (ErrorLoop), evidence.py (EvidenceSet), event.py (EventModel)
- `05-CONTEXT.md` — Full implementation decisions from discussion
- Test conventions: plain `def test_*`, `assert`, `unittest.mock`, typer.testing.CliRunner for CLI
- Test fixtures: test_fixtures/*.jsonl (5 golden sessions)

Implementation Decisions (from discussion — see 05-CONTEXT.md for full detail)

- Report format = Match SPEC.md exactly (icon-based, risk banner, scores table, claim list with confidence %)
- Run Store = Individual per-type save/load methods
- CLI analyze = Full pipeline sync with Rich progress, partial report on LLM failure
- CLI config = Dot notation (llm.provider), commands: get/set/show/init
- Progress to stderr, --json outputs to stdout

GStack Role Check

No GStack roles needed — architecture is fully specified in SPEC.md and locked by prior plan-ceo-review + plan-eng-review sessions. Implementation decisions captured in 05-CONTEXT.md.

Superpowers Execution

1. Use test-driven-development skill: RED-GREEN-REFACTOR
2. Write failing test first
3. Implement minimal code to pass
4. Verify with self-review

What to Commit

```
blackbox/pipeline/
  report_generator.py           NEW: Markdown + JSON report rendering

blackbox/storage/
  run_store.py                  MODIFY: Add save/load methods for all artifact types

tests/
  test_report_generator.py      NEW: 4 tests
  test_storage.py               NEW: 5 tests (save/load claims, score, loops, report, list)
  test_cli.py                   NEW: 5 tests (analyze, analyze --json, list, report, config)
  __init__.py                   MODIFY if needed
```
