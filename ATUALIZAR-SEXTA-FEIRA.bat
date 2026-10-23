@echo off
setlocal EnableExtensions
title Atualizar Sexta-Feira
cd /d "%~dp0"
set "REPO=https://raw.githubusercontent.com/teste2026008-del/assistente-v1.0/main"
set "BACKUP=%LOCALAPPDATA%\Sexta-Feira\backup-atualizacao-%RANDOM%"
if not exist "%LOCALAPPDATA%\Sexta-Feira" mkdir "%LOCALAPPDATA%\Sexta-Feira" >nul 2>&1
mkdir "%BACKUP%" >nul 2>&1
echo.
echo ==========================================
echo      ATUALIZADOR DA SEXTA-FEIRA
echo ==========================================
echo.
where powershell >nul 2>&1
if errorlevel 1 (
 echo ERRO: PowerShell nao encontrado.
 pause
 exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop'; $root='%CD%'; $base='%REPO%'; $backup='%BACKUP%';" ^
 "$files=@('local_agent.py','desktop_app.py','public/index.html','public/local-whisper.js','INICIAR-SEXTA-FEIRA-SOLO.bat');" ^
 "foreach($f in $files){$dest=Join-Path $root $f; $dir=Split-Path $dest -Parent; if(!(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force | Out-Null}; if(Test-Path $dest){$bk=Join-Path $backup $f; $bd=Split-Path $bk -Parent; if(!(Test-Path $bd)){New-Item -ItemType Directory -Path $bd -Force | Out-Null}; Copy-Item $dest $bk -Force}; $url=$base+'/'+$f; Write-Host ('Baixando '+$f); Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest }"
if errorlevel 1 (
 echo.
 echo A atualizacao falhou. Os arquivos anteriores foram copiados para:
 echo "%BACKUP%"
 echo.
 pause
 exit /b 1
)
echo.
echo Atualizacao concluida. Backup dos arquivos antigos:
echo "%BACKUP%"
echo.
choice /C SN /N /M "Deseja iniciar a Sexta-Feira agora? [S/N] "
if errorlevel 2 goto fim
call "%~dp0INICIAR-SEXTA-FEIRA-SOLO.bat"
:fim
endlocal
