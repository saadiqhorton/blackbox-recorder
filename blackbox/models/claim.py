from enum import StrEnum

from pydantic import BaseModel


class ClaimCategory(StrEnum):
    TEST_RESULT = "test_result"
    OUTCOME = "outcome"
    SCOPE = "scope"
    APPROACH = "approach"
    STATE = "state"


class ConfidenceLevel(StrEnum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    MISSING = "missing"


class EvidenceRef(BaseModel):
    source: str
    type: str
    value: str
    confidence: ConfidenceLevel


class Claim(BaseModel):
    text: str
    category: ClaimCategory
    source_message_idx: int
    verifiable: bool = True
    evidence: list[EvidenceRef] = []
