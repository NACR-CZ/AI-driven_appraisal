# DocSelector Phase 1 — prototyp nástroje pro archivní appraisal

Tento balík obsahuje první funkční prototyp pro výzkumné testování metody automatizovaného výběru A/V/S.

## Co prototyp umí

1. Metadata-only režim: import CSV/XLSX seznamu, i když obsahuje jen název a případně cestu.
2. Scan složky: vyčte názvy souborů, velikosti, datové formáty, hash a textovou vrstvu z TXT/PDF/DOCX.
3. Algoritmická analýza: klíčová slova, čas, místa, osoby, organizace, témata podle konfigurovatelné matice.
4. Matice designated communities × témata: skóre 0–5 + váha komunity + váha tématu.
5. Retenční pravidla: pravidlo je navázáno na kombinaci typ dokumentu + typ původce + agenda + účel.
6. Scoring: vypočítá A / V / S, vysvětlení a auditní stopu.
7. LLM porovnání: volitelně přes OpenAI-compatible API key.
8. Vizualizace: čas, místa, témata, rozhodnutí, formáty a kvalita metadat.
9. Export: nastavení JSON, auditní JSON, výsledky CSV.
10. Roztřídění souborů: kopírování do složek `A_zachovat`, `V_prezkoumat`, `S_kandidat_vyradit` se zachováním relativní hierarchie.

## Spuštění backendu

```bat
cd ...
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Swagger dokumentace: http://localhost:8000/docs

## Spuštění frontendu

V druhém CMD/PowerShellu:

```bat
cd ...
npm install
npm run dev
```

Otevři: http://localhost:3000

## První test

1. Spusť backend a frontend.
2. V záložce **Import / scan** nahraj `sample_data/metadata_seznam.csv`.
3. Klikni **Spočítat algoritmicky**.
4. Otevři **Vizualizace** a **Výsledky**.
5. V **Export / LLM** stáhni auditní JSON nebo výsledky CSV.

## Poznámky k metodě

- `A` = zachovat / archivovat.
- `V` = přezkoumat ručně; v hraničních případech je to správný výsledek, nikoli chyba.
- `S` = kandidát na vyřazení; prototyp nic nemaže, pouze kopíruje do složek po lidském potvrzení.
- Metadata-only vstup má bezpečnostní pravidlo: automaticky nedává definitivní skartaci bez přezkumu.

## LLM režim

V záložce **Export / LLM** vlož:

- Base URL, např. `https://api.openai.com/v1` nebo vlastní OpenAI-compatible endpoint
- Model
- API key
- zaškrtni zapnutí LLM

Potom v **Import / scan** použij **Porovnat s LLM**. Výsledek LLM se uloží do detailu záznamu vedle algoritmického výsledku.
