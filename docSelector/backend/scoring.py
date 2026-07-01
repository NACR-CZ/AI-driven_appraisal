from __future__ import annotations
from typing import Any


def _wildcard_match(rule_value: Any, actual: Any) -> bool:
    if rule_value in (None, "", "*"):
        return True
    if actual in (None, ""):
        return False
    return str(rule_value).strip().lower() == str(actual).strip().lower()


def match_retention_rule(record: dict[str, Any], project: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    actual = {
        "doc_type": record.get("doc_type") or record.get("analysis", {}).get("document_type"),
        "originator_type": record.get("originator_type") or project.get("originator_type"),
        "agenda": record.get("agenda") or project.get("agenda"),
        "purpose": project.get("purpose"),
    }
    active_rules = [r for r in rules if r.get("active", True)]
    active_rules.sort(key=lambda r: int(r.get("priority", 0)), reverse=True)
    for r in active_rules:
        if all(_wildcard_match(r.get(k), actual.get(k)) for k in ["doc_type", "originator_type", "agenda", "purpose"]):
            return r
    # Pokud importovaný seznam už obsahuje skartační znak, použijeme ho jako slabé/inferované pravidlo.
    # Není to totéž jako metodicky schválené pravidlo, proto má nízkou prioritu a je označené source=record_metadata.
    mark = (record.get("retention_mark") or "").strip().upper()
    if mark in {"A", "V", "S"}:
        return {
            "id": "RECORD_RETENTION_MARK",
            "source": "record_metadata",
            "doc_type": actual.get("doc_type") or "*",
            "originator_type": actual.get("originator_type") or "*",
            "agenda": actual.get("agenda") or "*",
            "purpose": actual.get("purpose") or "*",
            "retention_mark": mark,
            "retention_years": record.get("retention_years"),
            "decision": mark,
            "note": "Inferováno ze sloupce Sk. znak ve vstupním seznamu."
        }
    return None


def retention_score(rule: dict[str, Any] | None) -> float:
    if not rule:
        return 2.5
    decision = (rule.get("decision") or "V").upper()
    if decision == "A":
        return 5.0
    if decision == "S":
        return 1.0
    return 3.0


def community_matrix_score(analysis: dict[str, Any], store: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    topics = analysis.get("detected_topics") or []
    if not topics:
        return 0.0, []
    communities = [c for c in store.get("communities", []) if c.get("active", True)]
    topic_by_id = {t["id"]: t for t in store.get("topics", [])}
    scores = store.get("scores", {})
    contributions = []
    total = 0.0
    denom = 0.0
    for mt in topics:
        tid = mt.get("id")
        topic = topic_by_id.get(tid, {})
        tw = float(topic.get("weight", 1.0) or 1.0)
        topic_match = float(mt.get("match_score", 1.0) or 1.0) / 5.0
        for c in communities:
            cw = float(c.get("weight", 1.0) or 1.0)
            raw = float(scores.get(f"{c['id']}|{tid}", 0) or 0)
            if raw <= 0:
                continue
            weighted = raw * cw * tw * topic_match
            max_possible = 5.0 * cw * tw
            total += weighted
            denom += max_possible
            contributions.append({
                "community_id": c["id"], "community": c.get("name"), "topic_id": tid,
                "topic": topic.get("name", tid), "cell_score": raw, "community_weight": cw,
                "topic_weight": tw, "topic_match": round(topic_match, 3), "contribution": round(weighted, 3)
            })
    if denom <= 0:
        return 0.0, contributions
    return round((total / denom) * 5, 3), sorted(contributions, key=lambda x: -x["contribution"])[:20]


def metadata_quality_score(record: dict[str, Any]) -> float:
    fields = ["title", "doc_type", "date_from", "date_to", "place", "description"]
    present = sum(1 for f in fields if record.get(f) or record.get("analysis", {}).get(f))
    analysis = record.get("analysis", {})
    if analysis.get("time_range", {}).get("earliest"):
        present += 1
    if analysis.get("places"):
        present += 1
    if analysis.get("detected_topics"):
        present += 1
    return round(min((present / 9) * 5, 5), 3)


def information_density_score(record: dict[str, Any]) -> float:
    a = record.get("analysis", {})
    points = 0
    points += min(len(a.get("keywords", [])), 10) * 0.2
    points += min(len(a.get("persons", [])), 5) * 0.25
    points += min(len(a.get("places", [])), 5) * 0.25
    points += min(len(a.get("organizations", [])), 5) * 0.25
    points += min(len(a.get("detected_topics", [])), 4) * 0.4
    if a.get("time_range", {}).get("earliest"):
        points += 0.8
    return round(min(points, 5), 3)


def uniqueness_score(record: dict[str, Any], all_records: list[dict[str, Any]]) -> float:
    h = record.get("hash_md5")
    if h:
        same = [r for r in all_records if r.get("hash_md5") == h]
        if len(same) > 1:
            return 1.0
    title = (record.get("title") or "").lower().strip()
    same_title = [r for r in all_records if (r.get("title") or "").lower().strip() == title]
    return 3.0 if len(same_title) > 1 else 4.0


def technical_risk_score(record: dict[str, Any]) -> float:
    ext = (record.get("extension") or "").lower()
    if not ext:
        return 2.5
    if ext in {".txt", ".pdf", ".docx", ".csv", ".xml", ".jpg", ".png", ".tif", ".tiff"}:
        return 4.0
    if ext in {".mp3", ".wav", ".mp4", ".mov", ".avi"}:
        return 3.0
    if ext in {".tmp", ".bak", ".lnk"}:
        return 1.0
    return 2.5


def final_decision(score: float, profile: dict[str, Any], record: dict[str, Any], input_mode: str, rule: dict[str, Any] | None) -> str:
    safety = profile.get("safety", {})
    if rule and (rule.get("decision") or "").upper() == "A":
        return "A"
    if rule and (rule.get("decision") or "").upper() == "V":
        return "V"
    if input_mode == "metadata" and safety.get("metadata_only_never_auto_discard", True) and score < profile.get("thresholds", {}).get("review", 2.5):
        return "V"
    thresholds = profile.get("thresholds", {})
    if score >= float(thresholds.get("preserve", 4.0)):
        return "A"
    if score >= float(thresholds.get("review", 2.5)):
        return "V"
    return "S"


def score_record(record: dict[str, Any], all_records: list[dict[str, Any]], store: dict[str, Any], input_mode: str = "metadata") -> dict[str, Any]:
    profile = store.get("decision_profile", {})
    weights = profile.get("weights", {})
    project = store.get("project", {})
    rule = match_retention_rule(record, project, store.get("retention_rules", []))
    r_score = retention_score(rule)
    m_score, contributions = community_matrix_score(record.get("analysis", {}), store)
    md_score = metadata_quality_score(record)
    u_score = uniqueness_score(record, all_records)
    info_score = information_density_score(record)
    tech_score = technical_risk_score(record)
    components = {
        "retention_rule_score": r_score,
        "community_matrix_score": m_score,
        "metadata_quality_score": md_score,
        "uniqueness_score": u_score,
        "information_density_score": info_score,
        "technical_risk_score": tech_score,
    }
    final = 0.0
    total_w = 0.0
    for k, v in components.items():
        w = float(weights.get(k, 0) or 0)
        final += v * w
        total_w += w
    if total_w:
        final = final / total_w
    decision = final_decision(final, profile, record, input_mode, rule)
    confidence = min(abs(final - float(profile.get("thresholds", {}).get("review", 2.5))) / 2.5, 1.0)
    if decision == "A":
        label = "zachovat / archivovat"
    elif decision == "S":
        label = "kandidát na vyřazení"
    else:
        label = "přezkoumat ručně"
    trace = [
        {"step": "retention_rule", "matched": bool(rule), "rule": rule},
        {"step": "topic_matching", "topics": record.get("analysis", {}).get("detected_topics", [])},
        {"step": "community_matrix", "score": m_score, "top_contributions": contributions[:8]},
        {"step": "components", "scores": components, "weights": weights},
        {"step": "final_decision", "final_score": round(final, 3), "decision": decision, "confidence": round(confidence, 3)},
    ]
    explanation = build_explanation(record, decision, components, rule, contributions)
    return {
        "components": components,
        "matrix_contributions": contributions,
        "retention_rule": rule,
        "final_score": round(final, 3),
        "decision": decision,
        "decision_label": label,
        "confidence": round(confidence, 3),
        "explanation": explanation,
        "decision_trace": trace,
    }


def build_explanation(record: dict[str, Any], decision: str, components: dict[str, Any], rule: dict[str, Any] | None, contributions: list[dict[str, Any]]) -> str:
    bits = []
    if rule:
        bits.append(f"Sedí retenční pravidlo {rule.get('id')} ({rule.get('retention_mark')}, {rule.get('retention_years') or 'trvale'}).")
    topics = record.get("analysis", {}).get("detected_topics", [])
    if topics:
        bits.append("Detekovaná témata: " + ", ".join(t.get("name", t.get("id")) for t in topics[:4]) + ".")
    if contributions:
        top = contributions[0]
        bits.append(f"Nejvyšší komunitní vazba: {top.get('community')} × {top.get('topic')}.")
    bits.append(f"Skóre matice {components['community_matrix_score']:.2f}, informační hustota {components['information_density_score']:.2f}.")
    if decision == "A":
        bits.append("Výsledek směřuje k zachování.")
    elif decision == "S":
        bits.append("Výsledek je pouze kandidát na vyřazení a vyžaduje potvrzení člověkem.")
    else:
        bits.append("Výsledek je hraniční nebo pravidlově sporný, proto jde k ručnímu přezkumu.")
    return " ".join(bits)
