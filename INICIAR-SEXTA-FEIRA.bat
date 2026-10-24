@echo off
setlocal EnableExtensions
title Sexta-Feira - Inicializador
cd /d "%~dp0"
set "LOG=%LOCALAPPDATA%\Sexta-Feira\iniciador.log"
if not exist "%LOCALAPPDATA%\Sexta-Feira" mkdir "%LOCALAPPDATA%\Sexta-Feira" >nul 2>&1
echo.>>"%LOG%"
echo ===== Inicio %DATE% %TIME% =====>>"%LOG%"
echo Pasta: %CD%>>"%LOG%"
if not exist "desktop_app.py" goto missing
if not exist "local_agent.py" goto missing
if not exist "public\index.html" goto missing
where py >nul 2>&1
if errorlevel 1 goto nopy

set "PYVER="
for %%V in (3.15 3.14 3.13 3.12 3.11 3.10 3) do call :checkpy %%V
if not defined PYVER goto nopy
echo Python selecionado: %PYVER%
echo Python selecionado: %PYVER%>>"%LOG%"
py -%PYVER% --version

py -%PYVER% -c "import webview" >nul 2>&1
if errorlevel 1 (
 echo Instalando pywebview...
 py -%PYVER% -m pip install --user pywebview >>"%LOG%" 2>&1
 py -%PYVER% -c "import webview" >>"%LOG%" 2>&1
 if errorlevel 1 goto dependencyerror
)
py -%PYVER% -c "import edge_tts" >nul 2>&1
if errorlevel 1 py -%PYVER% -m pip install --user edge-tts >>"%LOG%" 2>&1

echo Iniciando Sexta-Feira...
echo Inicio do app com Python %PYVER%>>"%LOG%"
py -%PYVER% desktop_app.py >>"%LOG%" 2>&1
if errorlevel 1 (
 echo O aplicativo fechou com erro. Log:
 type "%LOG%"
 goto error
)
goto done

:checkpy
if defined PYVER exit /b
py -%1 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYVER=%1"
exit /b

:missing
echo ERRO: faltam arquivos do aplicativo nesta pasta.
echo Verifique desktop_app.py, local_agent.py e public\index.html.
goto error
:nopy
echo ERRO: Python 3.11 ou superior nao foi encontrado.
echo Execute py -0p para verificar as versoes instaladas.
py -0p
goto error
:dependencyerror
echo ERRO: nao consegui instalar/verificar pywebview.
echo Consulte o log: "%LOG%"
goto error
:error
echo.
echo O iniciador nao conseguiu abrir a Sexta-Feira.
echo Log: "%LOG%"
pause
exit /b 1
:done
echo Sexta-Feira foi encerrada.
pause
endlocal
