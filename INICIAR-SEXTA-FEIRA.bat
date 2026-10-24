@echo off
setlocal
cd /d "%~dp0"
set "LOG=%LOCALAPPDATA%\Sexta-Feira\instalacao.log"
if not exist "%LOCALAPPDATA%\Sexta-Feira" mkdir "%LOCALAPPDATA%\Sexta-Feira" >nul 2>&1
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.11 ou superior.>> "%LOG%"
  exit /b 1
)
py -3.12 -c "import webview" >nul 2>nul
if errorlevel 1 (
  py -3.12 -m pip install --user pywebview >> "%LOG%" 2>&1
  py -3.12 -c "import webview" >> "%LOG%" 2>&1
  if errorlevel 1 exit /b 1
)
py -3.12 -c "import edge_tts" >nul 2>nul
if errorlevel 1 (
  py -3.12 -m pip install --user edge-tts >> "%LOG%" 2>&1
)
REM pyw abre o aplicativo sem uma janela de console associada.
where pyw >nul 2>nul
if errorlevel 1 (
  start "" py -3.12w desktop_app.py
) else (
  start "" pyw -3.12 desktop_app.py
)
endlocal
