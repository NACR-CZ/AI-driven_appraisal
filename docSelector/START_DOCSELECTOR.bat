@echo off
setlocal
cd /d "%~dp0"
echo Spoustim DocSelector: backend + frontend...
echo.
start "DocSelector Backend" cmd /k call "%~dp0START_BACKEND.bat"
start "DocSelector Frontend" cmd /k call "%~dp0START_FRONTEND.bat"
echo.
echo Otevre se backend a frontend ve dvou oknech.
echo Backend:  http://localhost:8000/docs
echo Frontend: http://localhost:3000
echo.
pause
