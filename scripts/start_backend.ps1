param([switch]$WebOnly)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoRoot
$pythonCandidates = @(
    (Join-Path $repoRoot '.venv/Scripts/python.exe'),
    (Join-Path $repoRoot 'edge-server/.venv/Scripts/python.exe')
)
$pythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pythonExe) {
    throw 'Create .venv or edge-server/.venv and install the project first; see docs/setup/system-integration.md.'
}
if ($WebOnly) { $env:MQTT_ENABLED = 'false' }
$checkArgs = @('scripts/check_environment.py', '--runtime')
if ($WebOnly) { $checkArgs += '--web-only' }
& $pythonExe @checkArgs
if ($LASTEXITCODE -ne 0) { throw 'Resolve the missing runtime components listed above before starting.' }
& $pythonExe -m uvicorn smart_parking.interfaces.http.app:app --app-dir (Join-Path $repoRoot 'edge-server/src') --host 0.0.0.0 --port 8000 --workers 1
exit $LASTEXITCODE
