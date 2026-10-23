@echo off
setlocal
cd /d "%~dp0"
set "LOG=%LOCALAPPDATA%\Sexta-Feira\instalacao.log"
if not exist "%LOCALAPPDATA%\Sexta-Feira" mkdir "%LOCALAPPDATA%\Sexta-Feira"
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.11 ou superior.
  pause
  exit /b 1
)
py -3.12 -c "import edge_tts" >nul 2>nul
if errorlevel 1 (
  echo Preparando a voz neural gratuita em portugues brasileiro...
  py -3.12 -m pip install --user edge-tts >> "%LOG%" 2>&1
)
py -3.12 -c "import webview" >nul 2>nul
if errorlevel 1 (
  py -3.12 -m pip install --user pywebview > "%LOG%" 2>&1
  if errorlevel 1 (
    echo Nao consegui preparar a janela do aplicativo.
    echo Consulte o arquivo: "%LOG%"
    pause
    exit /b 1
  )
)
where pyw >nul 2>nul
if errorlevel 1 (
  start "" py -3.12w desktop_app.py
) else (
  start "" pyw -3.12 desktop_app.py
)
endlocal
