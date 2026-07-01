from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from datetime import datetime
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from analysis_algorithms import analyze_record, extract_text, technical_metadata
from export_utils import export_json, export_results_csv, sort_files
from llm_client import llm_analyze, test_llm_connection
from llm_analysis_routes import router as llm_analysis_router
from scoring import score_record
from store import delete_item, load_store, new_id, reset_store, save_store, upsert_item

app = FastAPI(title="DocSelector Phase 1 API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(llm_analysis_router)


class FolderScanRequest(BaseModel):
    path: str
    extract_text_layer: bool = True
    max_files: int = 500


class ScoreRequest(BaseModel):
    mode: str = "algorithmic"  # algorithmic | llm | compare


class SortRequest(BaseModel):
    output_root: str
    mode: str = "copy"  # copy | move


class LLMAnalyzeRequest(BaseModel):
    max_records: int = 20
    only_without_llm: bool = True
    overwrite: bool = False
    full_context: bool = False





def _event(data: dict[str, Any], event_type: str, *, batch_id: str | None = None, count: int = 0, started: float | None = None, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    elapsed_ms = int((time.perf_counter() - started) * 1000) if started else None
    row = {"id": new_id("evt"), "type": event_type, "batch_id": batch_id, "count": count, "elapsed_ms": elapsed_ms, "records_per_sec": round(count / (elapsed_ms / 1000), 3) if elapsed_ms and elapsed_ms > 0 else None, "detail": detail or {}, "created_at": datetime.now().isoformat(timespec="seconds")}
    data.setdefault("events", []).append(row)
    return row


def _decision_for_llm(value: Any) -> str:
    d = str(value or "V").strip().upper()
    return d if d in {"A", "S", "V"} else "k_revizi"


def _llm_assessment_item(batch_id: str, rec: dict[str, Any], llm: dict[str, Any], cfg: dict[str, Any], model_run_id: str) -> dict[str, Any]:
    analysis = rec.get("analysis") or {}
    scoring = rec.get("scoring") or {}
    comps = scoring.get("components") or {}
    return {
        "batch_id": batch_id,
        "document_id": rec.get("id"),
        "filename": rec.get("filename") or rec.get("path") or rec.get("relative_path"),
        "title": rec.get("title"),
        "assessed_by_model": cfg.get("model") or llm.get("model") or "neznamy_model",
        "model_provider": cfg.get("provider") or cfg.get("base_url") or "openai-compatible",
        "model_run_id": model_run_id,
        "assessment_timestamp": datetime.now().isoformat(timespec="seconds"),
        "prompt_template_version": "docselector_appraisal_v1",
        "ruleset_version": "store_retention_rules_current",
        "weights_version": "store_decision_profile_current",
        "detected_document_type": analysis.get("document_type") or rec.get("doc_type"),
        "detected_agenda": rec.get("agenda") or "",
        "matched_retention_rules": [x.get("id") for x in scoring.get("matched_rules", []) if isinstance(x, dict)],
        "scores": {"historical_information": float(comps.get("community_matrix_score", 0) or 0), "metadata_quality": float(comps.get("metadata_quality_score", 0) or 0), "communities": float(comps.get("community_matrix_score", 0) or 0), "topics": float(len(llm.get("detected_topics") or []))},
        "weighted_total_score": float(scoring.get("final_score", 0) or 0),
        "community_scores": [],
        "topic_scores": [{"topic_id": t, "score": 1, "reason": "LLM detekce"} for t in (llm.get("detected_topics") or [])],
        "entities": {"persons": llm.get("persons") or [], "corporate_bodies": llm.get("organizations") or [], "places": llm.get("places") or [], "events": [], "dates": list((llm.get("time_range") or {}).values()) if isinstance(llm.get("time_range"), dict) else []},
        "recommended_decision": _decision_for_llm(llm.get("recommendation") or rec.get("llm_decision") or "V"),
        "confidence": float(llm.get("confidence", 0.5) or 0.5),
        "explanation": llm.get("reasoning") or llm.get("reason") or llm.get("summary") or "",
        "supporting_evidence": [], "uncertainties": [llm.get("error")] if llm.get("error") else [], "conflicts": [],
        "human_review_required": bool(llm.get("error") or _decision_for_llm(llm.get("recommendation")) == "k_revizi"),
        "raw_llm_output": llm,
    }

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat(timespec="seconds")}


@app.get("/")
def root():
    return {"app": "DocSelector Phase 1", "status": "running", "docs": "http://localhost:8000/docs", "frontend": "http://localhost:3000"}


@app.get("/events")
def list_events(limit: int = 200):
    data = load_store()
    return list(reversed(data.get("events", [])))[0:limit]


@app.post("/reset")
def reset():
    return reset_store()


@app.get("/store")
def get_store():
    return load_store()


@app.get("/config/project")
def get_project():
    return load_store()["project"]


@app.put("/config/project")
def put_project(project: dict[str, Any]):
    data = load_store(); data["project"] = project; save_store(data); return project


@app.get("/config/decision-profile")
def get_profile():
    return load_store()["decision_profile"]


@app.put("/config/decision-profile")
def put_profile(profile: dict[str, Any]):
    data = load_store(); data["decision_profile"] = profile; save_store(data); return profile


@app.get("/config/llm")
def get_llm_config():
    cfg = dict(load_store()["llm_config"])
    if cfg.get("api_key"):
        cfg["api_key"] = cfg["api_key"][:4] + "****"
    return cfg


@app.put("/config/llm")
def put_llm_config(config: dict[str, Any]):
    data = load_store(); data["llm_config"].update(config); save_store(data)
    out = dict(data["llm_config"]); out["api_key"] = "****" if out.get("api_key") else ""
    return out


COLLECTION_PREFIX = {
    "community_groups": "cg", "communities": "comm", "topic_groups": "tg", "topics": "topic", "retention_rules": "ret"
}


@app.get("/{collection}")
def list_collection(collection: str):
    if collection not in COLLECTION_PREFIX:
        raise HTTPException(404, "Neznámá kolekce")
    return load_store().get(collection, [])


@app.post("/{collection}")
def upsert_collection(collection: str, item: dict[str, Any]):
    if collection not in COLLECTION_PREFIX:
        raise HTTPException(404, "Neznámá kolekce")
    data = load_store(); saved = upsert_item(data, collection, item, COLLECTION_PREFIX[collection]); save_store(data); return saved


@app.delete("/{collection}/{item_id}")
def delete_collection(collection: str, item_id: str):
    if collection not in COLLECTION_PREFIX:
        raise HTTPException(404, "Neznámá kolekce")
    data = load_store(); ok = delete_item(data, collection, item_id); save_store(data); return {"deleted": ok}




@app.get("/llm/status")
def llm_status():
    data = load_store()
    cfg = dict(data.get("llm_config", {}))
    has_key = bool(cfg.get("api_key"))
    cfg.pop("api_key", None)
    return {
        "config": cfg,
        "has_api_key": has_key,
        "last_test": data.get("llm_last_test"),
    }


@app.post("/llm/test")
async def llm_test():
    data = load_store()
    result = await test_llm_connection(data.get("llm_config", {}))
    data["llm_last_test"] = result
    if result.get("ok"):
        data.setdefault("llm_config", {})["enabled"] = True
    save_store(data)
    return result


@app.get("/matrix/full")
def matrix_full():
    data = load_store()
    return {k: data[k] for k in ["community_groups", "communities", "topic_groups", "topics", "scores"]}


@app.put("/matrix/score")
def set_matrix_score(payload: dict[str, Any]):
    data = load_store()
    cid, tid = payload.get("community_id"), payload.get("topic_id")
    if not cid or not tid:
        raise HTTPException(400, "community_id a topic_id jsou povinné")
    data.setdefault("scores", {})[f"{cid}|{tid}"] = int(payload.get("value", 0))
    save_store(data)
    return {"key": f"{cid}|{tid}", "value": data["scores"][f"{cid}|{tid}"]}


@app.get("/matrix/export")
def matrix_export():
    data = load_store()
    return {"export_type": "docselector_matrix_config", "exported_at": datetime.now().isoformat(timespec="seconds"), "community_groups": data.get("community_groups", []), "communities": data.get("communities", []), "topic_groups": data.get("topic_groups", []), "topics": data.get("topics", []), "scores": data.get("scores", {}), "decision_profile": data.get("decision_profile", {})}


@app.post("/matrix/import")
def matrix_import(payload: dict[str, Any]):
    data = load_store(); imported = {"communities": 0, "topics": 0, "scores": 0}
    for item in payload.get("communities", []): upsert_item(data, "communities", item, "comm"); imported["communities"] += 1
    for item in payload.get("topics", []): upsert_item(data, "topics", item, "topic"); imported["topics"] += 1
    if isinstance(payload.get("scores"), dict): data.setdefault("scores", {}).update({str(k): int(v) for k, v in payload["scores"].items()}); imported["scores"] += len(payload["scores"])
    if isinstance(payload.get("decision_profile"), dict): data["decision_profile"] = payload["decision_profile"]
    _event(data, "matrix_import", count=sum(imported.values()), detail=imported); save_store(data); return {"ok": True, "imported": imported}


@app.get("/retention_rules/export")
def retention_rules_export():
    data = load_store(); return {"export_type": "docselector_retention_rules", "exported_at": datetime.now().isoformat(timespec="seconds"), "retention_rules": data.get("retention_rules", [])}


@app.post("/retention_rules/import")
def retention_rules_import(payload: Any):
    data = load_store(); rules = payload.get("retention_rules", payload) if isinstance(payload, dict) else payload
    if not isinstance(rules, list): raise HTTPException(400, "Čekám seznam pravidel nebo objekt {retention_rules:[...]}")
    imported = 0
    for row in rules:
        if isinstance(row, str):
            parts = [p.strip() for p in row.split(",")]
            row = {"doc_type": parts[0] if len(parts)>0 else "", "retention_mark": parts[1] if len(parts)>1 else "V", "retention_years": parts[2] if len(parts)>2 else ""}
        item = dict(row)
        if not item.get("id"): item["id"] = new_id("ret")
        item.setdefault("originator_type", "*"); item.setdefault("agenda", "*"); item.setdefault("purpose", "*"); item.setdefault("decision", item.get("retention_mark", "V")); item.setdefault("active", True)
        upsert_item(data, "retention_rules", item, "ret"); imported += 1
    _event(data, "retention_rules_import", count=imported); save_store(data); return {"ok": True, "imported": imported}



def _norm_header(value: Any) -> str:
    """Normalizuje názvy sloupců: diakritika pryč, malá písmena, jen alfanumerika."""
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _detect_header_row(df: pd.DataFrame) -> int:
    """
    Najde řádek s hlavičkou. Umí běžné CSV i protokoly, kde jsou před tabulkou poznámky.
    Hledá signály typu: Spis. znak, Obsah/Název, Sk. znak, Rozhodnutí.
    """
    expected = {
        "title", "nazev", "obsah", "obsah_nazev_typoveho_spisu_a_soucasti",
        "spis_znak", "spisovy_znak", "spis_dil_dokument", "evid_cislo",
        "sk_znak", "sk_lhuta", "rozhodnuti", "podoba", "ulozeno"
    }
    best_idx, best_score = 0, -1
    for idx in range(min(len(df), 30)):
        vals = [_norm_header(v) for v in df.iloc[idx].tolist()]
        vals = [v for v in vals if v]
        score = 0
        for v in vals:
            if v in expected:
                score += 3
            if "nazev" in v or "obsah" in v:
                score += 2
            if "rozhodnuti" in v or v in {"sk_znak", "sk_lhuta"}:
                score += 2
            if "spis" in v or "evid" in v:
                score += 1
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx


def read_table_upload(file: UploadFile) -> list[dict[str, Any]]:
    """
    Načte CSV/XLSX. Podporuje i český „seznam k protokolu výběru“, kde hlavička
    není v prvním řádku. Výstupem jsou řádky s původními názvy sloupců.
    """
    raw = file.file.read()
    name = (file.filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        raw_df = pd.read_excel(io.BytesIO(raw), header=None, dtype=str)
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        sep = ";" if text.splitlines() and text.splitlines()[0].count(";") >= text.splitlines()[0].count(",") else ","
        raw_df = pd.read_csv(io.StringIO(text), header=None, sep=sep, dtype=str)

    raw_df = raw_df.fillna("")
    header_idx = _detect_header_row(raw_df)
    headers = [str(x).strip() if str(x).strip() else f"column_{i+1}" for i, x in enumerate(raw_df.iloc[header_idx].tolist())]
    df = raw_df.iloc[header_idx + 1:].copy()
    df.columns = headers
    df = df.fillna("")
    # pryč úplně prázdné řádky
    df = df[df.apply(lambda r: any(str(v).strip() for v in r.tolist()), axis=1)]
    return df.to_dict(orient="records")


def _pick(row_lower: dict[str, Any], aliases: list[str]) -> str:
    for a in aliases:
        an = _norm_header(a)
        for k, v in row_lower.items():
            if k == an or k.endswith("_" + an) or an.endswith("_" + k):
                if v not in (None, ""):
                    return str(v).strip()
    return ""


def _split_year_range(value: str) -> tuple[str, str]:
    years = re.findall(r"\b(18\d{2}|19\d{2}|20[0-3]\d)\b", str(value or ""))
    if not years:
        return "", ""
    return min(years), max(years)


def normalize_import_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizace obecného CSV i českého XLSX seznamu k protokolu výběru.
    Existující sloupec Rozhodnutí ukládáme jako reference_decision, nikoli jako nové rozhodnutí systému.
    """
    lower = {_norm_header(k): v for k, v in row.items()}
    out = {"id": new_id("doc"), "raw_row": row}

    out["spisovy_znak"] = _pick(lower, ["Spis. znak", "Spis znak", "spisovy_znak", "spisový znak"])
    out["record_ref"] = _pick(lower, ["Spis/Díl/Dokument", "spis_dil_dokument", "spis", "dil", "dokument"])
    out["evidence_number"] = _pick(lower, ["Evid. číslo", "Evid cislo", "evidencni_cislo", "evidenční číslo"])

    title = _pick(lower, [
        "Obsah / Název typového spisu a součásti", "Obsah", "Název", "Nazev", "title", "name"
    ])
    path = _pick(lower, ["path", "cesta", "file", "soubor"])
    description = _pick(lower, ["description", "popis", "poznámka", "poznamka", "Pozn. archiváře"])
    if title:
        out["title"] = title
    elif path:
        out["title"] = Path(path).name
    elif out.get("record_ref"):
        out["title"] = out["record_ref"]
    else:
        out["title"] = "bez_nazvu"
    if path:
        out["path"] = path
    if description:
        out["description"] = description

    time_value = _pick(lower, ["Časový rozsah vč. vyřízení", "casovy rozsah vc vyrizeni", "časový rozsah", "date", "datum"])
    date_from = _pick(lower, ["date_from", "od", "rok_od"])
    date_to = _pick(lower, ["date_to", "do", "rok_do"])
    if not (date_from or date_to):
        date_from, date_to = _split_year_range(time_value)
    if date_from:
        out["date_from"] = date_from
    if date_to:
        out["date_to"] = date_to
    if time_value:
        out["time_original"] = time_value

    # spisový/skartační údaj
    retention_mark = _pick(lower, ["Sk. znak", "Sk znak", "skartacni_znak", "skartační znak", "retention_mark"])
    retention_years = _pick(lower, ["Sk. lhůta", "Sk lhuta", "skartacni_lhuta", "skartační lhůta", "retention_years"])
    if retention_mark:
        out["retention_mark"] = retention_mark.upper()
    if retention_years:
        out["retention_years"] = retention_years

    out["accessibility"] = _pick(lower, ["Přístupnost", "Pristupnost", "accessibility"])
    out["form"] = _pick(lower, ["Podoba", "form", "podoba"])
    out["storage"] = _pick(lower, ["Uloženo", "Ulozeno", "storage"])
    out["place"] = _pick(lower, ["place", "místo", "misto"])
    out["agenda"] = _pick(lower, ["agenda"])
    out["doc_type"] = _pick(lower, ["doc_type", "typ", "typ_dokumentu"])

    ref_dec = _pick(lower, ["Rozhodnutí", "Rozhodnuti", "decision", "reference_decision"])
    if ref_dec:
        out["reference_decision"] = ref_dec.upper()
        out["source_decision"] = ref_dec.upper()

    # Pro metadata-only analýzu spojíme důležitá pole do popisu, aby šlo extrahovat téma/čas/místo.
    text_parts = [
        out.get("title", ""), out.get("description", ""), out.get("record_ref", ""),
        out.get("evidence_number", ""), out.get("spisovy_znak", ""), out.get("storage", ""),
        out.get("form", ""), out.get("retention_mark", ""), out.get("time_original", "")
    ]
    out["metadata_text"] = "\n".join(str(x) for x in text_parts if x)
    return {k: v for k, v in out.items() if v not in (None, "")}


@app.post("/import/metadata")
def import_metadata(file: UploadFile = File(...)):
    data = load_store()
    rows = read_table_upload(file)
    records = []
    for row in rows:
        rec = normalize_import_row(row)
        rec["input_mode"] = "metadata"
        rec["analysis"] = analyze_record(rec, data.get("topics", []))
        records.append(rec)
    batch_id = new_id("batch")
    batch = {"id": batch_id, "name": file.filename, "input_mode": "metadata", "created": datetime.now().isoformat(timespec="seconds"), "records": records, "project_snapshot": data.get("project"), "config_snapshot": {"decision_profile": data.get("decision_profile")}}
    data.setdefault("batches", {})[batch_id] = batch
    save_store(data)
    return batch


@app.post("/scan/folder")
def scan_folder(req: FolderScanRequest):
    root = Path(req.path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(404, f"Složka neexistuje: {root}")
    data = load_store()
    records = []
    for p in sorted(root.rglob("*")):
        if len(records) >= req.max_files:
            break
        if not p.is_file() or p.name.startswith("."):
            continue
        rec = {"id": new_id("doc"), **technical_metadata(str(p), str(root)), "input_mode": "folder"}
        if req.extract_text_layer:
            rec["text"] = extract_text(str(p))
        rec["analysis"] = analyze_record(rec, data.get("topics", []))
        rec["doc_type"] = rec["analysis"].get("document_type")
        records.append(rec)
    batch_id = new_id("batch")
    batch = {"id": batch_id, "name": root.name, "source_root": str(root), "input_mode": "folder", "created": datetime.now().isoformat(timespec="seconds"), "records": records, "project_snapshot": data.get("project"), "config_snapshot": {"decision_profile": data.get("decision_profile")}}
    data.setdefault("batches", {})[batch_id] = batch
    save_store(data)
    return batch


@app.get("/batches")
def list_batches():
    batches = load_store().get("batches", {})
    return [{"id": b["id"], "name": b.get("name"), "created": b.get("created"), "input_mode": b.get("input_mode"), "count": len(b.get("records", []))} for b in batches.values()]


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    batch = load_store().get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    return batch




def _wildcard_match(rule_value: Any, actual: Any) -> bool:
    rv = str(rule_value or "*").strip().lower()
    av = str(actual or "").strip().lower()
    return rv in {"", "*", "vše", "all"} or rv == av or (rv and rv in av)


def _relevant_retention_rules(data: dict[str, Any], rec: dict[str, Any], project: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    actual = {
        "doc_type": rec.get("doc_type") or (rec.get("analysis") or {}).get("document_type") or "",
        "originator_type": rec.get("originator_type") or project.get("originator_type") or "",
        "agenda": rec.get("agenda") or project.get("agenda") or "",
        "purpose": rec.get("purpose") or project.get("purpose") or project.get("archive_purpose") or "",
    }
    matched = []
    for rule in data.get("retention_rules", []):
        if not rule.get("active", True):
            continue
        checks = [
            _wildcard_match(rule.get("doc_type"), actual["doc_type"]),
            _wildcard_match(rule.get("originator_type"), actual["originator_type"]),
            _wildcard_match(rule.get("agenda"), actual["agenda"]),
            _wildcard_match(rule.get("purpose"), actual["purpose"]),
        ]
        if all(checks):
            matched.append(rule)
    matched.sort(key=lambda r: int(r.get("priority", 0) or 0), reverse=True)
    return matched[:limit]


def _compact_matrix_for_llm(data: dict[str, Any]) -> dict[str, Any]:
    communities = [
        {"id": c.get("id"), "name": c.get("name"), "weight": c.get("weight", 1), "type": c.get("type"), "active": c.get("active", True)}
        for c in data.get("communities", []) if c.get("active", True)
    ]
    topics = [
        {"id": t.get("id"), "name": t.get("name"), "weight": t.get("weight", 1), "keywords": t.get("keywords", ""), "active": t.get("active", True)}
        for t in data.get("topics", []) if t.get("active", True)
    ]
    scores = []
    raw_scores = data.get("scores", {}) or {}
    for key, value in raw_scores.items():
        if not isinstance(key, str) or "|" not in key:
            continue
        community_id, topic_id = key.split("|", 1)
        try:
            score = float(value)
        except Exception:
            score = 0
        if score > 0:
            scores.append({"community_id": community_id, "topic_id": topic_id, "score_0_5": score})
    return {"communities": communities, "topics": topics, "scores": scores[:2000]}


def _llm_context_for_record(data: dict[str, Any], batch: dict[str, Any], rec: dict[str, Any]) -> dict[str, Any]:
    project = data.get("project", {}) or {}
    scoring = rec.get("scoring") or {}
    analysis = rec.get("analysis") or {}
    return {
        "batch_context": {
            "batch_id": batch.get("id"),
            "batch_name": batch.get("name"),
            "input_mode": batch.get("input_mode"),
            "project": project,
            "originator_type": rec.get("originator_type") or project.get("originator_type"),
            "purpose": rec.get("purpose") or project.get("purpose") or project.get("archive_purpose"),
            "agenda": rec.get("agenda") or project.get("agenda"),
        },
        "record_metadata": {
            "id": rec.get("id"), "title": rec.get("title"), "path": rec.get("path") or rec.get("relative_path"),
            "doc_type": rec.get("doc_type") or analysis.get("document_type"),
            "date_from": rec.get("date_from"), "date_to": rec.get("date_to"),
            "retention_mark": rec.get("retention_mark"), "retention_years": rec.get("retention_years"),
            "reference_decision": rec.get("reference_decision") or rec.get("source_decision"),
            "technical_metadata": rec.get("technical") or rec.get("technical_metadata") or {},
        },
        "decision_profile": data.get("decision_profile", {}),
        "relevant_retention_rules": _relevant_retention_rules(data, rec, project),
        "detected_or_possible_topics": analysis.get("detected_topics") or rec.get("topics") or [],
        "communities_topics_matrix": _compact_matrix_for_llm(data),
        "algorithmic_result": {
            "decision": scoring.get("decision"),
            "final_score": scoring.get("final_score"),
            "components": scoring.get("components"),
            "matched_rules": scoring.get("matched_rules"),
            "explanation": scoring.get("explanation"),
        },
    }

@app.post("/batches/{batch_id}/score")
async def score_batch(batch_id: str, req: ScoreRequest):
    started = time.perf_counter()
    data = load_store(); batch = data.get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    records = batch.get("records", [])
    model_run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    llm_items = []; processed = 0; errors = 0
    for rec in records:
        rec["scoring"] = score_record(rec, records, data, batch.get("input_mode", "metadata")); processed += 1
        if req.mode in ("llm", "compare"):
            text = rec.get("text") or rec.get("analysis", {}).get("text_snippet") or "\n".join(str(rec.get(k, "")) for k in ["title", "description", "path"])
            rec["llm_analysis"] = await llm_analyze(text, data.get("llm_config", {}), data.get("topics", []), full_context=False, context=None)
            rec["llm_model"] = data.get("llm_config", {}).get("model"); rec["llm_model_run_id"] = model_run_id
            if rec["llm_analysis"].get("error"): errors += 1
            if rec["llm_analysis"].get("recommendation") in {"A", "V", "S"}:
                rec["llm_decision"] = rec["llm_analysis"]["recommendation"]
                if req.mode == "llm": rec["scoring"]["decision"] = rec["llm_decision"]
            llm_items.append(_llm_assessment_item(batch_id, rec, rec.get("llm_analysis", {}), data.get("llm_config", {}), model_run_id))
    if llm_items: data.setdefault("llm_assessments", []).extend(llm_items)
    batch["last_scored"] = datetime.now().isoformat(timespec="seconds"); batch["score_mode"] = req.mode
    if llm_items: batch["last_llm_analysis"] = {"model_run_id": model_run_id, "processed": processed, "errors": errors, "model": data.get("llm_config", {}).get("model")}
    _event(data, "score_batch", batch_id=batch_id, count=processed, started=started, detail={"mode": req.mode, "errors": errors, "model_run_id": model_run_id if llm_items else None})
    save_store(data); return batch


@app.post("/batches/{batch_id}/llm/analyze")
async def llm_analyze_batch(batch_id: str, req: LLMAnalyzeRequest):
    started = time.perf_counter()
    started_dt = datetime.now().isoformat(timespec="seconds")
    data = load_store(); batch = data.get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    cfg = data.get("llm_config", {})
    if not cfg.get("base_url") or not cfg.get("model"): raise HTTPException(400, "Chybí Base URL nebo model v LLM nastavení.")
    records = batch.get("records", [])
    model_run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    processed = skipped = errors = 0; llm_items = []
    for rec in records:
        if processed >= req.max_records: break
        if req.only_without_llm and rec.get("llm_analysis") and not req.overwrite: skipped += 1; continue
        if not rec.get("scoring"): rec["scoring"] = score_record(rec, records, data, batch.get("input_mode", "metadata"))
        text = rec.get("text") or rec.get("analysis", {}).get("text_snippet") or "\n".join(str(rec.get(k, "")) for k in ["title", "description", "path", "doc_type", "date_from", "date_to"])
        llm = await llm_analyze(text, cfg, data.get("topics", []), full_context=req.full_context, context=_llm_context_for_record(data, batch, rec) if req.full_context else None)
        rec["llm_analysis"] = llm; rec["llm_model"] = cfg.get("model"); rec["llm_model_run_id"] = model_run_id
        if llm.get("error"): errors += 1
        if llm.get("recommendation") in {"A", "V", "S"}: rec["llm_decision"] = llm["recommendation"]
        llm_items.append(_llm_assessment_item(batch_id, rec, llm, cfg, model_run_id)); processed += 1
    if llm_items: data.setdefault("llm_assessments", []).extend(llm_items)
    finished_dt = datetime.now().isoformat(timespec="seconds")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    batch["last_llm_analysis"] = {
        "started_at": started_dt,
        "finished_at": finished_dt,
        "elapsed_ms": elapsed_ms,
        "elapsed_seconds": round(elapsed_ms / 1000, 3),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "max_records": req.max_records,
        "only_without_llm": req.only_without_llm,
        "overwrite": req.overwrite,
        "full_context": req.full_context,
        "context_mode": "full" if req.full_context else "basic",
        "model": cfg.get("model"),
        "model_run_id": model_run_id,
    }
    _event(data, "llm_analysis", batch_id=batch_id, count=processed, started=started, detail=batch["last_llm_analysis"])
    save_store(data)
    return {"batch": batch, **batch["last_llm_analysis"]}


@app.patch("/batches/{batch_id}/records/{record_id}/decision")
def human_decision(batch_id: str, record_id: str, payload: dict[str, Any]):
    data = load_store(); batch = data.get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    for rec in batch.get("records", []):
        if rec.get("id") == record_id:
            rec["human_decision"] = payload.get("decision")
            rec["human_note"] = payload.get("note", "")
            rec["human_confirmed_at"] = datetime.now().isoformat(timespec="seconds")
            save_store(data)
            return rec
    raise HTTPException(404, "Záznam nenalezen")


@app.get("/batches/{batch_id}/dashboard")
def dashboard(batch_id: str):
    batch = load_store().get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    by_year, by_place, by_topic, by_decision, by_reference_decision, by_ext = {}, {}, {}, {}, {}, {}
    missing = {"date": 0, "place": 0, "topic": 0}
    for r in batch.get("records", []):
        a = r.get("analysis", {})
        year = r.get("date_from") or a.get("time_range", {}).get("earliest")
        if year: by_year[str(year)] = by_year.get(str(year), 0) + 1
        else: missing["date"] += 1
        pls = ([r.get("place")] if r.get("place") else []) + a.get("places", [])
        if pls:
            for p in set(pls): by_place[p] = by_place.get(p, 0) + 1
        else: missing["place"] += 1
        topics = a.get("detected_topics", [])
        if topics:
            for t in topics: by_topic[t.get("name", t.get("id"))] = by_topic.get(t.get("name", t.get("id")), 0) + 1
        else: missing["topic"] += 1
        dec = r.get("human_decision") or r.get("scoring", {}).get("decision") or "N"
        by_decision[dec] = by_decision.get(dec, 0) + 1
        ref_dec = r.get("reference_decision") or r.get("source_decision")
        if ref_dec:
            by_reference_decision[ref_dec] = by_reference_decision.get(ref_dec, 0) + 1
        ext = r.get("extension") or r.get("form") or "metadata"
        by_ext[ext] = by_ext.get(ext, 0) + 1
    return {"by_year": by_year, "by_place": by_place, "by_topic": by_topic, "by_decision": by_decision, "by_reference_decision": by_reference_decision, "by_extension": by_ext, "missing": missing, "count": len(batch.get("records", []))}


@app.get("/export/config")
def export_config():
    data = load_store()
    payload = {k: data.get(k) for k in ["project", "decision_profile", "community_groups", "communities", "topic_groups", "topics", "scores", "retention_rules"]}
    path = export_json(f"docselector_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", payload)
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.get("/export/batch/{batch_id}/json")
def export_batch_json(batch_id: str):
    batch = load_store().get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    path = export_json(f"{batch_id}_audit.json", batch)
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.get("/export/batch/{batch_id}/csv")
def export_batch_csv(batch_id: str):
    batch = load_store().get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    path = export_results_csv(batch)
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.post("/batches/{batch_id}/sort")
def sort_batch(batch_id: str, req: SortRequest):
    data = load_store(); batch = data.get("batches", {}).get(batch_id)
    if not batch: raise HTTPException(404, "Dávka nenalezena")
    result = sort_files(batch, req.output_root, req.mode)
    batch["last_sort"] = result
    save_store(data)
    return result
