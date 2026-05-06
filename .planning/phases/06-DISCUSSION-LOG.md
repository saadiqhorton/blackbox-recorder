# Phase 6: Tests, PyPI Packaging & CI — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 6-tests-pypi-packaging-ci
**Areas discussed:** README scope, CI pipeline design, PyPI publishing & release, E2E tests & housekeeping

---

## README Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full OSS README | Install, quickstart, CLI reference, badges, example output | ✓ |
| Minimal README | Just install + usage example | |
| Full README + docs dir | Full README + docs/ directory | |

**User's choice:** Full OSS README

| Option | Description | Selected |
|--------|-------------|----------|
| Basic badges | CI, PyPI version, Python version, license | ✓ |
| No badges | Clean look | |
| All badges | Full set including style, coverage, last commit | |

**User's choice:** Basic badges

| Option | Description | Selected |
|--------|-------------|----------|
| One example | Single analyze command with report output | ✓ |
| Full CLI walkthrough | Multiple examples covering all commands | |
| No examples | Link to --help only | |

**User's choice:** One example

| Option | Description | Selected |
|--------|-------------|----------|
| Standard sections | Description, Install, Quickstart, CLI Reference, How It Works, Configuration, Development, License | ✓ |
| Minimal sections | Description, Install, Quickstart only | |

**User's choice:** Standard sections

---

## CI Pipeline Design

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub Actions | Native GitHub integration, free for OSS | ✓ |
| Another platform | | |

**User's choice:** GitHub Actions

| Option | Description | Selected |
|--------|-------------|----------|
| 3.14 only | Single version, matches requires-python | ✓ |
| Include nightly | 3.14 + 3.15 nightly | |

**User's choice:** 3.14 only

| Option | Description | Selected |
|--------|-------------|----------|
| Ubuntu only | Fastest, no platform-specific deps | ✓ |
| Full OS matrix | Ubuntu + macOS + Windows | |

**User's choice:** Ubuntu only

| Option | Description | Selected |
|--------|-------------|----------|
| Push to main + PRs | Standard OSS workflow | ✓ |
| All pushes | Every branch | |
| PRs only | Saves CI on WIP | |

**User's choice:** Push to main + PRs

---

## PyPI Publishing & Release

| Option | Description | Selected |
|--------|-------------|----------|
| Automated on tag | GitHub Actions with trusted publishing | ✓ |
| Manual publish | Run hatch publish locally | |

**User's choice:** Automated on tag

| Option | Description | Selected |
|--------|-------------|----------|
| 0.1.0 | First pre-release, matches Pre-Alpha classifier | ✓ |
| 1.0.0 | Wrong signal for pre-alpha | |

**User's choice:** 0.1.0

| Option | Description | Selected |
|--------|-------------|----------|
| Tag-based via hatch-vcs | Git tag drives version, single source of truth | ✓ |
| Manual version | Set in pyproject.toml | |
| Automated bumps | Bump commits or automated PRs | |

**User's choice:** Tag-based via hatch-vcs

---

## E2E Tests & Housekeeping

| Option | Description | Selected |
|--------|-------------|----------|
| Add E2E tests | Run full pipeline on golden fixtures, assert report | ✓ |
| Skip E2E | Unit tests sufficient | |

**User's choice:** Add E2E tests

| Option | Description | Selected |
|--------|-------------|----------|
| Contribution templates | Bug + feature issue templates, PR template | ✓ |
| Full community health | + CONTRIBUTING.md + SECURITY.md | |
| None | Skip community files | |

**User's choice:** Contribution templates

| Option | Description | Selected |
|--------|-------------|----------|
| Add MIT LICENSE | Already in pyproject.toml, needed for repo root | ✓ |
| Yes, add it | Same | |

**User's choice:** Add MIT LICENSE

| Option | Description | Selected |
|--------|-------------|----------|
| Measure in CI, no gate | pytest-cov, report visible, no threshold | ✓ |
| Enforce threshold | Set minimum % | |
| Skip | No coverage | |

**User's choice:** Measure in CI, no gate

| Option | Description | Selected |
|--------|-------------|----------|
| Single CI workflow | One .yml for test + lint + publish | ✓ |
| Separate workflows | ci.yml + release.yml | |
| One per concern | lint.yml + test.yml + publish.yml | |

**User's choice:** Single CI workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Ruff + mypy | Comprehensive lint + type checking | ✓ |
| Ruff only | Fast, basic | |
| No linter | Tests only | |

**User's choice:** Ruff + mypy

---

## Claude's Discretion

- E2E test implementation details (CliRunner vs subprocess, specific assertions)
- CI workflow step organization (within the single-file constraint)
- README wording and structure (within the sections defined above)
- Issue/PR template format and detail level
- Coverage tool choice (pytest-cov or coverage.py)
- Ruff and mypy config settings

## Deferred Ideas

None — discussion stayed within phase scope.
