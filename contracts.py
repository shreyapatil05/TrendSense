"""Typed contracts shared by persistence and evaluation layers."""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ObservationRecord:
    observation_id: str
    trend_id: str
    keyword: str
    category: str
    source: str
    platform: str
    geography: str
    language: str
    observed_at: str
    raw_signal: Dict[str, Any]
    normalized_signal: Dict[str, Any]
    source_reliability: float
    provenance: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ForecastRecord:
    forecast_id: str
    trend_id: str
    keyword: str
    forecast_timestamp: str
    forecast_horizon_days: int
    predicted_strength: Optional[float]
    predicted_direction: str
    predicted_lifecycle: str
    forecast_confidence: float
    decision: str
    evidence_snapshot: Dict[str, Any]
    sources_used: List[str]
    system_version: str
    configuration_version: str
    forecast_method: str = "rule_based_fallback"
    predicted_probabilities: Dict[str, float] = field(default_factory=dict)
    model_version: Optional[str] = None
    current_interest: Optional[float] = None
    semantic_agreement_score: Optional[float] = None
    actual_outcome: Optional[str] = None
    actual_strength: Optional[float] = None
    actual_lifecycle: Optional[str] = None
    actual_direction: Optional[str] = None
    forecast_error: Optional[float] = None
    evaluation_status: str = "PENDING"

    def to_dict(self):
        return asdict(self)
