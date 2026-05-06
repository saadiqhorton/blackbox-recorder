# Black Box Recorder

[![CI](https://img.shields.io/github/actions/workflow/status/agent-blackbox/blackbox-recorder/ci.yml?branch=main&label=CI&logo=github)](https://github.com/agent-blackbox/blackbox-recorder/actions)
[![PyPI](https://img.shields.io/pypi/v/blackbox-recorder?logo=pypi&logoColor=white)](https://pypi.org/project/blackbox-recorder/)
[![Python](https://img.shields.io/pypi/pyversions/blackbox-recorder?logo=python&logoColor=white)](https://pypi.org/project/blackbox-recorder/)
[![License](https://img.shields.io/pypi/l/blackbox-recorder?logo=mit&logoColor=white)](https://github.com/agent-blackbox/blackbox-recorder/blob/main/LICENSE)

Know what your AI agent actually did — not what it said it did.

## Description

AI coding agents talk a good game. They say "all tests pass," "minimal change," "no
side effects." Sometimes it is true. Sometimes it is not. Black Box Recorder is a
forensic pre-commit verification tool that treats agents as witnesses and cross-
examines them against the evidence.

The core differentiator is the **lie detector**. Most agent tools replay what
happened. Black Box Recorder tells you whether the agent is telling the truth about
what happened. It extracts claims from the agent's own summaries, then cross-
references each claim against empirical evidence — exit codes, git diffs, error
logs, command history. The output is a trust report: what to accept, what to
scrutinize, and what the evidence actually shows.

This is **pre-commit verification**, not postmortem forensics. Verify the agent's
claims before their changes land in your repository. Designed for individual
developers using Claude Code, with an architecture that supports team and CI use
as the tool matures.

## Installation

```bash
pip install blackbox-recorder
```

Requires Python 3.14 or later. Published as a pre-alpha (Development Status 2)
package on PyPI — the verification loop works, but interfaces may change.

## Quickstart

Point `blackbox analyze` at a Claude Code session export:

```bash
blackbox analyze ~/.claude/sessions/7c3a1f2e.jsonl
```

```text
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

Each claim shows an icon (pass, warn, fail), a confidence level (exact or semantic),
a match score against the evidence, and the evidence snippet that supports or
contradicts it. The risk banner summarizes whether to proceed, block, or require
review.

For machine-readable output:

```bash
blackbox analyze --json session.jsonl > report.json
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `analyze <path>` | Analyze a session JSONL file |
| `analyze --json <path>` | Machine-readable JSON output |
| `list` | List previously analyzed runs |
| `report <run-id>` | Regenerate a report from stored analysis |
| `config set <key> <value>` | Set a config value |
| `config get <key>` | Read a config value |
| `config show` | Display the full configuration |
| `config init` | Create a default `.blackbox/config.yaml` |

## How It Works

The analysis pipeline processes a session JSONL file through six stages:

1. **Ingest** — Parse the Claude Code session export into a typed event model
2. **Extract** — Send the agent's messages to an LLM to extract structured claims
3. **Collect** — Gather evidence: command exit codes, git diffs, error logs, file
   changes
4. **Cross-reference** — Match each claim against the evidence, producing two
   independent scores (evidence completeness and claim veracity)
5. **Detect loops** — Scan for repeated failures, circular file edits, and error
   spikes
6. **Report** — Render the results as a human-readable markdown report

All artifacts are stored in `.blackbox/runs/<run-id>/` for later review or
regeneration.

## Configuration

Black Box Recorder is configured via `.blackbox/config.yaml` in the project root:

```yaml
# .blackbox/config.yaml
llm:
  provider: openai       # openai | anthropic | ollama | custom
  model: gpt-4o          # provider-specific model name
  api_key: null          # set via `blackbox config set` or env var
  base_url: null         # custom endpoint (for Ollama)

storage:
  runs_dir: .blackbox/runs

thresholds:
  min_completeness: 50   # below this → HIGH risk
  min_veracity: 50       # below this → HIGH risk
```

Use `blackbox config init` to create the default file, then `blackbox config set`
to configure your LLM provider and API key. Keys can also be set via environment
variables (`BLACKBOX_LLM_KEY`, `BLACKBOX_LLM_PROVIDER`, `BLACKBOX_LLM_MODEL`).

## Development

```bash
git clone https://github.com/agent-blackbox/blackbox-recorder
cd blackbox-recorder
pip install -e ".[dev]"
pytest
```

The test suite uses pytest with golden fixture sessions that have known ground
truth — honest, dishonest, ambiguous, corrupt, and empty. Run `pytest -v` to see
which scenarios are covered.

## License

MIT
