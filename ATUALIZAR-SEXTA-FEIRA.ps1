# Atualiza a Sexta-Feira diretamente do GitHub sem baixar ZIP.
$ErrorActionPreference = "Stop"
$Owner = "teste2026008-del"
$Repo = "assistente-v1.0"
$Branch = "main"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $Root ("backup-atualizacao-" + $Stamp)
$Files = @(
  "local_agent.py",
  "desktop_app.py",
  "INICIAR-SEXTA-FEIRA.bat",
  "ABRIR-SEXTA-FEIRA.vbs",
  "public/local-whisper.js",
  "public/index.html"
)
New-Item -ItemType Directory -Path $Backup -Force | Out-Null
foreach ($Relative in $Files) {
  $Target = Join-Path $Root $Relative
  $Directory = Split-Path -Parent $Target
  New-Item -ItemType Directory -Path $Directory -Force | Out-Null
  if (Test-Path $Target) {
    $BackupTarget = Join-Path $Backup $Relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $BackupTarget) -Force | Out-Null
    Copy-Item -LiteralPath $Target -Destination $BackupTarget -Force
  }
}
try {
  foreach ($Relative in $Files) {
    $UrlPath = $Relative.Replace("\\", "/")
    $Url = "https://raw.githubusercontent.com/$Owner/$Repo/$Branch/$UrlPath"
    $Target = Join-Path $Root $Relative
    $Temp = "$Target.download"
    Invoke-WebRequest -Uri $Url -OutFile $Temp -UseBasicParsing
    if (!(Test-Path $Temp) -or (Get-Item $Temp).Length -lt 1) {
      throw "O download de $Relative veio vazio."
    }
    Move-Item -LiteralPath $Temp -Destination $Target -Force
    Write-Host "Atualizado: $Relative"
  }
  Write-Host ""
  Write-Host "ATUALIZACAO CONCLUIDA. Backup: $Backup" -ForegroundColor Green
  Write-Host "Feche e abra a Sexta-Feira para aplicar as mudancas."
} catch {
  Write-Host "Falha na atualizacao: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Os arquivos anteriores estao no backup: $Backup"
  exit 1
}
