# Phase 6: Tests, PyPI Packaging & CI

**Waves:** 2
**Plans:** 4

---

## Plan 6.1: README, LICENSE & GitHub Templates (Wave 1)

**Wave:** 1
**Depends on:** None (Wave 1)
**Files to create:**
- `README.md` (full rewrite)
- `LICENSE`
- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/feature.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`

<task id="p6-1-1">
<read_first>
- `pyproject.toml` — license = "MIT" already declared; author email
- `06-CONTEXT.md` — README decisions (standard sections, basic badges, one example)
- `SPEC.md` lines 304-347 — CLI commands and output format for the example
</read_first>

<action>
Rewrite `README.md` with the following structure:

```markdown
# Black Box Recorder

<!-- badges: CI | PyPI | Python | License -->

Know what your AI agent actually did — not what it said it did.

## Description

(2-3 paragraphs: what it is, the lie detector differentiator, pre-commit verification focus)

## Installation

```bash
pip install blackbox-recorder
```

## Quickstart

```bash
blackbox analyze session.jsonl
```

Show the full verification report output matching SPEC.md format (risk banner, scores, icon-based claims, error loops).

## CLI Reference

Brief reference for: `analyze`, `analyze --json`, `list`, `report <run-id>`, `config get/set/show/init`.

## How It Works

Brief pipeline explanation: JSONL → Parse → Extract Claims → Collect Evidence → Cross-Reference → Detect Errors → Report.

## Configuration

Reference `.blackbox/config.yaml` structure with llm provider, thresholds.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
```

Use shields.io badges for: GitHub Actions CI status, PyPI version, Python version, MIT license.
One usage example showing `blackbox analyze session.jsonl` output with report.
Write clean, intentional prose per SOUL.md standards — no AI-slop, no filler.
</action>

<acceptance_criteria>
- `README.md` contains `## Description`, `## Installation`, `## Quickstart`, `## CLI Reference`, `## How It Works`, `## Configuration`, `## Development`, `## License` headers
- `README.md` contains at least 4 shields.io badge image links
- `README.md` contains a code block with `pip install blackbox-recorder`
- `README.md` contains a code block with `blackbox analyze` and output showing score/risk
- README feels intentional, not generated
</acceptance_criteria>
</task>

<task id="p6-1-2">
<read_first>
- `pyproject.toml` — license field confirms MIT
</read_first>

<action>
Create `LICENSE` file with the MIT license text:

```
MIT License

Copyright (c) 2026 Agent Black Box Recorder

Permission is hereby granted...
```
</action>

<acceptance_criteria>
- `LICENSE` file exists at repo root
- `LICENSE` contains "MIT License" and "Permission is hereby granted"
</acceptance_criteria>
</task>

<task id="p6-1-3">
<read_first>
- No existing templates to match — create fresh
</read_first>

<action>
Create `.github/ISSUE_TEMPLATE/bug.yml`:

```yaml
name: Bug Report
description: Report a bug
title: "[Bug]: "
labels: ["bug"]
body:
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What happened?
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Reproduction
      description: Steps to reproduce
      placeholder: |
        1. Run 'blackbox analyze ...'
        2. See error
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
  - type: input
    id: version
    attributes:
      label: Version
      description: blackbox-recorder version
```

Create `.github/ISSUE_TEMPLATE/feature.yml`:

```yaml
name: Feature Request
description: Suggest an idea
title: "[Feature]: "
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What problem does this solve?
  - type: textarea
    id: solution
    attributes:
      label: Proposed solution
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
```

Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Summary

<!-- One sentence summary -->

## Changes

- <!-- Bullet list of changes -->

## Test plan

- [ ] Tests pass (`pytest`)
- [ ] Manual verification steps
```
</action>

<acceptance_criteria>
- `.github/ISSUE_TEMPLATE/bug.yml` exists with valid YAML
- `.github/ISSUE_TEMPLATE/feature.yml` exists with valid YAML
- `.github/PULL_REQUEST_TEMPLATE.md` exists
- `python -c "import yaml; yaml.safe_load(open('.github/ISSUE_TEMPLATE/bug.yml'))"` succeeds
- `python -c "import yaml; yaml.safe_load(open('.github/ISSUE_TEMPLATE/feature.yml'))"` succeeds
</acceptance_criteria>
</task>

---

## Plan 6.2: Dev Dependencies & CI Workflow (Wave 1)

**Wave:** 1
**Depends on:** None (Wave 1 — parallel with 6.1)
**Files to modify:**
- `pyproject.toml`
**Files to create:**
- `.github/workflows/ci.yml`

<task id="p6-2-1">
<read_first>
- `pyproject.toml` — existing build config, dependencies, [project.scripts]
- `06-CONTEXT.md` D-05 to D-10 — CI decisions
</read_first>

<action>
Add `[project.optional-dependencies] dev` section to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-cov>=6",
  "ruff>=0.11",
  "mypy>=1.15",
]
```

Append `[tool.ruck]` and `[tool.mypy]` sections:

```toml
[tool.ruck]
target-version = "py314"
line-length = 100

[tool.mypy]
python_version = "3.14"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

No other changes to existing pyproject.toml sections.
</action>

<acceptance_criteria>
- `pyproject.toml` contains `[project.optional-dependencies]` with `dev` key
- `pyproject.toml` contains `pytest-cov` in dev dependencies
- `pyproject.toml` contains `ruff` in dev dependencies
- `pyproject.toml` contains `mypy` in dev dependencies
- `pyproject.toml` contains `[tool.ruck]` section
- `pyproject.toml` contains `[tool.mypy]` section
- `pip install -e ".[dev]"` succeeds (verify if possible)
</acceptance_criteria>
</task>

<task id="p6-2-2">
<read_first>
- `06-CONTEXT.md` D-05 to D-10 — CI decisions (GitHub Actions, single workflow, Python 3.14, Ubuntu, ruff + mypy + pytest-cov, push to main + PRs, coverage measure no gate)
</read_first>

<action>
Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.14"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Lint
        run: ruff check .
      - name: Type check
        run: mypy blackbox/
      - name: Test with coverage
        run: pytest --cov=blackbox --cov-report=term

  publish:
    if: startsWith(github.ref, 'refs/tags/v')
    needs: [test]
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install build tools
        run: pip install hatchling hatch-vcs
      - name: Build
        run: pip install build && python -m build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

The publish job triggers on any tag starting with `v` (e.g., `v0.1.0`). Uses PyPI trusted publishing (OIDC) — no API tokens in secrets.
</action>

<acceptance_criteria>
- `.github/workflows/ci.yml` exists
- File contains `on: push: branches: [main]`
- File contains `on: pull_request: branches: [main]`
- File contains `runs-on: ubuntu-latest`
- File contains `python-version: ["3.14"]`
- File contains `ruff check .`
- File contains `mypy blackbox/`
- File contains `pytest --cov=blackbox --cov-report=term`
- File contains `pypa/gh-action-pypi-publish@release/v1`
- File contains `id-token: write` (trusted publishing)
- File contains `if: startsWith(github.ref, 'refs/tags/v')`
</acceptance_criteria>
</task>

---

## Plan 6.3: E2E Pipeline Integration Tests (Wave 2)

**Wave:** 2
**Depends on:** Plan 6.2 (dev dependencies exist for pytest-cov)
**Files to create:**
- `tests/test_e2e_pipeline.py`

<task id="p6-3-1">
<read_first>
- `06-CONTEXT.md` D-14 — E2E test decision
- `06-CONTEXT.md` Specifics section — E2E test structure ideas
- `test_fixtures/honest_session.jsonl` — golden fixture format
- `test_fixtures/dishonest_session.jsonl` — golden fixture format
- `test_fixtures/ambiguous_session.jsonl` — golden fixture format
- `test_fixtures/corrupt_session.jsonl` — golden fixture format
- `test_fixtures/empty_session.jsonl` — golden fixture format
- `blackbox/cli.py` — CLI app for CliRunner usage
- `tests/test_cli.py` — existing CliRunner pattern to follow
</read_first>

<action>
Create `tests/test_e2e_pipeline.py` with integration tests that run the full pipeline via `typer.testing.CliRunner` on each golden fixture. Follow existing test conventions (plain `def test_*`, `assert`).

The tests need to handle that pipeline stages may require LLM calls (claim extraction). The cross-referencer and error loop detector don't need LLM. Use mocking for the LLM-dependent stages where needed, but test the full adapter → evidence → cross-ref → detection → report chain.

Test structure:

```python
"""End-to-end pipeline integration tests using golden fixtures."""

import json
from pathlib import Path
from typer.testing import CliRunner
from blackbox.cli import app

runner = CliRunner()

FIXTURES_DIR = Path("test_fixtures")


def test_e2e_honest_session():
    """Full pipeline on honest_session.jsonl produces HIGH completeness + HIGH veracity."""
    result = runner.invoke(app, ["analyze", str(FIXTURES_DIR / "honest_session.jsonl"), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # Honest session: all claims match evidence
    assert data["evidence_completeness"] >= 50  # most claims evidenced
    assert data["claim_veracity"] >= 50  # evidenced claims match


def test_e2e_dishonest_session():
    """Full pipeline on dishonest_session.jsonl produces HIGH completeness + LOW veracity."""
    result = runner.invoke(app, ["analyze", str(FIXTURES_DIR / "dishonest_session.jsonl"), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # Has evidence but claims contradict
    assert "evidence_completeness" in data
    assert "claim_veracity" in data


def test_e2e_ambiguous_session():
    """Full pipeline on ambiguous_session.jsonl produces LOW completeness."""
    result = runner.invoke(app, ["analyze", str(FIXTURES_DIR / "ambiguous_session.jsonl"), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "evidence_completeness" in data


def test_e2e_empty_session():
    """Full pipeline on empty_session.jsonl returns gracefully."""
    result = runner.invoke(app, ["analyze", str(FIXTURES_DIR / "empty_session.jsonl"), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # Empty session should still produce a valid report structure


def test_e2e_corrupt_session():
    """Full pipeline on corrupt_session.jsonl handles partial data."""
    result = runner.invoke(app, ["analyze", str(FIXTURES_DIR / "corrupt_session.jsonl"), "--json"])
    # Should handle gracefully — either 0 or non-zero but not crash
    assert "No session file" not in result.stdout
```

Use `--json` flag for machine-parseable output. Tests validate that the pipeline runs end-to-end without crashes and produces structured report output. Mock the LLM call in claim_extractor if needed to avoid API dependency in tests.

Existing mock patterns from `tests/test_claim_extractor.py` should be followed.
</action>

<acceptance_criteria>
- `tests/test_e2e_pipeline.py` exists
- File contains `from typer.testing import CliRunner`
- File contains `runner = CliRunner()`
- File contains at least 5 test functions (`def test_e2e_*`)
- `pytest tests/test_e2e_pipeline.py -v` runs without import errors
- Each test uses `runner.invoke(app, ["analyze", ...])`
</acceptance_criteria>
</task>

---

## Plan 6.4: PyPI Publishing & Release (Wave 2)

**Wave:** 2
**Depends on:** Plan 6.2 (CI workflow is the publishing mechanism); Plan 6.3 (tests verify pipeline works)
**Files to create:**
- (none — all CI config done in 6.2.2)
**Files to modify:**
- `.planning/STATE.json` — mark Phase 6 complete after verification

<task id="p6-4-1">
<read_first>
- `.github/workflows/ci.yml` — verify publish job exists (created in 6.2.2)
- `pyproject.toml` — verify hatch-vcs version source
- `06-CONTEXT.md` D-11 to D-13 — publishing decisions
</read_first>

<action>
Verify the publish job is correctly configured in `.github/workflows/ci.yml`:

1. The `publish` job must have `if: startsWith(github.ref, 'refs/tags/v')` (already configured)
2. Must use `pypa/gh-action-pypi-publish@release/v1` with `id-token: write` (already configured)
3. Version is driven by git tags via `hatch-vcs` (already configured in pyproject.toml)

**Release process (document in README or a RELEASE.md):**

To release v0.1.0:
```bash
git tag v0.1.0
git push origin v0.1.0
```

CI will:
1. Run all tests (must pass)
2. Build wheel + sdist via `python -m build`
3. Publish to PyPI via trusted publishing

**No code changes needed** — the CI workflow from Plan 6.2 is the publishing mechanism.

Verification steps:
- Confirm `pyproject.toml` has `source = "vcs"` under `[tool.hatch.version]`
- Confirm `[project.scripts]` has `blackbox = "blackbox.cli:main"`
- Run `hatch version` to verify VCS-based version resolves (optional, needs git tag)
</action>

<acceptance_criteria>
- `.github/workflows/ci.yml` has publish job with `pypa/gh-action-pypi-publish`
- Publish job has `id-token: write` permission
- Publish job requires `test` job to pass
- `pyproject.toml` has `source = "vcs"` under `[tool.hatch.version]`
- Version format uses `v` prefix convention (v0.1.0)
</acceptance_criteria>
</task>
