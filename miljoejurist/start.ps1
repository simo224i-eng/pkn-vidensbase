# Start Miljøjuristen lokalt med dit eget Claude-abonnement (Claude Code) som sprogmodel.
#
#   powershell -ExecutionPolicy Bypass -File miljoejurist\start.ps1            # Haiku (standard)
#   powershell -ExecutionPolicy Bypass -File miljoejurist\start.ps1 -Model sonnet
#
# Kræver, at Claude Code er logget ind (kør claude.exe én gang og skriv /login).
# Kun til personlig, lokal brug. Åbn derefter http://localhost:8766
param([string]$Model = "haiku", [int]$Port = 8766)

$repo = Split-Path -Parent $PSScriptRoot
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    # Desktop-appen har sin egen claude.exe; tag den nyeste version
    $claude = Get-ChildItem "$env:APPDATA\Claude\claude-code" -Recurse -Filter claude.exe -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $claude) { Write-Error "Fandt ikke Claude Code (claude.exe)."; exit 1 }

$env:LLM_PROVIDER = "claude_cli"
$env:LLM_CLAUDE_BIN = $claude
$env:LLM_MODEL = $Model
$env:LLM_FAST_MODEL = "haiku"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Miljøjuristen på http://localhost:$Port  (sprogmodel: Claude Code / $Model)"
Set-Location $repo
& "$repo\.venv\Scripts\python.exe" -m uvicorn miljoejurist.server:app --port $Port
