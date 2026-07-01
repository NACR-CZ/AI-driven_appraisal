from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SUPPORTED_TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"}

STOPWORDS_CS = {
    "a","i","v","na","se","je","to","z","do","ze","pro","při","po","k","s","o","ve","ale",
    "nebo","jak","jako","který","která","které","jsou","byl","byla","bylo","tento","tato","že","co",
    "podle","roku","dne","bez","nad","mezi","také","již","není","bude","byly","byli"
}

KNOWN_CITIES = [
    "Praha", "Brno", "Ostrava", "Plzeň", "Liberec", "Olomouc", "Pardubice", "Chrudim", "Hradec Králové",
    "České Budějovice", "Zlín", "Jihlava", "Opava", "Karlovy Vary", "Hlinsko", "Litomyšl", "Vysoké Mýto"
]

DOC_TYPE_PATTERNS = [
    ("účetní doklad", r"\b(faktura|účetní doklad|daňový doklad|objednávka|platba)\b"),
    ("zpráva", r"\b(zpráva|výroční zpráva|hlášení|podávám zprávu)\b"),
    ("zápis", r"\b(zápis|porada|jednání|usnesení|schůze)\b"),
    ("smlouva", r"\b(smlouva|smluvní strany|uzavírají)\b"),
    ("kronika", r"\b(kronika|pamětní kniha|letopis)\b"),
    ("žádost", r"\b(žádost|žádám|prosím o|obracím se)\b"),
    ("zdravotnická dokumentace", r"\b(pacient|anamnéza|diagnóza|očkování|hygienická stanice|nemocnice)\b"),
]


def file_hash(path: str, algo: str = "md5") -> str | None:
    try:
        h = hashlib.new(algo)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def extract_text(path: str, max_chars: int = 16000) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in SUPPORTED_TEXT_EXTS:
            return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                text = "\n".join(page.get_text() for page in doc[:20])
                return text[:max_chars]
            except Exception as e:
                return f"[PDF text extraction failed: {e}]"
        if ext == ".docx":
            try:
                from docx import Document
                doc = Document(path)
                return "\n".join(p.text for p in doc.paragraphs)[:max_chars]
            except Exception as e:
                return f"[DOCX extraction failed: {e}]"
    except Exception as e:
        return f"[Text extraction failed: {e}]"
    return ""


def detect_language(text: str) -> str:
    if not text or len(text) < 30:
        return "unknown"
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        cs_chars = sum(1 for c in text if c in "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ")
        return "cs" if cs_chars > len(text) * 0.01 else "unknown"


def keywords(text: str, n: int = 12) -> list[str]:
    if not text:
        return []
    try:
        import yake
        kw = yake.KeywordExtractor(lan="cs", n=2, dedupLim=0.7, top=n).extract_keywords(text)
        return [k for k, _score in kw[:n]]
    except Exception:
        words = re.findall(r"\b[A-Za-zÁ-ž]{4,}\b", text)
        freq = Counter(w.lower() for w in words if w.lower() not in STOPWORDS_CS)
        return [w for w, _ in freq.most_common(n)]


def dates(text: str) -> dict[str, Any]:
    years = set(int(y) for y in re.findall(r"\b(18\d{2}|19\d{2}|20[0-3]\d)\b", text or ""))
    mentions = re.findall(r"\b(?:\d{1,2}\.\s*\d{1,2}\.\s*)?(?:18\d{2}|19\d{2}|20[0-3]\d)\b", text or "")[:20]
    if not years:
        return {"earliest": None, "latest": None, "mentions": []}
    return {"earliest": str(min(years)), "latest": str(max(years)), "mentions": list(dict.fromkeys(mentions))[:10]}


def places(text: str) -> list[str]:
    out = []
    lower = (text or "").lower()
    for c in KNOWN_CITIES:
        if c.lower() in lower:
            out.append(c)
    extra = re.findall(r"\b(?:v|ve|z|ze|do|na)\s+([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]{3,}(?:\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+)?)\b", text or "")
    return list(dict.fromkeys(out + extra))[:12]


def persons(text: str) -> list[str]:
    pattern = r"\b(?:(?:MUDr|PhDr|RNDr|Ing|Mgr|JUDr|prof|doc|Dr)\.?\s+)?([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]{2,})\b"
    return list(dict.fromkeys(re.findall(pattern, text or "")))[:10]


def organizations(text: str) -> list[str]:
    pattern = r"\b([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][\wÁ-ž\s]{3,}\s(?:úřad|škola|nemocnice|stanice|spolek|ministerstvo|archiv|firma|s\.r\.o\.|a\.s\.))\b"
    return list(dict.fromkeys(m.strip() for m in re.findall(pattern, text or "", flags=re.IGNORECASE)))[:10]


def detect_doc_type(text: str, fallback_name: str = "") -> str:
    probe = f"{fallback_name}\n{text[:3000]}".lower()
    for label, pat in DOC_TYPE_PATTERNS:
        if re.search(pat, probe, re.IGNORECASE):
            return label
    return "obecný dokument"


def match_topics(text: str, topics: list[dict[str, Any]], top_n: int = 4) -> list[dict[str, Any]]:
    probe = (text or "").lower()
    scored = []
    for t in topics:
        if not t.get("active", True):
            continue
        terms = []
        terms.extend(re.findall(r"\w+", (t.get("name") or "").lower()))
        terms.extend(re.findall(r"\w+", (t.get("description") or "").lower()))
        terms.extend([x.strip().lower() for x in (t.get("keywords") or "").split(";") if x.strip()])
        terms = [x for x in terms if len(x) > 3 and x not in STOPWORDS_CS]
        hits = sum(1 for term in set(terms) if term in probe)
        score = hits / max(len(set(terms)), 1)
        if hits:
            scored.append({"id": t["id"], "name": t.get("name", t["id"]), "match_score": round(min(score * 5, 5), 3), "hits": hits})
    scored.sort(key=lambda x: (-x["match_score"], x["name"]))
    return scored[:top_n]


def technical_metadata(path: str, root: str | None = None) -> dict[str, Any]:
    p = Path(path)
    stat = p.stat()
    mime, _ = mimetypes.guess_type(str(p))
    rel = str(p.relative_to(root)) if root else p.name
    return {
        "path": str(p), "relative_path": rel, "title": p.name, "extension": p.suffix.lower(),
        "mime": mime or "application/octet-stream", "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "hash_md5": file_hash(str(p)),
    }


def analyze_record(record: dict[str, Any], topics: list[dict[str, Any]]) -> dict[str, Any]:
    text = record.get("text") or "\n".join(str(record.get(k, "")) for k in ["title", "description", "path", "relative_path", "doc_type", "agenda"])
    d = dates(text)
    pl = places(text)
    return {
        "language": detect_language(text),
        "keywords": keywords(text),
        "time_range": {"earliest": record.get("date_from") or d["earliest"], "latest": record.get("date_to") or d["latest"], "mentions": d["mentions"]},
        "places": list(dict.fromkeys(([record.get("place")] if record.get("place") else []) + pl)),
        "persons": persons(text),
        "organizations": organizations(text),
        "document_type": record.get("doc_type") or detect_doc_type(text, record.get("title", "")),
        "detected_topics": match_topics(text, topics),
        "text_length": len(text),
        "text_snippet": text[:700],
    }
