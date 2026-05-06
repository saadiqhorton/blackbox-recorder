Phase 6: Tests, PyPI Packaging & CI

Phase Goal

Ship the project. Polish the README, set up CI/CD, add E2E integration tests, configure PyPI publishing, and add repo health files. After this phase, the project is documented, CI-verified, and pip-installable via PyPI.

Exit Criteria

• [ ] Full OSS README with Description, Install, Quickstart, CLI Reference, How It Works, Configuration, Development, License sections
• [ ] README includes basic header badges (CI status, PyPI version, Python version, license) and one `blackbox analyze` usage example with report output
• [ ] GitHub Actions CI workflow runs on push to main + PRs: ruff check, mypy, pytest with coverage (Python 3.14, Ubuntu)
• [ ] GitHub Actions publish workflow publishes to PyPI via trusted publishing on tag push (version 0.1.0)
• [ ] E2E integration tests run `blackbox analyze` on all 5 golden fixtures and verify report scores/sections
• [ ] MIT LICENSE file added to repo root
• [ ] Issue templates (bug report + feature request) and PR template in .github/
• [ ] All 45+ existing tests continue to pass; new E2E tests pass

Stack Context

- `SPEC.md` — Key sections: lines 399-409 (test coverage targets), lines 425-432 (packaging & distribution)
- `SOUL.md` — Project craft standards (README must feel intentional, not AI-slop)
- `06-CONTEXT.md` — 17 locked implementation decisions from discuss-phase
- Existing `pyproject.toml` — hatchling + hatch-vcs build config, version from VCS tags
- `blackbox/cli.py` — Full CLI with `main` entry point (`blackbox = blackbox.cli:main`)
- 45 existing tests across 8 test files (test_claim_extractor, test_claude_code_adapter, test_cli, etc.)
- Test conventions: plain `def test_*`, `assert`, `unittest.mock`, `typer.testing.CliRunner`
- `test_fixtures/*.jsonl` — 5 golden fixture sessions (honest, dishonest, ambiguous, corrupt, empty)
- README currently one line: "Know what your AI agent actually did — not what it said it did."
- No `.github/` directory exists yet

GStack Role Check

No GStack roles needed — all decisions locked in 06-CONTEXT.md and SPEC.md.

Implementation Decisions (from discussion — see 06-CONTEXT.md for full detail)

- Full OSS README: Description, Install, Quickstart, CLI Reference, How It Works, Configuration, Development, License
- Badges: CI status, PyPI version, Python version, license (shields.io)
- One usage example: `blackbox analyze` with report output
- CI: GitHub Actions, single ci.yml, Python 3.14, Ubuntu, trigger on push to main + PRs
- Lint: ruff check + mypy
- Coverage: pytest-cov with term report, no hard threshold
- PyPI: Automated via trusted publishing (OIDC) on tag push, version 0.1.0, hatch-vcs tag versioning
- E2E: CliRunner-based tests running full pipeline on golden fixtures
- Repo: MIT LICENSE, .github/ISSUE_TEMPLATE/bug.yml + feature.yml, .github/PULL_REQUEST_TEMPLATE.md

What to Commit

```
README.md                          FULL REWRITE: Full OSS README with sections, badges, example
LICENSE                            NEW: MIT license file
.github/
  workflows/
    ci.yml                         NEW: Test + lint on push/PR, publish on tag
  ISSUE_TEMPLATE/
    bug.yml                        NEW: Bug report template
    feature.yml                    NEW: Feature request template
  PULL_REQUEST_TEMPLATE.md         NEW: PR checklist template

tests/
  test_e2e_pipeline.py            NEW: Integration tests running full pipeline on golden fixtures

pyproject.toml                    MODIFY: Add dev dependencies (ruff, mypy, pytest-cov)
```
