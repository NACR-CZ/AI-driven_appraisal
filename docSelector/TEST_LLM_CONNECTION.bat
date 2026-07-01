@echo off
setlocal
cd /d "%~dp0backend"
title DocSelector - test LLM

if not exist ".venv\Scripts\python.exe" (
  echo CHYBA: Virtualni prostredi neexistuje. Nejprve spustte START_DOCSELECTOR.bat.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "from app.config import settings; import requests; print('ENV:', settings.env_file); print('URL:', settings.llm_base_url); print('MODEL:', settings.llm_model); print('KLIC:', ('nacten, delka ' + str(len(settings.llm_api_key)) + ', zacatek ' + settings.llm_api_key[:4] + '...' + settings.llm_api_key[-4:]) if settings.llm_api_key else 'CHYBI'); r=requests.get(settings.llm_base_url.rstrip('/') + '/models', headers={'Authorization':'Bearer ' + settings.llm_api_key}, timeout=30); print('HTTP:', r.status_code); print((r.text or '')[:2000])"

echo.
pause
