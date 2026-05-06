Phase 4: Cross-Referencer, Scoring & Error Loop Detection

Phase Goal

Build the cross-referencing, scoring, and error loop detection pipeline stages. After this phase, the system can match extracted claims against collected evidence, compute independent verification scores (evidence completeness + claim veracity), detect three error loop patterns (repeated commands, circular edits, error spikes), and produce the core verification data that feeds report generation in Phase 5.

Exit Criteria

- [ ] CrossReferencer correctly matches claims to evidence and produces LieScore with evidence_completeness + claim_veracity
- [ ] CrossReferencer assigns per-claim confidence: exact (evidence directly confirms), semantic (consistent but unproven), missing (no evidence)
- [ ] CrossReferencer handles all-edge cases: no claims, no evidence, empty session, all contradictory
- [ ] ErrorLoopDetector detects all 3 patterns: repeated failing commands (same command, non-zero exit, 3+ times), circular edits (4+ edits toggling between states), error spikes (5+ consecutive ErrorEvents within 60 seconds)
- [ ] ErrorLoopDetector handles normal sessions (no loops), single-failure sessions (no loop false positive)
- [ ] 10 tests pass: 5 cross_referencer + 5 error_loop_detector

Stack Context

- SPEC.md lines 38-50 (cross-referencing), lines 52-55 (confidence levels), lines 56-65 (error loop detection), lines 267-285 (scoring model), lines 290-303 (error loop details), lines 399-409 (test coverage)
- Existing models — Claim (with evidence: list[EvidenceRef]), EvidenceSet (commands, git_diffs, errors, file_changes), EvidenceItem, LieScore, EvidenceCompleteness, ClaimVeracity, RiskLabel, ErrorLoop, PatternType, EventModel
- Existing pipeline — ClaimExtractor (produces list[Claim]), EvidenceCollector (produces EvidenceSet)
- Claim model has `evidence: list[EvidenceRef]` field — cross-referencer populates this per claim
- EvidenceSet has per-category typed lists consumed by cross-referencer matching logic
- Tests follow established patterns: plain `def test_*`, `assert`, inline EventModel construction, unittest.mock for externals
- Test target: 5 tests for cross_referencer + 5 tests for error_loop_detector (10 total)

Module structure to create:
```
blackbox/pipeline/
  cross_referencer.py        NEW: Claim-evidence matching, scoring
  error_loop_detector.py     NEW: 3-pattern detection

tests/
  test_cross_referencer.py   NEW: 5 tests
  test_error_loop_detector.py NEW: 5 tests
```

GStack Role Check

No GStack roles needed — architecture is fully specified in SPEC.md and locked by prior plan-ceo-review + plan-eng-review sessions.

Implementation Order

1. `blackbox/pipeline/cross_referencer.py` — CrossReferencer class
2. `tests/test_cross_referencer.py` — 5 tests for cross-referencer
3. `blackbox/pipeline/error_loop_detector.py` — ErrorLoopDetector class
4. `tests/test_error_loop_detector.py` — 5 tests for error loop detector
5. Update `blackbox/pipeline/__init__.py` to export new classes

Cross-Referencer Design (from SPEC.md)

- Input: list[Claim] (from ClaimExtractor) + EvidenceSet (from EvidenceCollector)
- Output: LieScore (evidence_completeness + claim_veracity + risk_label)
- Side effect: Populates each Claim.evidence with list[EvidenceRef]

Matching logic:
- For each claim, scan relevant evidence by claim category:
  - test_result → command evidence (exit codes), git diff evidence
  - outcome → command evidence, file change evidence
  - scope → file change evidence, git diff evidence
  - approach → command evidence (which commands were run)
  - state → error evidence, command evidence
- Confidence assignment:
  - EXACT: exit code == 0 for "pass" claims, file diff matches claim text, error type matches claim text
  - SEMANTIC: evidence exists in the same category but no direct match (fallback)
  - MISSING: no evidence found in any relevant category

Scoring:
- evidence_completeness = evidenced_claims / total_claims (where evidenced = has at least one EvidenceRef)
- claim_veracity = matching_claims / evidenced_claims (where matching = at least one EXACT evidence ref)
- risk_label = compute_risk_label(completeness%, veracity%) from blackbox.models.score

Error Loop Detection Design (from SPEC.md)

Three pattern detectors:

1. RepeatedCommandDetector:
   - Scan ToolUseEvent events with tool_name="Bash"
   - Group by command string (from input dict)
   - Filter groups with 3+ occurrences where is_error=True
   - Report: command, count, time_range, stderr snippet from output

2. CircularEditDetector:
   - Scan ToolUseEvent events with tool_name in ("Edit", "Write")
   - Group by file path (from input dict)
   - For groups with 4+ edits, detect oscillation (same state appearing >1x)
   - Simple heuristic: track the pattern of paths; if the same path is re-edited after another path, it's circular
   - Report: file, edit_count, time_range

3. ErrorSpikeDetector:
   - Scan ErrorEvent events
   - Sliding window: 5+ ErrorEvents within 60 seconds
   - Report: error_type, count, time_range

Each detector is a method on ErrorLoopDetector. Results aggregated into list[ErrorLoop].

What to Commit

```
blackbox/pipeline/
  cross_referencer.py        CrossReferencer: claim-evidence matching + LieScore computation
  error_loop_detector.py     ErrorLoopDetector: 3-pattern detection (repeated command, circular edit, error spike)

tests/
  test_cross_referencer.py   5 tests (exact match, semantic match, contradictory, empty claims, empty evidence)
  test_error_loop_detector.py 5 tests (repeated command, circular edit, error spike, normal session, single failure)
```
