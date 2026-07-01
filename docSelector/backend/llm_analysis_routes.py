from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Any, Dict, List

from llm_analysis_service import LlmAnalysisStore, build_summary

router = APIRouter(prefix="/api/llm-analysis", tags=["LLM analýzy"])
store = LlmAnalysisStore()

class LlmAssessmentBatchIn(BaseModel):
    batch_id: str
    items: List[Dict[str, Any]]

@router.get("")
def list_llm_assessments(
    batch_id: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    model_run_id: Optional[str] = Query(default=None),
):
    items = store.list_items(batch_id=batch_id, decision=decision, model=model, model_run_id=model_run_id)
    return {
        "filters": {"batch_id": batch_id, "decision": decision, "model": model, "model_run_id": model_run_id},
        "summary": build_summary(items),
        "items": items,
    }

@router.post("")
def save_llm_assessment_batch(payload: LlmAssessmentBatchIn):
    store.add_batch(batch_id=payload.batch_id, items=payload.items)
    items = store.list_items(batch_id=payload.batch_id)
    return {"filters": {"batch_id": payload.batch_id}, "summary": build_summary(items), "items": items}

@router.put("/replace-run")
def replace_llm_assessment_run(payload: LlmAssessmentBatchIn):
    if not payload.items:
        return {"filters": {"batch_id": payload.batch_id}, "summary": build_summary([]), "items": []}
    model_run_id = payload.items[0].get("model_run_id") or "bez_run_id"
    store.replace_run(batch_id=payload.batch_id, model_run_id=model_run_id, items=payload.items)
    items = store.list_items(batch_id=payload.batch_id, model_run_id=model_run_id)
    return {"filters": {"batch_id": payload.batch_id, "model_run_id": model_run_id}, "summary": build_summary(items), "items": items}
