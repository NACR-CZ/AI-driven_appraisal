from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
STORE_PATH = DATA_DIR / "docselector_store.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


DEFAULT_STORE: dict[str, Any] = {
    "project": {
        "name": "Testovací appraisal dávka",
        "purpose": "predskartacni_posouzeni",
        "originator": "",
        "originator_type": "urad",
        "agenda": "",
        "archive_context": "testovací výzkumný režim",
        "place": "",
        "date_from": "",
        "date_to": "",
        "note": "",
    },
    "decision_profile": {
        "name": "Vyvážený profil A/S/V",
        "weights": {
            "retention_rule_score": 0.30,
            "community_matrix_score": 0.35,
            "metadata_quality_score": 0.10,
            "uniqueness_score": 0.10,
            "information_density_score": 0.10,
            "technical_risk_score": 0.05,
        },
        "thresholds": {"preserve": 4.0, "review": 2.5},
        "safety": {
            "metadata_only_never_auto_discard": True,
            "unknown_format_goes_to_review": True,
            "discard_requires_human_confirmation": True,
        },
    },
    "llm_config": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "enabled": False,
    },
    "community_groups": [
        {"id": "cg_academic", "name": "Akademici", "description": "Výzkumné a odborné komunity"},
        {"id": "cg_public", "name": "Veřejnost", "description": "Občané, genealogové, místní komunity"},
        {"id": "cg_institution", "name": "Instituce", "description": "Paměťové a veřejné instituce"},
        {"id": "cg_future", "name": "Budoucí / spekulativní", "description": "Prediktivní archivace a budoucí využití"},
    ],
    "communities": [
        {"id": "historik", "group_id": "cg_academic", "name": "Historik", "description": "Obecné historické využití", "type": "academic", "weight": 1.0, "active": True},
        {"id": "historik_mediciny", "group_id": "cg_academic", "name": "Historik medicíny", "description": "Dějiny zdravotnictví, nemocí a péče", "type": "academic", "weight": 1.2, "active": True},
        {"id": "sociolog", "group_id": "cg_academic", "name": "Sociolog", "description": "Společenské struktury, každodennost, instituce", "type": "academic", "weight": 1.0, "active": True},
        {"id": "epidemiolog", "group_id": "cg_academic", "name": "Epidemiolog", "description": "Výskyt a šíření nemocí v populaci", "type": "academic", "weight": 1.1, "active": True},
        {"id": "genealog", "group_id": "cg_public", "name": "Genealog", "description": "Rodinné a osobní dějiny", "type": "public", "weight": 0.8, "active": True},
        {"id": "obcan", "group_id": "cg_public", "name": "Občan", "description": "Veřejný zájem a komunitní paměť", "type": "public", "weight": 0.7, "active": True},
        {"id": "archivar", "group_id": "cg_institution", "name": "Archivář", "description": "Evidence, kontext, provenience, správa fondu", "type": "institutional", "weight": 1.2, "active": True},
        {"id": "datovy_vedec", "group_id": "cg_future", "name": "Datový vědec", "description": "Korpusy, NLP, longitudinální datové sady", "type": "future", "weight": 0.9, "active": True},
    ],
    "topic_groups": [
        {"id": "tg_health", "name": "Zdravotnictví", "description": "Zdraví, nemoci, veřejné zdravotnictví"},
        {"id": "tg_politics", "name": "Politika a správa", "description": "Správa, rozhodování, právo"},
        {"id": "tg_society", "name": "Společnost", "description": "Každodennost, spolky, práce, rodina"},
        {"id": "tg_environment", "name": "Životní prostředí", "description": "Krajina, klima, voda, včelaření"},
        {"id": "tg_data", "name": "Digitální a datová hodnota", "description": "Data, AI, technická a korpusová hodnota"},
    ],
    "topics": [
        {"id": "epidemie", "group_id": "tg_health", "name": "Epidemie", "description": "Výskyt a správa infekčních nemocí", "keywords": "epidemie;pandemie;neštovice;cholera;očkování;nákaza;hygiena", "weight": 1.5, "active": True},
        {"id": "zdravotnictvi", "group_id": "tg_health", "name": "Zdravotnictví", "description": "Organizace zdravotní péče a zdravotnické instituce", "keywords": "nemocnice;lékař;pacient;zdravotní;hygienická stanice", "weight": 1.2, "active": True},
        {"id": "politicke_dejiny", "group_id": "tg_politics", "name": "Politické dějiny", "description": "Rozhodování, moc, správa a veřejné události", "keywords": "rada;usnesení;volby;politika;ministerstvo;úřad", "weight": 1.2, "active": True},
        {"id": "kazdodennost", "group_id": "tg_society", "name": "Každodenní život", "description": "Běžný život, práce, bydlení, škola", "keywords": "rodina;škola;bydlení;práce;každodenní", "weight": 1.0, "active": True},
        {"id": "vcelareni", "group_id": "tg_environment", "name": "Včelaření", "description": "Chov včel, spolky, krajina, med", "keywords": "včely;včelař;med;úly;spolek", "weight": 0.8, "active": True},
        {"id": "ucetnictvi", "group_id": "tg_politics", "name": "Účetnictví a provoz", "description": "Běžné účetní a provozní doklady", "keywords": "faktura;účetní;doklad;objednávka;platba", "weight": 0.6, "active": True},
        {"id": "data_korpus", "group_id": "tg_data", "name": "Datová / korpusová hodnota", "description": "Dokumenty vhodné pro datovou analýzu a budoucí technologie", "keywords": "dataset;tabulka;databáze;korpus;metadata;xml;csv", "weight": 1.0, "active": True},
    ],
    "scores": {},
    "retention_rules": [
        {"id": "RET_A_ZAKLADACI", "doc_type": "zakládací dokument", "originator_type": "*", "agenda": "*", "purpose": "*", "retention_mark": "A", "retention_years": None, "decision": "A", "legal_basis": "zákon 499/2004 Sb.", "note": "Trvalá hodnota", "active": True, "priority": 100},
        {"id": "RET_S_UCETNI", "doc_type": "účetní doklad", "originator_type": "*", "agenda": "*", "purpose": "spisovna", "retention_mark": "S", "retention_years": 10, "decision": "S", "legal_basis": "zákon o účetnictví", "note": "Po lhůtě kandidát na skartaci", "active": True, "priority": 60},
        {"id": "RET_V_ZDRAVOTNI", "doc_type": "zdravotnická dokumentace", "originator_type": "nemocnice", "agenda": "zdravotnictví", "purpose": "*", "retention_mark": "V", "retention_years": 40, "decision": "V", "legal_basis": "zákon 372/2011 Sb.", "note": "Citlivé a hodnotné, ruční přezkum", "active": True, "priority": 80},
    ],
    "batches": {},
}

# Seed matrix scores
_seed_scores = {
    "historik|epidemie": 5, "historik_mediciny|epidemie": 5, "epidemiolog|epidemie": 5,
    "sociolog|epidemie": 3, "obcan|epidemie": 3, "datovy_vedec|epidemie": 4,
    "historik|zdravotnictvi": 4, "historik_mediciny|zdravotnictvi": 5, "epidemiolog|zdravotnictvi": 4,
    "archivar|zdravotnictvi": 4, "historik|politicke_dejiny": 5, "sociolog|politicke_dejiny": 4,
    "obcan|politicke_dejiny": 3, "archivar|politicke_dejiny": 4, "historik|kazdodennost": 4,
    "sociolog|kazdodennost": 5, "genealog|kazdodennost": 4, "obcan|kazdodennost": 4,
    "historik|vcelareni": 3, "sociolog|vcelareni": 2, "obcan|vcelareni": 3, "datovy_vedec|vcelareni": 2,
    "archivar|ucetnictvi": 2, "datovy_vedec|ucetnictvi": 2, "historik|ucetnictvi": 2,
    "datovy_vedec|data_korpus": 5, "archivar|data_korpus": 4, "historik|data_korpus": 3,
}
DEFAULT_STORE["scores"] = _seed_scores


def _backup_path(suffix: str = "bak") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return STORE_PATH.with_name(f"{STORE_PATH.stem}.{suffix}.{stamp}{STORE_PATH.suffix}")


def _try_parse_store_bytes(raw: bytes) -> dict[str, Any] | None:
    """Try to recover a JSON store that has encoding damage in text values."""
    # Normal expected encoding first.
    for encoding, errors in [
        ("utf-8", "strict"),
        ("utf-8-sig", "strict"),
        ("cp1250", "strict"),
        ("cp1252", "strict"),
        ("latin-1", "strict"),
        ("utf-8", "replace"),
    ]:
        try:
            text = raw.decode(encoding, errors=errors)
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def load_store() -> dict[str, Any]:
    if not STORE_PATH.exists():
        save_store(deepcopy(DEFAULT_STORE))

    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        # The store file was probably interrupted during write or contains non-UTF8 bytes.
        raw = STORE_PATH.read_bytes()
        recovered = _try_parse_store_bytes(raw)
        corrupt_path = _backup_path("corrupt_encoding")
        corrupt_path.write_bytes(raw)
        if recovered is not None:
            save_store(recovered)
            return recovered
        raise RuntimeError(
            f"Úložiště {STORE_PATH} má poškozené kódování a nepodařilo se ho automaticky opravit. "
            f"Poškozená kopie je uložená jako {corrupt_path}. Spusť repair_store.py nebo obnov export konfigurace."
        )
    except json.JSONDecodeError as exc:
        raw = STORE_PATH.read_bytes()
        recovered = _try_parse_store_bytes(raw)
        corrupt_path = _backup_path("corrupt_json")
        corrupt_path.write_bytes(raw)
        if recovered is not None:
            save_store(recovered)
            return recovered
        raise RuntimeError(
            f"Úložiště {STORE_PATH} není platný JSON: {exc}. "
            f"Poškozená kopie je uložená jako {corrupt_path}. Spusť repair_store.py nebo obnov export konfigurace."
        )


def save_store(data: dict[str, Any]) -> None:
    """Save the store atomically as UTF-8 JSON.

    Earlier versions wrote directly to docselector_store.json. If the server reloaded,
    the process was interrupted, or two requests saved at nearly the same time, the
    JSON file could become partially written / invalidly encoded. This function writes
    to a temporary UTF-8 file, validates it, creates a backup, and then replaces the
    original atomically.
    """
    data = deepcopy(data)
    data["_saved_at"] = now_iso()
    DATA_DIR.mkdir(exist_ok=True)

    tmp_path = STORE_PATH.with_name(f"{STORE_PATH.name}.tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path.write_text(text, encoding="utf-8", newline="\n")

    # Validate the newly written file before replacing the old one.
    with open(tmp_path, "r", encoding="utf-8") as f:
        json.load(f)

    if STORE_PATH.exists():
        try:
            backup = _backup_path("bak")
            backup.write_bytes(STORE_PATH.read_bytes())
        except Exception:
            # Backup failure should not block saving the application state.
            pass

    tmp_path.replace(STORE_PATH)


def reset_store() -> dict[str, Any]:
    data = deepcopy(DEFAULT_STORE)
    save_store(data)
    return data


def upsert_item(data: dict[str, Any], collection: str, item: dict[str, Any], prefix: str) -> dict[str, Any]:
    if not item.get("id"):
        item["id"] = new_id(prefix)
    items = data.setdefault(collection, [])
    for idx, existing in enumerate(items):
        if existing.get("id") == item["id"]:
            items[idx] = {**existing, **item}
            return items[idx]
    items.append(item)
    return item


def delete_item(data: dict[str, Any], collection: str, item_id: str) -> bool:
    items = data.setdefault(collection, [])
    before = len(items)
    data[collection] = [x for x in items if x.get("id") != item_id]
    return len(data[collection]) != before
