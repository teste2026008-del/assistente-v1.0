@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 local_agent.py) else (python local_agent.py)
if errorlevel 1 (
 echo.
 echo Instale Python 3.11 ou superior e marque Add Python to PATH.
 pause
)
