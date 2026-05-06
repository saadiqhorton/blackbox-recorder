from __future__ import annotations

from blackbox.models.claim import Claim, ClaimCategory, ConfidenceLevel
from blackbox.models.evidence import EvidenceSet
from blackbox.models.score import (
    ClaimVeracity,
    EvidenceCompleteness,
    LieScore,
    compute_risk_label,
)


class CrossReferencer:
    """Matches claims against evidence and produces LieScore.

    For each claim, scans relevant evidence by claim category, assigns confidence
    (EXACT / SEMANTIC / MISSING), populates claim.evidence, and returns an
    aggregate LieScore.
    """

    def cross_reference(self, claims: list[Claim], evidence: EvidenceSet) -> LieScore:
        """Match each claim against relevant evidence, populate claim.evidence, return LieScore."""
        if not claims:
            completeness = EvidenceCompleteness(evidenced_claims=0, total_claims=0)
            veracity = ClaimVeracity(matching_claims=0, evidenced_claims=0)
            return LieScore(
                evidence_completeness=completeness,
                claim_veracity=veracity,
                risk_label=compute_risk_label(completeness.percentage, veracity.percentage),
            )

        if evidence.total_count == 0:
            for c in claims:
                c.evidence = []
            completeness = EvidenceCompleteness(evidenced_claims=0, total_claims=len(claims))
            veracity = ClaimVeracity(matching_claims=0, evidenced_claims=0)
            return LieScore(
                evidence_completeness=completeness,
                claim_veracity=veracity,
                risk_label=compute_risk_label(completeness.percentage, veracity.percentage),
            )

        for claim in claims:
            refs = self._match(claim, evidence)
            claim.evidence = refs

        evidenced_claims = sum(1 for c in claims if len(c.evidence) > 0)
        matching_claims = sum(
            1 for c in claims
            if any(r.get("confidence") == ConfidenceLevel.EXACT for r in c.evidence)
        )

        completeness = EvidenceCompleteness(
            evidenced_claims=evidenced_claims,
            total_claims=len(claims),
        )
        veracity = ClaimVeracity(
            matching_claims=matching_claims,
            evidenced_claims=evidenced_claims,
        )
        risk = compute_risk_label(completeness.percentage, veracity.percentage)

        return LieScore(
            evidence_completeness=completeness,
            claim_veracity=veracity,
            risk_label=risk,
        )

    def _match(self, claim: Claim, evidence: EvidenceSet) -> list:
        """Scan relevant evidence by claim category and return EvidenceRef-compatible dicts."""
        refs: list = []
        category = claim.category

        if category == ClaimCategory.TEST_RESULT:
            refs.extend(self._match_commands(claim, evidence.commands))
            refs.extend(self._match_git_diffs(claim, evidence.git_diffs))

        elif category == ClaimCategory.OUTCOME:
            refs.extend(self._match_commands(claim, evidence.commands))
            refs.extend(self._match_file_changes(claim, evidence.file_changes))

        elif category == ClaimCategory.SCOPE:
            refs.extend(self._match_file_changes(claim, evidence.file_changes))
            refs.extend(self._match_git_diffs(claim, evidence.git_diffs))

        elif category == ClaimCategory.APPROACH:
            refs.extend(self._match_commands(claim, evidence.commands))

        elif category == ClaimCategory.STATE:
            refs.extend(self._match_errors(claim, evidence.errors))
            refs.extend(self._match_commands(claim, evidence.commands))

        if not refs:
            item = self._first_relevant(claim, evidence)
            if item is not None:
                refs.append({
                    "source": "evidence",
                    "type": category.value,
                    "value": "semantic",
                    "confidence": ConfidenceLevel.SEMANTIC,
                })

        return refs

    def _first_relevant(self, claim: Claim, evidence: EvidenceSet) -> object | None:
        """Return the first evidence item relevant to the claim's category, or None."""
        if claim.category == ClaimCategory.TEST_RESULT:
            items = evidence.commands + evidence.git_diffs
        elif claim.category == ClaimCategory.OUTCOME:
            items = evidence.commands + evidence.file_changes
        elif claim.category == ClaimCategory.SCOPE:
            items = evidence.file_changes + evidence.git_diffs
        elif claim.category == ClaimCategory.APPROACH:
            items = evidence.commands
        elif claim.category == ClaimCategory.STATE:
            items = evidence.errors + evidence.commands
        else:
            items = []
        return items[0] if items else None

    def _match_commands(self, claim: Claim, commands: list) -> list:
        """Match claim text against command evidence. Returns EXACT or SEMANTIC refs."""
        refs = []
        claim_lower = claim.text.lower()
        for cmd in commands:
            if not cmd.is_error and ("pass" in claim_lower or "succeed" in claim_lower):
                refs.append({
                    "source": f"command:{cmd.source_idx}",
                    "type": "command",
                    "value": cmd.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
            elif cmd.is_error and ("fail" in claim_lower or "error" in claim_lower):
                refs.append({
                    "source": f"command:{cmd.source_idx}",
                    "type": "command",
                    "value": cmd.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and commands:
            refs.append({
                "source": "commands",
                "type": "command",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs

    def _match_git_diffs(self, claim: Claim, diffs: list) -> list:
        """Match claim text against git diff evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for diff in diffs:
            if claim_lower in diff.value.lower():
                refs.append({
                    "source": f"git_diff:{diff.source_idx}",
                    "type": "git_diff",
                    "value": diff.value[:100],
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and diffs:
            refs.append({
                "source": "git_diffs",
                "type": "git_diff",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs

    def _match_file_changes(self, claim: Claim, changes: list) -> list:
        """Match claim text against file change evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for change in changes:
            if claim_lower in change.value.lower():
                refs.append({
                    "source": f"file_change:{change.source_idx}",
                    "type": "file_change",
                    "value": change.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and changes:
            refs.append({
                "source": "file_changes",
                "type": "file_change",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs

    def _match_errors(self, claim: Claim, errors: list) -> list:
        """Match claim text against error evidence."""
        refs = []
        claim_lower = claim.text.lower()
        for err in errors:
            if claim_lower in err.value.lower():
                refs.append({
                    "source": f"error:{err.source_idx}",
                    "type": "error",
                    "value": err.value,
                    "confidence": ConfidenceLevel.EXACT,
                })
        if not refs and errors:
            refs.append({
                "source": "errors",
                "type": "error",
                "value": "semantic",
                "confidence": ConfidenceLevel.SEMANTIC,
            })
        return refs
