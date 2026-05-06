# Phase 6: Tests, PyPI Packaging & CI — Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the project. Polish the README, set up CI/CD, add E2E integration tests, configure PyPI publishing, and add repo health files. After this phase, the project is documented, CI-verified, and pip-installable via PyPI.

**What this phase delivers:**
- Full OSS README with install, quickstart, CLI reference, badges, and example output
- GitHub Actions CI (test + lint on push/PR, publish on tag)
- Automated PyPI publishing via trusted publishing (OIDC)
- E2E integration tests running full pipeline against golden fixtures
- Repo health files (LICENSE, issue templates, PR template)
- 0.1.0 release on PyPI
</domain>

<decisions>
## Implementation Decisions

### README
- **D-01:** Full OSS README with sections: Description, Install, Quickstart, CLI Reference, How It Works, Configuration, Development, License
- **D-02:** Header badges: CI status, PyPI version, Python version, license (basic set)
- **D-03:** One usage example — `blackbox analyze` with its report output
- **D-04:** Standard sections (not minimal, not docs/ dir)

### CI Pipeline
- **D-05:** GitHub Actions — single workflow file (ci.yml)
- **D-06:** Python 3.14 only (matches requires-python in pyproject.toml)
- **D-07:** Ubuntu only (no platform-specific deps)
- **D-08:** Triggers: push to main + all PRs
- **D-09:** Lint check: ruff + mypy
- **D-10:** Coverage: pytest-cov with report, no hard threshold gate

### PyPI Publishing
- **D-11:** Automated on tag push via GitHub Actions trusted publishing (OIDC)
- **D-12:** Version 0.1.0 for first release
- **D-13:** Tag-based versioning via hatch-vcs (already configured)

### E2E Tests
- **D-14:** Add integration tests that run `blackbox analyze` on each golden fixture and assert report contains expected scores/sections

### Repo Housekeeping
- **D-15:** Add MIT LICENSE file to repo root (already declared in pyproject.toml)
- **D-16:** Issue templates: bug report + feature request
- **D-17:** PR template with checklist

### Claude's Discretion
- E2E test implementation details (CLI runner vs subprocess, specific assertions)
- CI workflow step organization (within the single-file constraint)
- README wording and structure (within the sections defined above)
- Issue/PR template format and detail level
- Coverage tool choice (pytest-cov or coverage.py)
- Ruff and mypy config settings

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & Philosophy
- `SPEC.md` — Full specification. Key sections: lines 399-409 (test coverage targets), lines 425-432 (packaging & distribution)
- `SOUL.md` — Project craft standards. README must feel intentional.

### Existing Phase Definitions
- `.planning/phases/phase-1.md` through `phase-5.md` — Prior phase definitions
- `.planning/STATE.json` — Phase tracking state

### Existing Code
- `pyproject.toml` — Build config (hatchling + hatch-vcs), dependencies, entry point
- `blackbox/cli.py` — CLI entry point with all commands
- `tests/` — 45 existing unit tests across 8 test files

### Test Fixtures
- `test_fixtures/honest_session.jsonl` — Golden fixture for E2E testing
- `test_fixtures/dishonest_session.jsonl` — Golden fixture for E2E testing
- `test_fixtures/ambiguous_session.jsonl` — Golden fixture for E2E testing
- `test_fixtures/corrupt_session.jsonl` — Golden fixture for E2E testing
- `test_fixtures/empty_session.jsonl` — Golden fixture for E2E testing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` — Already configured with hatchling build + hatch-vcs versioning. Just needs dev deps added (ruff, mypy, pytest-cov).
- `blackbox/cli.py` — Full CLI with `main` entry point. E2E tests can use CliRunner or subprocess.
- `tests/` — 45 existing tests. Established patterns: plain `def test_*`, `assert`, `unittest.mock`, `typer.testing.CliRunner`.

### Established Patterns
- Plain `def test_*` with `assert` — all tests follow this.
- Pydantic `model_dump()` for serialization.
- `_atomic_write_json` pattern for safe file writes.

### Integration Points
- CI runs `pytest` on push/PR — configure with `pytest-cov` and optional `--cov-report=term`.
- PyPI publish step runs on tag push — uses `hatchling build` + `publish` with trusted publishing.
- E2E tests run `blackbox analyze` against golden fixtures and verify report output.

</code_context>

<specifics>
## Specific Ideas

### E2E Test Structure
- Use `typer.testing.CliRunner` (existing pattern in CLI tests) to run the full pipeline
- For each golden fixture, invoke `analyze` and validate the report output
- Honest session: expect high completeness + veracity
- Dishonest session: expect high completeness + low veracity
- Ambiguous session: expect low completeness
- Corrupt session: expect warnings + partial recovery
- Empty session: expect "no events found"

### CI Workflow Steps
1. Checkout + setup Python 3.14
2. Install dependencies (pip install -e . + dev extras)
3. Run ruff check
4. Run mypy
5. Run pytest with coverage
6. (On tag) Build + publish to PyPI via trusted publishing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

Items deferred from SPEC.md (live capture, Telescope/AgentReplay adapters, CI gate, web dashboard, richer evidence types, cross-session analytics, rollback automation) remain deferred for future phases.

</deferred>

---

*Phase: 6-tests-pypi-packaging-ci*
*Context gathered: 2026-05-06*
