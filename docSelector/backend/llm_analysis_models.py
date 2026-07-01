from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


Decision = Literal["A", "S", "V", "k_revizi"]


class LlmScoreSet(BaseModel):
    legal_evidential: float = 0
    administrative: float = 0
    historical_information: float = 0
    uniqueness: float = 0
    entities_events: float = 0
    communities: float = 0
    topics: float = 0
    context_loss: float = 0
    metadata_quality: float = 0
    duplication: float = 0


class CommunityScore(BaseModel):
    community_id: str
    score: float = 0
    reason: str = ""


class TopicScore(BaseModel):
    topic_id: str
    score: float = 0
    reason: str = ""


class SupportingEvidence(BaseModel):
    field: str = ""
    value: Any = ""
    reason: str = ""


class LlmEntities(BaseModel):
    persons: List[str] = Field(default_factory=list)
    corporate_bodies: List[str] = Field(default_factory=list)
    places: List[str] = Field(default_factory=list)
    events: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)


class LlmAssessmentItem(BaseModel):
    """
    Jeden výsledek LLM posouzení pro dokument nebo entitu.

    Důležité:
    - model je uložen přímo u každého posuzovaného záznamu,
      nejen na úrovni dávky;
    - model_run_id umožňuje srovnat opakované běhy stejné dávky.
    """

    document_id: str
    filename: Optional[str] = None
    title: Optional[str] = None

    # audit modelu pro KAŽDÝ záznam
    assessed_by_model: str
    model_provider: Optional[str] = None
    model_run_id: str
    assessment_timestamp: datetime
    prompt_template_version: Optional[str] = None
    ruleset_version: Optional[str] = None
    weights_version: Optional[str] = None

    detected_document_type: Optional[str] = None
    detected_agenda: Optional[str] = None
    matched_retention_rules: List[str] = Field(default_factory=list)

    scores: LlmScoreSet = Field(default_factory=LlmScoreSet)
    weighted_total_score: float = 0
    community_scores: List[CommunityScore] = Field(default_factory=list)
    topic_scores: List[TopicScore] = Field(default_factory=list)
    entities: LlmEntities = Field(default_factory=LlmEntities)

    recommended_decision: Decision
    confidence: float = 0
    explanation: str = ""
    supporting_evidence: List[SupportingEvidence] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    human_review_required: bool = False

    raw_llm_output: Optional[Dict[str, Any]] = None


class LlmAssessmentBatchIn(BaseModel):
    batch_id: str
    items: List[LlmAssessmentItem]


class LlmAssessmentFilters(BaseModel):
    batch_id: Optional[str] = None
    decision: Optional[Decision] = None
    model: Optional[str] = None
    model_run_id: Optional[str] = None


class LlmAssessmentSummary(BaseModel):
    total: int
    decision_counts: Dict[str, int]
    counts_by_model: Dict[str, Dict[str, int]]


class LlmAssessmentListResponse(BaseModel):
    filters: Dict[str, Any]
    summary: LlmAssessmentSummary
    items: List[LlmAssessmentItem]
