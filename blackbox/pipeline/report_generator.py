from pathlib import Path
from typing import Optional

from blackbox.models.score import LieScore, RiskLabel
from blackbox.models.claim import Claim, ConfidenceLevel
from blackbox.models.error_loop import ErrorLoop


class ReportGenerator:
    """Renders incident reports in Markdown and JSON formats."""

    RISK_MESSAGES = {
        RiskLabel.LOW: "looks good — safe to merge",
        RiskLabel.MEDIUM: "review before accepting",
        RiskLabel.HIGH: "do not merge — investigate",
    }

    def generate(
        self,
        session_info: dict,
        score: LieScore,
        claims: list[Claim],
        error_loops: list[ErrorLoop],
        report_path: Optional[Path] = None,
    ) -> dict:
        """Generate markdown and JSON reports.

        Args:
            session_info: Dict with session_id, agent_type, task, duration, analyzed_at.
            score: LieScore with evidence_completeness, claim_veracity, risk_label.
            claims: List of Claim objects.
            error_loops: List of ErrorLoop objects.
            report_path: Optional directory path to write report files.

        Returns:
            Dict with "markdown" (str) and "json" (dict) keys.
        """
        md = self._render_markdown(session_info, score, claims, error_loops)
        js = self._render_json(session_info, score, claims, error_loops)
        result = {"markdown": md, "json": js}

        if report_path is not None:
            import json

            report_path.mkdir(parents=True, exist_ok=True)
            (report_path / "incident_report.md").write_text(md)
            (report_path / "incident_report.json").write_text(
                json.dumps(js, indent=2)
            )

        return result

    def _render_markdown(
        self,
        session_info: dict,
        score: LieScore,
        claims: list[Claim],
        error_loops: list[ErrorLoop],
    ) -> str:
        """Render the report as formatted Markdown."""
        ec = score.evidence_completeness
        cv = score.claim_veracity
        risk = score.risk_label

        missing_claims = ec.total_claims - ec.evidenced_claims
        mismatched_claims = cv.evidenced_claims - cv.matching_claims

        comp_pct = int(ec.percentage)
        comp_icon = _score_icon(comp_pct)
        ver_pct = int(cv.percentage)
        ver_icon = _score_icon(ver_pct)

        lines = [
            "BLACK BOX RECORDER — VERIFICATION REPORT",
            "═══════════════════════════════════════════════════════════",
            'SESSION:     {session_id} | {agent_type} | "{task}"'.format(
                session_id=session_info.get("session_id", "?"),
                agent_type=session_info.get("agent_type", "?"),
                task=session_info.get("task", "?"),
            ),
            "DURATION:    {}".format(session_info.get("duration", "?")),
            "ANALYZED:    {}".format(session_info.get("analyzed_at", "?")),
            "",
            "EVIDENCE COMPLETENESS: {}% {}".format(comp_pct, comp_icon),
            "  {}/{} claims have supporting evidence".format(
                ec.evidenced_claims, ec.total_claims
            ),
        ]
        if missing_claims > 0:
            plural = "s" if missing_claims > 1 else ""
            lines.append("  {} claim{}: no evidence found".format(missing_claims, plural))

        lines.append("")
        lines.append("CLAIM VERACITY: {}% {}".format(ver_pct, ver_icon))
        lines.append("  {}/{} evidenced claims match the evidence".format(
            cv.matching_claims, cv.evidenced_claims
        ))
        if mismatched_claims > 0:
            plural = "s" if mismatched_claims > 1 else ""
            lines.append("  {} claim{}: evidence contradicts the claim".format(
                mismatched_claims, plural
            ))

        lines.append("")
        lines.append("CLAIMS:")
        for claim in claims:
            icon, conf, pct, evidence_text = _format_claim_line(claim)
            lines.append("  {} {:<30} ({}, {:>3})  {}".format(
                icon, claim.text[:30], conf, pct, evidence_text
            ))

        if error_loops:
            lines.append("")
            lines.append("ERROR LOOPS:")
            for loop in error_loops:
                details = loop.details or loop.pattern.value
                lines.append("  {} {} {}x      ({})".format(
                    "⚠️", loop.description, loop.count, details
                ))

        lines.append("")
        risk_msg = self.RISK_MESSAGES.get(risk, "unknown risk")
        lines.append("RISK: {} — {}".format(risk.upper(), risk_msg))

        return "\n".join(lines)

    def _render_json(
        self,
        session_info: dict,
        score: LieScore,
        claims: list[Claim],
        error_loops: list[ErrorLoop],
    ) -> dict:
        """Render the report as a JSON-serializable dict."""
        ec = score.evidence_completeness
        cv = score.claim_veracity
        risk = score.risk_label

        return {
            "session": {
                "id": session_info.get("session_id", ""),
                "agent": session_info.get("agent_type", ""),
                "task": session_info.get("task", ""),
                "duration": session_info.get("duration", ""),
                "analyzed_at": session_info.get("analyzed_at", ""),
            },
            "scores": {
                "evidence_completeness": {
                    "percentage": int(ec.percentage),
                    "evidenced_claims": ec.evidenced_claims,
                    "total_claims": ec.total_claims,
                },
                "claim_veracity": {
                    "percentage": int(cv.percentage),
                    "matching_claims": cv.matching_claims,
                    "evidenced_claims": cv.evidenced_claims,
                },
                "risk": {
                    "label": risk.upper(),
                    "message": self.RISK_MESSAGES.get(risk, "unknown risk"),
                },
            },
            "claims": [
                {
                    "text": c.text,
                    "category": c.category.value,
                    "confidence": self._confidence_for_claim(c),
                    "evidence": [
                        {
                            "source": e.source,
                            "type": e.type,
                            "value": e.value,
                            "confidence": e.confidence.value,
                        }
                        for e in c.evidence
                    ],
                }
                for c in claims
            ],
            "error_loops": [
                {
                    "pattern": loop.pattern.value,
                    "description": loop.description,
                    "count": loop.count,
                    "details": loop.details,
                }
                for loop in error_loops
            ],
        }

    def _confidence_for_claim(self, claim: Claim) -> str:
        """Return 'exact', 'semantic', or 'missing' based on evidence confidence."""
        if not claim.evidence:
            return "missing"
        has_exact = any(e.confidence == ConfidenceLevel.EXACT for e in claim.evidence)
        if has_exact:
            return "exact"
        has_semantic = any(
            e.confidence == ConfidenceLevel.SEMANTIC for e in claim.evidence
        )
        if has_semantic:
            return "semantic"
        return "missing"


def _score_icon(pct: int) -> str:
    """Return icon for a score percentage."""
    if pct >= 80:
        return "✅"
    return "⚠️"


def _format_claim_line(claim: Claim):
    """Format a single claim line for markdown output.

    Returns (icon, confidence_str, percentage_str, evidence_text).
    """
    if not claim.evidence:
        return "❌", "missing", "0%", "no evidence"

    exact_count = sum(
        1 for e in claim.evidence if e.confidence == ConfidenceLevel.EXACT
    )
    total = len(claim.evidence)
    pct = int(exact_count / total * 100) if total > 0 else 0

    has_missing = any(
        e.confidence == ConfidenceLevel.MISSING for e in claim.evidence
    )
    has_semantic = any(
        e.confidence == ConfidenceLevel.SEMANTIC for e in claim.evidence
    )
    has_exact = exact_count > 0

    if has_missing:
        icon = "❌"
        conf = "missing"
    elif has_semantic and not has_exact:
        icon = "⚠️"
        conf = "semantic"
    else:
        icon = "✅"
        conf = "exact"

    evidence_text = claim.evidence[0].value or claim.evidence[0].source
    return icon, conf, "{}%".format(pct), evidence_text
