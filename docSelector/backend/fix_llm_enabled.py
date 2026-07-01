from pathlib import Path
import json

store_path = Path(__file__).parent / 'data' / 'docselector_store.json'
if not store_path.exists():
    raise SystemExit(f'Soubor nenalezen: {store_path}\nSpusť tento skript ze složky backend, kde je podadresář data.')

data = json.loads(store_path.read_text(encoding='utf-8'))
cfg = data.setdefault('llm_config', {})
cfg['enabled'] = True
store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('OK: llm_config.enabled = true')
print('Base URL:', cfg.get('base_url'))
print('Model:', cfg.get('model'))
print('API key uložen:', bool(cfg.get('api_key')))
