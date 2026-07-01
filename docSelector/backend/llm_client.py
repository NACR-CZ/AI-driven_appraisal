from __future__ import annotations

import json
from typing import Any

import httpx


async def llm_analyze(
    text: str,
    config: dict[str, Any],
    topics: list[dict[str, Any]],
    *,
    full_context: bool = False,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """OpenAI-compatible LLM analysis.

    full_context=False: model receives only record text/title/description + valid topics.
    full_context=True: model also receives batch context, decision profile, relevant
    retention rules, communities/weights, topic weights, matrix scores and algorithmic
    scoring/explanation prepared by backend.
    """
    if not config.get("base_url") or not config.get("model"):
        return {"enabled": False, "error": "Chybí Base URL nebo model pro LLM."}

    config = dict(config)
    config["enabled"] = True

    topic_map = {
        t.get("id"): {
            "name": t.get("name"),
            "description": t.get("description", ""),
            "keywords": t.get("keywords", ""),
            "weight": t.get("weight", 1),
        }
        for t in topics
        if t.get("active", True) and t.get("id")
    }

    system = (
        "Jsi archivní analytik pro appraisal / výběr archiválií. "
        "Vrať pouze validní JSON bez markdownu. "
        "Neprovádíš finální skartaci, jen odborné doporučení pro člověka. "
        "Všechen vrácený text, tedy summary, reasoning, názvy rizik i vysvětlení, musí být v češtině."
    )

    schema = (
        '{"summary":"české shrnutí", "keywords":["česky"], '
        '"detected_topics":["id"], "places":[...], "persons":[...], '
        '"organizations":[...], "time_range":{"earliest":"YYYY","latest":"YYYY"}, '
        '"recommendation":"A|V|S", "confidence":0.0, "reasoning":"česky"}'
    )

    if full_context:
        context_payload = context or {}
        context_json = json.dumps(context_payload, ensure_ascii=False, indent=2, default=str)
        if len(context_json) > 24000:
            context_json = context_json[:24000] + "\n... [kontext zkrácen kvůli délce]"
        user = f"""Analyzuj záznam/dokument pro archivní appraisal.

REŽIM: PLNÝ METODICKÝ KONTEXT.
Použij níže uvedený kontext dávky, typ původce, účel archivace, agendu, rozhodovací profil, relevantní retenční pravidla, komunity a jejich váhy, témata a jejich váhy, matici komunita × téma a algoritmické skóre.
Tvým úkolem není mechanicky opsat algoritmus, ale zkontrolovat jej jako druhý posuzovatel. Při nejistotě doporuč V.
Tvrdá retenční pravidla nepřepisuj bez jasného důvodu; případný konflikt popiš ve zdůvodnění.
Všechen text ve výstupu vrať česky.

PLATNÁ TÉMATA:
{json.dumps(topic_map, ensure_ascii=False)}

METODICKÝ KONTEXT:
{context_json}

Vrať JSON přesně se strukturou:
{schema}

TEXT / POPIS ZÁZNAMU:
{text[:12000]}
"""
    else:
        user = f"""Analyzuj text nebo metadatový popis pro archivní appraisal.

REŽIM: ZÁKLADNÍ ÚDAJE.
Použij jen text/název/popis záznamu a seznam platných témat. Neopírej se o celou rozhodovací matici ani retenční pravidla.
Všechen text ve výstupu vrať česky.

PLATNÁ TÉMATA:
{json.dumps(topic_map, ensure_ascii=False)}

Vrať JSON přesně se strukturou:
{schema}

TEXT / POPIS ZÁZNAMU:
{text[:8000]}
"""

    try:
        headers = {"Content-Type": "application/json"}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config.get('api_key')}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{config['base_url'].rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": config.get("model"),
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": float(config.get("temperature", 0.1)),
                    "max_tokens": int(config.get("max_tokens", 1600) or 1600),
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(content)
            data["enabled"] = True
            data["context_mode"] = "full" if full_context else "basic"
            data["prompt_language"] = "cs"
            return data
    except Exception as e:
        return {"enabled": True, "context_mode": "full" if full_context else "basic", "prompt_language": "cs", "error": str(e)}


async def test_llm_connection(config: dict[str, Any]) -> dict[str, Any]:
    """Otestuje OpenAI-compatible chat/completions endpoint a vrátí bezpečný stav pro UI."""
    started = __import__('datetime').datetime.now()
    base_url = (config.get('base_url') or '').rstrip('/')
    model = config.get('model') or ''
    api_key = config.get('api_key') or ''
    if not base_url:
        return {"ok": False, "status": "missing_base_url", "message": "Chybí Base URL.", "tested_at": started.isoformat(timespec='seconds')}
    if not model:
        return {"ok": False, "status": "missing_model", "message": "Chybí název modelu.", "tested_at": started.isoformat(timespec='seconds')}

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Odpověz pouze jedním slovem: OK"},
                        {"role": "user", "content": "Test spojení"},
                    ],
                    "temperature": 0,
                    "max_tokens": 10,
                },
            )
            elapsed_ms = int((__import__('datetime').datetime.now() - started).total_seconds() * 1000)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status": "http_error",
                    "http_status": resp.status_code,
                    "message": resp.text[:600],
                    "tested_at": started.isoformat(timespec='seconds'),
                    "elapsed_ms": elapsed_ms,
                    "base_url": base_url,
                    "model": model,
                }
            payload = resp.json()
            reply = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "ok": True,
                "status": "connected",
                "message": "Spojení s LLM je navázáno.",
                "reply": str(reply).strip()[:200],
                "tested_at": started.isoformat(timespec='seconds'),
                "elapsed_ms": elapsed_ms,
                "base_url": base_url,
                "model": model,
            }
    except Exception as e:
        elapsed_ms = int((__import__('datetime').datetime.now() - started).total_seconds() * 1000)
        return {
            "ok": False,
            "status": "exception",
            "message": str(e),
            "tested_at": started.isoformat(timespec='seconds'),
            "elapsed_ms": elapsed_ms,
            "base_url": base_url,
            "model": model,
        }
