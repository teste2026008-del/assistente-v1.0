@echo off
setlocal EnableExtensions
title Sexta-Feira - Inicializador
cd /d "%~dp0"

set "LOG=%LOCALAPPDATA%\Sexta-Feira\iniciador.log"
if not exist "%LOCALAPPDATA%\Sexta-Feira" mkdir "%LOCALAPPDATA%\Sexta-Feira" >nul 2>&1

echo.
echo ==========================================
echo       SEXTA-FEIRA - INICIADOR
echo ==========================================
echo.

if not exist "desktop_app.py" (
  echo ERRO: nao encontrei desktop_app.py.
  echo Coloque este arquivo na pasta principal do projeto.
  goto erro
)
if not exist "local_agent.py" (
  echo ERRO: nao encontrei local_agent.py.
  goto erro
)
if not exist "public\index.html" (
  echo ERRO: nao encontrei public\index.html.
  goto erro
)

where py >nul 2>&1
if errorlevel 1 (
  echo ERRO: o iniciador nao encontrou o Python Launcher.
  echo Instale Python 3.11 e marque "Add Python to PATH".
  goto erro
)

echo [1/3] Verificando Python 3.11...
py -3.11 --version
if errorlevel 1 (
  echo ERRO: Python 3.11 nao foi encontrado pelo comando py.
  echo Python 3.11 precisa estar instalado para este iniciador.
  goto erro
)

echo.
echo [2/3] Verificando a janela do aplicativo...
py -3.11 -c "import edge_tts" >nul 2>&1
if errorlevel 1 (
  echo Instalando o mecanismo gratuito de voz neural em portugues brasileiro...
  py -3.11 -m pip install --user edge-tts >> "%LOG%" 2>&1
  py -3.11 -c "import edge_tts" >nul 2>&1
  if errorlevel 1 (
    echo AVISO: nao consegui instalar a voz neural agora. O app ainda tentara a voz local do Windows.
  )
)
py -3.11 -c "import webview" >nul 2>&1
if errorlevel 1 (
  echo Instalando pywebview no Python 3.11...
  py -3.11 -m pip install --user pywebview >> "%LOG%" 2>&1
  py -3.11 -c "import webview" >nul 2>&1
  if errorlevel 1 (
    echo ERRO: nao foi possivel instalar/verificar pywebview.
    echo Detalhes salvos em: "%LOG%"
    goto erro
  )
)

echo.
echo [3/3] Abrindo a Sexta-Feira...
echo Se a janela nao abrir, o erro sera mostrado abaixo.
echo Log: "%LOG%"
echo.

py -3.11 desktop_app.py
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo O aplicativo encerrou com erro %RESULT%.
  echo Verifique tambem: "%LOCALAPPDATA%\Sexta-Feira\app.log"
  echo.
  type "%LOCALAPPDATA%\Sexta-Feira\app.log" 2>nul
  goto erro
)
goto fim

:erro
echo.
echo O iniciador nao conseguiu abrir a Sexta-Feira.
echo Se precisar de ajuda, envie uma foto desta tela.
echo.
pause
exit /b 1

:fim
echo.
echo Sexta-Feira encerrada.
pause
endlocal
