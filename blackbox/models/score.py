from enum import StrEnum

from pydantic import BaseModel, model_validator


class RiskLabel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceCompleteness(BaseModel):
    evidenced_claims: int
    total_claims: int

    @model_validator(mode='after')
    def cap_evidenced(self):
        self.evidenced_claims = min(self.evidenced_claims, self.total_claims)
        return self

    @property
    def percentage(self) -> float:
        if self.total_claims == 0:
            return 0.0
        return (self.evidenced_claims / self.total_claims) * 100


class ClaimVeracity(BaseModel):
    matching_claims: int
    evidenced_claims: int

    @model_validator(mode='after')
    def cap_matching(self):
        self.matching_claims = min(self.matching_claims, self.evidenced_claims)
        return self

    @property
    def percentage(self) -> float:
        if self.evidenced_claims == 0:
            return 0.0
        return (self.matching_claims / self.evidenced_claims) * 100


class LieScore(BaseModel):
    evidence_completeness: EvidenceCompleteness
    claim_veracity: ClaimVeracity
    risk_label: RiskLabel


def compute_risk_label(completeness: float, veracity: float) -> RiskLabel:
    if completeness >= 80 and veracity >= 80:
        return RiskLabel.LOW
    if completeness >= 50 and veracity >= 50:
        return RiskLabel.MEDIUM
    return RiskLabel.HIGH
