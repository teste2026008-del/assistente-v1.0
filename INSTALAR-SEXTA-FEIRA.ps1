$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoZip = "https://codeload.github.com/teste2026008-del/assistente-v1.0/zip/refs/heads/main"
$installRoot = Join-Path $env:USERPROFILE "Sexta-Feira"
$tempZip = Join-Path $env:TEMP "sexta-feira-main.zip"
$tempDir = Join-Path $env:TEMP "sexta-feira-extract"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR LOCAL - SEXTA-FEIRA" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "1/4 - Verificando Python..."

$pythonOk = $false
try { & py -3 --version *> $null; if ($LASTEXITCODE -eq 0) { $pythonOk = $true } } catch {}
if (-not $pythonOk) {
  try { & python --version *> $null; if ($LASTEXITCODE -eq 0) { $pythonOk = $true } } catch {}
}
if (-not $pythonOk) {
  Write-Host "Python não encontrado. Tentando instalar Python 3.12 pelo winget..."
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "Não encontrei Python nem winget. Instale Python 3.12 em https://www.python.org/downloads/windows/ e execute este instalador novamente."
  }
  & winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Host "O winget não confirmou a instalação. Vou tentar continuar e verificar novamente."
  }
  $env:Path = "$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts;$env:Path"
  $pythonOk = $false
  try { & py -3 --version *> $null; if ($LASTEXITCODE -eq 0) { $pythonOk = $true } } catch {}
  if (-not $pythonOk -and (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) { $pythonOk = $true }
  if (-not $pythonOk) { throw "Não consegui confirmar o Python. Reinicie o CMD e execute o comando de instalação novamente." }
}

Write-Host "2/4 - Baixando o projeto do GitHub..."
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
Invoke-WebRequest -Uri $repoZip -OutFile $tempZip -UseBasicParsing

Write-Host "3/4 - Extraindo os arquivos..."
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
Expand-Archive -LiteralPath $tempZip -DestinationPath $tempDir -Force
$source = Join-Path $tempDir "assistente-v1.0-main"
if (-not (Test-Path (Join-Path $source "local_agent.py"))) {
  throw "O ZIP foi baixado, mas não encontrei local_agent.py. Confira se o arquivo existe no branch main do GitHub."
}
if (Test-Path $installRoot) {
  $backup = Join-Path $env:USERPROFILE ("Sexta-Feira-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  Move-Item -LiteralPath $installRoot -Destination $backup
  Write-Host "A versão anterior foi preservada em: $backup"
}
Move-Item -LiteralPath $source -Destination $installRoot
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $tempZip -Force -ErrorAction SilentlyContinue

Write-Host "4/4 - Preparando para iniciar..."
$launcher = Join-Path $installRoot "INICIAR-SEXTA-FEIRA.bat"
if (-not (Test-Path $launcher)) { throw "Os arquivos foram extraídos, mas o iniciador INICIAR-SEXTA-FEIRA.bat não foi encontrado." }

Write-Host ""
Write-Host "Instalação dos arquivos concluída em: $installRoot" -ForegroundColor Green
Write-Host "A IA e a voz ainda precisam de internet e usam o serviço online."
Write-Host "Abrindo a Sexta-Feira..."
Start-Process -FilePath $launcher -WorkingDirectory $installRoot
