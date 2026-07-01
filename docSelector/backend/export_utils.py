from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def export_json(name: str, data: Any) -> Path:
    path = RESULTS_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_results_csv(batch: dict[str, Any], name: str | None = None) -> Path:
    name = name or f"{batch['id']}_results.csv"
    path = RESULTS_DIR / name
    rows = batch.get("records", [])
    fields = ["id", "title", "spisovy_znak", "record_ref", "evidence_number", "relative_path", "doc_type", "retention_mark", "retention_years", "form", "storage", "date_from", "date_to", "place", "source_decision", "reference_decision", "algorithmic_decision", "human_decision", "final_score", "confidence", "explanation"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            scoring = r.get("scoring", {})
            w.writerow({
                "id": r.get("id"),
                "title": r.get("title"),
                "spisovy_znak": r.get("spisovy_znak"),
                "record_ref": r.get("record_ref"),
                "evidence_number": r.get("evidence_number"),
                "relative_path": r.get("relative_path") or r.get("path"),
                "doc_type": r.get("doc_type") or r.get("analysis", {}).get("document_type"),
                "retention_mark": r.get("retention_mark"),
                "retention_years": r.get("retention_years"),
                "form": r.get("form"),
                "storage": r.get("storage"),
                "date_from": r.get("date_from") or r.get("analysis", {}).get("time_range", {}).get("earliest"),
                "date_to": r.get("date_to") or r.get("analysis", {}).get("time_range", {}).get("latest"),
                "place": r.get("place") or "; ".join(r.get("analysis", {}).get("places", [])),
                "source_decision": r.get("source_decision"),
                "reference_decision": r.get("reference_decision"),
                "algorithmic_decision": scoring.get("decision"),
                "human_decision": r.get("human_decision"),
                "final_score": scoring.get("final_score"),
                "confidence": scoring.get("confidence"),
                "explanation": scoring.get("explanation"),
            })
    return path


def sort_files(batch: dict[str, Any], output_root: str, mode: str = "copy") -> dict[str, Any]:
    out = Path(output_root).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    moved = []
    errors = []
    decision_dirs = {"A": "A_zachovat", "V": "V_prezkoumat", "S": "S_kandidat_vyradit", "N": "N_nerozhodnuto"}
    for r in batch.get("records", []):
        src = r.get("path")
        if not src:
            continue
        src_path = Path(src)
        if not src_path.exists():
            errors.append({"path": src, "error": "soubor neexistuje"})
            continue
        decision = r.get("human_decision") or r.get("scoring", {}).get("decision") or "N"
        rel = Path(r.get("relative_path") or src_path.name)
        dst = out / decision_dirs.get(decision, "N_nerozhodnuto") / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if mode == "move":
                shutil.move(str(src_path), str(dst))
            else:
                shutil.copy2(str(src_path), str(dst))
            moved.append({"from": str(src_path), "to": str(dst), "decision": decision})
        except Exception as e:
            errors.append({"path": src, "error": str(e)})
    return {"output_root": str(out), "mode": mode, "processed": len(moved), "errors": errors, "items": moved}
