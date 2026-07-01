from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from store import load_store, save_store

DECISIONS = ["A", "S", "V", "k_revizi"]


def normalize_decision(value: Any) -> str:
    v = str(value or "").strip().upper()
    if v in {"A", "S", "V"}:
        return v
    if v in {"K_REVIZI", "K REVIZI", "REVIEW", "REVIZE", "PŘEZKOUMAT", "PREZKOUMAT"}:
        return "k_revizi"
    return "k_revizi"


def _model_from_config(data: Dict[str, Any]) -> str:
    cfg = data.get("llm_config") or {}
    return cfg.get("model") or "neznamy_model"


def _normalize_item(item: Dict[str, Any], *, fallback_batch_id: str | None = None, store_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    llm = item.get("raw_llm_output") or item.get("llm_analysis") or {}
    if not isinstance(llm, dict):
        llm = {}

    batch_id = item.get("batch_id") or fallback_batch_id or ""
    decision = normalize_decision(
        item.get("recommended_decision")
        or item.get("llm_decision")
        or llm.get("recommendation")
        or llm.get("decision")
        or "k_revizi"
    )
    model = item.get("assessed_by_model") or item.get("llm_model") or llm.get("model")
    if not model and store_data:
        model = _model_from_config(store_data)
    model = model or "neznamy_model"

    ts = item.get("assessment_timestamp") or item.get("created_at") or item.get("timestamp")
    if not ts:
        ts = datetime.now().isoformat(timespec="seconds")

    document_id = item.get("document_id") or item.get("id") or item.get("record_id") or ""
    filename = item.get("filename") or item.get("path") or item.get("relative_path") or item.get("source_ref")
    title = item.get("title") or item.get("name") or filename or document_id

    score = item.get("weighted_total_score")
    if score is None:
        score = item.get("final_score") or item.get("score") or 0
    confidence = item.get("confidence")
    if confidence is None:
        confidence = llm.get("confidence", 0)

    return {
        "batch_id": batch_id,
        "document_id": document_id,
        "filename": filename,
        "title": title,
        "assessed_by_model": model,
        "model_provider": item.get("model_provider") or item.get("provider") or llm.get("provider") or "openai-compatible",
        "model_run_id": item.get("model_run_id") or item.get("llm_model_run_id") or item.get("run_id") or "bez_run_id",
        "assessment_timestamp": str(ts),
        "prompt_template_version": item.get("prompt_template_version") or "appraisal_v1",
        "ruleset_version": item.get("ruleset_version") or "rules_current",
        "weights_version": item.get("weights_version") or "weights_current",
        "detected_document_type": item.get("detected_document_type") or item.get("doc_type") or llm.get("document_type"),
        "detected_agenda": item.get("detected_agenda") or item.get("agenda") or llm.get("agenda"),
        "matched_retention_rules": item.get("matched_retention_rules") or [],
        "scores": item.get("scores") or {},
        "weighted_total_score": float(score or 0),
        "community_scores": item.get("community_scores") or [],
        "topic_scores": item.get("topic_scores") or [],
        "entities": item.get("entities") or {
            "persons": llm.get("persons") or [],
            "corporate_bodies": llm.get("organizations") or [],
            "places": llm.get("places") or [],
            "events": [],
            "dates": [],
        },
        "recommended_decision": decision,
        "confidence": float(confidence or 0),
        "explanation": item.get("explanation") or llm.get("reasoning") or llm.get("reason") or llm.get("summary") or "",
        "supporting_evidence": item.get("supporting_evidence") or [],
        "uncertainties": item.get("uncertainties") or ([llm.get("error")] if llm.get("error") else []),
        "conflicts": item.get("conflicts") or [],
        "human_review_required": bool(item.get("human_review_required") or llm.get("error") or decision == "k_revizi"),
        "raw_llm_output": item.get("raw_llm_output") or llm,
    }


def _items_from_batches(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for batch_id, batch in (data.get("batches") or {}).items():
        for rec in batch.get("records") or []:
            if not rec.get("llm_analysis"):
                continue
            row = dict(rec)
            row["batch_id"] = batch_id
            row["document_id"] = rec.get("id")
            row["recommended_decision"] = rec.get("llm_decision") or rec.get("llm_analysis", {}).get("recommendation")
            row["assessed_by_model"] = rec.get("llm_model") or _model_from_config(data)
            row["model_run_id"] = rec.get("llm_model_run_id") or batch.get("last_llm_analysis", {}).get("model_run_id") or "bez_run_id"
            row["assessment_timestamp"] = batch.get("last_llm_analysis", {}).get("finished_at") or batch.get("last_llm_analysis", {}).get("created_at")
            row["raw_llm_output"] = rec.get("llm_analysis")
            row["weighted_total_score"] = (rec.get("scoring") or {}).get("final_score", 0)
            out.append(_normalize_item(row, fallback_batch_id=batch_id, store_data=data))
    return out


class LlmAnalysisStore:
    def _load(self) -> Dict[str, Any]:
        data = load_store()
        data.setdefault("llm_assessments", [])
        return data

    def list_items(self, batch_id: Optional[str] = None, decision: Optional[str] = None, model: Optional[str] = None, model_run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load()
        stored = [_normalize_item(x, store_data=data) for x in (data.get("llm_assessments") or []) if isinstance(x, dict)]
        derived = _items_from_batches(data)

        # Sloučení podle document_id + model_run_id, aby se nezobrazovalo dvakrát.
        merged: Dict[str, Dict[str, Any]] = {}
        for x in derived + stored:
            key = f"{x.get('batch_id')}|{x.get('document_id')}|{x.get('model_run_id')}"
            merged[key] = x
        items = list(merged.values())

        if batch_id:
            items = [x for x in items if x.get("batch_id") == batch_id]
        if decision:
            d = normalize_decision(decision)
            items = [x for x in items if x.get("recommended_decision") == d]
        if model:
            items = [x for x in items if x.get("assessed_by_model") == model]
        if model_run_id:
            items = [x for x in items if x.get("model_run_id") == model_run_id]
        return items

    def add_batch(self, batch_id: str, items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        data = self._load()
        stored_items = [_normalize_item(dict(item), fallback_batch_id=batch_id, store_data=data) for item in items]
        data.setdefault("llm_assessments", []).extend(stored_items)
        save_store(data)
        return stored_items

    def replace_run(self, batch_id: str, model_run_id: str, items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        data = self._load()
        current = data.get("llm_assessments", [])
        data["llm_assessments"] = [x for x in current if not (x.get("batch_id") == batch_id and x.get("model_run_id") == model_run_id)]
        save_store(data)
        return self.add_batch(batch_id=batch_id, items=items)


def build_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    decision_counts = {d: 0 for d in DECISIONS}
    counts_by_model: Dict[str, Dict[str, int]] = {}
    for item in items:
        decision = normalize_decision(item.get("recommended_decision"))
        model = item.get("assessed_by_model") or "neznamy_model"
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        counts_by_model.setdefault(model, {d: 0 for d in DECISIONS})
        counts_by_model[model][decision] = counts_by_model[model].get(decision, 0) + 1
    return {"total": len(items), "decision_counts": decision_counts, "counts_by_model": counts_by_model}
