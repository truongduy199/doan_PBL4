param([switch]$WebOnly)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoRoot
$pythonExe = Join-Path $repoRoot 'edge-server/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Create edge-server/.venv and install the project first; see docs/setup/duy-handover.md.'
}
if ($WebOnly) { $env:MQTT_ENABLED = 'false' }
$checkArgs = @('scripts/check_duy.py', '--runtime')
if ($WebOnly) { $checkArgs += '--web-only' }
& $pythonExe @checkArgs
if ($LASTEXITCODE -ne 0) { throw 'Resolve the missing runtime components listed above before starting.' }
& $pythonExe -m uvicorn smart_parking.interfaces.http.app:app --host 0.0.0.0 --port 8000 --workers 1
exit $LASTEXITCODE
