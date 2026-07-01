
# DocVizor v.3.04 – vizualizace obsahu pro výběr
Tento balík obsahuje funkční prototyp pro výzkumné testování metody výběru A/V/S s využitím LLM a následnou vizualizací pro posouzení archivářem. 
Pro využití LLM musí mít uživatel vlastní API KEY.

## 1. Jak aplikace pracuje

### Vstup „sada souborů“

Každý nahraný soubor je jedna analyzovaná položka. Podporované textové extrakce: PDF, DOCX, PPTX, TXT/MD, CSV, JSON, XML/HTML, XLSX.

### Vstup „seznam“

Nahraje se jeden soubor CSV/XLSX/JSON/TXT. Každý řádek se posuzuje samostatně. U CSV se aplikace snaží poznat oddělovač.

### Kontrola toho, co se posílá LLM

Tlačítko **Zobrazit přesný prompt bez odeslání** připraví kompletní prompt, ale nevolá LLM.
Tlačítko **Odeslat na LLM a vizualizovat** uloží u každého výsledku také přesný prompt.

### Mapa

Místa vytěžená LLM se zobrazují na mapě OpenStreetMap. Souřadnice se doplňují až po kliknutí na **Doplnit souřadnice míst**, protože tím se názvy míst posílají na veřejnou službu Nominatim.

## 2. Poznámky a limity prototypu

- OCR zatím není součástí. U skenovaných PDF bez textové vrstvy se vytěží málo nebo nic.
- DOC starší než DOCX a PPT starší než PPTX nejsou zatím podporované.
- Geokódování míst je orientační; stejnojmenná místa mohou být špatně umístěna.
- Pro větší dávky bude vhodné doplnit frontu úloh a průběžný stav zpracování.
- `MAX_CHARS_PER_ITEM` chrání před odesláním příliš dlouhého obsahu.

## 3. Výstup JSON

Export obsahuje:

- model,
- agregace pro vizualizace,
- pro každou položku prompt,
- raw odpověď LLM,
- parsovaný JSON,
- technické údaje souboru včetně velikosti a SHA-256.

## 4. Patch UX 2026-06-18

Po výběru souboru se ještě nic neodesílá. Aplikace teď ukazuje:

- seznam vybraných souborů,
- stavovou hlášku,
- tlačítko `Otestovat spojení s backendem`,
- samostatnou záložku `Protokol`, kde je vidět, zda odešel požadavek na backend,
- hlášku `Čekám na LLM…` během analýzy.

Kontrola:

1. Backend musí běžet přes `python -m app.main`.
2. Frontend musí běžet přes `npm run dev`.
3. Na stránce klikněte na `Otestovat spojení s backendem`.
4. Pak vyberte soubor.
5. Klikněte na `Zobrazit přesný prompt bez odeslání` nebo `Odeslat na LLM a vizualizovat`.
6. V backend okně se při skutečné analýze musí objevit `POST /api/analyze`.

## 5. Test připojení k LLM

Dvojklikem spusťte `TEST_LLM_CONNECTION.bat`. Test ukáže, z jakého `.env` se konfigurace načetla, zkrácený otisk klíče, model a HTTP stav. Celý API klíč se nevypisuje.


## 6. Verze v.3.04

Verze v.3.04 opravuje zpracování LLM požadavků a zachovává paralelní běh až 4 modelů podle `LLM_MODELS`, přepínač kompletních výsledků podle modelu a tlačítko `Hromadný export dávky`. Hromadný export nyní vytvoří samostatný ZIP pro každou kombinaci dávka + model. Uvnitř každého ZIPu jsou adresáře prompt, png a json. Před exportem lze vyplnit název dávky, který se promítne do názvů ZIPů a manifestu.


## 7. Rate limit a paralelní modely

Verze v.3.04 hlídá dva limity:

- `MAX_PARALLEL_MODELS=4` – kolik modelů se může zpracovávat paralelně,
- `MAX_PARALLEL_LLM_REQUESTS=4` – globální limit všech současných HTTP požadavků na LLM endpoint napříč modely.

  (pokud máte možnost běhu více ještě modelů paralelně, lze pouze upravit počet a přidat názvy dalších modelů)

Pokud endpoint vrátí HTTP 429, aplikace požadavek několikrát zopakuje podle `LLM_RETRY_429_COUNT`.

## 8. Nejjednodušší spuštění přes BAT

V kořenové složce spusťte dvojklikem:

```text
START_DOCSELECTOR.bat
```

Skript automaticky:

- při prvním spuštění vytvoří `backend\.venv`,
- nainstaluje backendové knihovny pouze tehdy, pokud venv ještě neexistuje,
- vytvoří `backend\.env` z předlohy,
- při prvním spuštění otevře `.env` pro doplnění API klíče,
- nainstaluje frontendové balíčky pouze tehdy, pokud chybí `node_modules`,
- spustí backend i frontend ve dvou samostatných oknech,
- otevře aplikaci na `http://127.0.0.1:5173`.

Další pomocné soubory:

- `EDIT_LLM_SETTINGS.bat` – otevře nastavení LLM a API klíče,
- `REINSTALL_DOCSELECTOR.bat` – smaže venv a `node_modules`, když je potřeba čistá reinstalace; `.env` zůstane zachován.


Lokální prototyp aplikace pro:

- nahrání sady souborů, nebo seznamu CSV/XLSX/JSON/TXT,
- extrakci textu z PDF, DOCX, PPTX, TXT, CSV, JSON, XML, XLSX,
- zobrazení přesného promptu před odesláním,
- odeslání položek na OpenAI-compatible LLM endpoint,
- paralelní analýzu až ve 4 modelech podle `LLM_MODELS`,
- vytěžení témat, osob, institucí, míst, časového rozsahu, doby vzniku, typu dokumentu,
- vizualizaci témat, typů dokumentů, technických údajů a míst na OpenStreetMap,
- export výsledků do JSON včetně promptů,
- hromadný export celé dávky: JSON, prompty, rozhodnutí stromu a PNG dashboardy pro každý model.

## Důležité k Pythonu 3.14

Tato verze backendu je záměrně předělaná z FastAPI na Flask, aby se neinstaloval `pydantic-core`. Tím se obchází chybu:

```text
Python interpreter version (3.14) is newer than PyO3's maximum supported version (3.13)
```

## 9. Spuštění backendu

Ve složce `backend`:

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
python -m app.main
```

Backend poběží na:

```text
http://127.0.0.1:8000
```

Do `.env` doplňte hlavně:

```env
LLM_BASE_URL=---url LLM služeb
LLM_API_KEY=...
LLM_MODEL=any.model
LLM_MODELS=any.model1,any.model2,any.model3,any.model4
MAX_PARALLEL_MODELS=4
```

Bez API klíče aplikace neselže: zobrazí prompty a do výsledku napíše, že LLM nebylo voláno.

## 10. Spuštění frontendu

V druhém CMD okně ve složce `frontend`:

```bat
cd frontend
npm install
npm run dev
```

Otevřete adresu, kterou vypíše Vite, typicky:

```text
http://127.0.0.1:5173
```


