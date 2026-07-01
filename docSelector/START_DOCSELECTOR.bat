@echo off
setlocal
cd /d "%~dp0"
title DocVizor v.3.02 - spousteni

echo ===============================================
echo DocVizor v.3.02 - automaticke spusteni
echo ===============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo CHYBA: Python nebyl nalezen v PATH.
  echo Nainstalujte Python 3.14 nebo ho pridejte do PATH.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo CHYBA: npm nebyl nalezen v PATH.
  echo Nainstalujte Node.js LTS.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/4] Vytvarim virtualni prostredi backendu...
  python -m venv "backend\.venv"
  if errorlevel 1 goto :error

  echo [2/4] Instaluji knihovny backendu...
  "backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  "backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
  if errorlevel 1 goto :error
) else (
  echo [1/4] Virtualni prostredi backendu uz existuje.
)

if not exist "backend\.env" (
  echo [2/4] Vytvarim backend\.env z predlohy...
  copy /y "backend\.env.example" "backend\.env" >nul
  echo.
  echo POZOR: Do backend\.env je potreba doplnit LLM_API_KEY.
  start "" notepad "backend\.env"
)

if not exist "frontend\node_modules\.docselector_ready" (
  echo [3/4] Instaluji frontendove balicky z verejneho npm registru...
  pushd frontend
  call npm config set registry https://registry.npmjs.org/ --location=project
  if exist node_modules (
    echo Odstranuji nedokoncenou predchozi instalaci...
    rmdir /s /q node_modules 2>nul
    if exist node_modules (
      echo.
      echo CHYBA: Slozku frontend\node_modules nelze odstranit.
      echo Zavrete vsechna okna DocSelector FRONTEND, VS Code a Průzkumnika otevreneho v teto slozce,
      echo potom spustte tento BAT znovu.
      popd
      pause
      exit /b 1
    )
  )
  if exist package-lock.json del /f /q package-lock.json
  call npm cache verify
  call npm install --registry=https://registry.npmjs.org/
  if errorlevel 1 (
    popd
    goto :error
  )
  type nul > node_modules\.docselector_ready
  popd
) else (
  echo [3/4] Frontendove balicky uz existuji.
)

echo [4/4] Spoustim backend a frontend...
start "DocVizor BACKEND" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m app.main"
start "DocVizor FRONTEND" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo.
echo Aplikace se otevira na http://127.0.0.1:5173
timeout /t 5 /nobreak >nul
start "" http://127.0.0.1:5173
exit /b 0

:error
echo.
echo CHYBA: Instalace nebo spusteni se nepodarilo.
echo Zkontrolujte vypis vyse.
pause
exit /b 1
