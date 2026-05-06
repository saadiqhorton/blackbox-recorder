"""Pipeline stages for claim extraction, evidence collection, cross-referencing, and error loop detection."""
from blackbox.pipeline.claim_extractor import ClaimExtractor
from blackbox.pipeline.cross_referencer import CrossReferencer
from blackbox.pipeline.error_loop_detector import ErrorLoopDetector
from blackbox.pipeline.evidence_collector import EvidenceCollector

__all__ = [
    "ClaimExtractor",
    "EvidenceCollector",
    "CrossReferencer",
    "ErrorLoopDetector",
]
