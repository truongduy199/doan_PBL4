param(
    [switch]$Apply,
    [switch]$DevicesOffline,
    [string]$DemoPlate,
    [switch]$NoRestart
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoRoot
$pythonExe = Join-Path $repoRoot '.venv/Scripts/python.exe'
$resetScript = Join-Path $repoRoot 'edge-server/scripts/reset_test_data.py'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Project .venv is missing.' }
$resetArgs = @($resetScript, '--json')
if ($DemoPlate) { $resetArgs += @('--demo-plate', $DemoPlate) }
$preview = & $pythonExe @resetArgs
if ($LASTEXITCODE -ne 0) { throw 'Reset preview failed; database unchanged.' }
$plan = $preview | ConvertFrom-Json
Write-Host "Database: $($plan.database)"
Write-Host 'Delete transaction rows:' ($plan.delete | ConvertTo-Json -Compress)
Write-Host 'Preserve accounts, registered vehicles, account face templates, slot IDs and configuration.'
if ($plan.vehicle_change) { Write-Host 'Demo plate:' $plan.vehicle_change.old_plate '->' $plan.vehicle_change.new_plate }
if (-not $Apply) { Write-Host 'Preview only. Run with -Apply to reset.'; return }
if (-not $DevicesOffline) {
    $null = Read-Host 'Power OFF both ESP boards and clear the IR sensors, then press Enter'
}
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $plan.http_port -ErrorAction SilentlyContinue)
$processes = @()
foreach ($listener in $listeners) {
    $info = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if (-not $info -or $info.CommandLine -notmatch 'smart_parking.interfaces.http.app:app') {
        throw 'Unexpected process on backend port; no process was stopped and database was not reset.'
    }
    $processes += $info.ProcessId
}
$wasRunning = $processes.Count -gt 0
$applied = $false
try {
    foreach ($backendId in ($processes | Select-Object -Unique)) {
        Stop-Process -Id $backendId
        Wait-Process -Id $backendId -Timeout 10 -ErrorAction SilentlyContinue
    }
    & $pythonExe @resetArgs --apply --database $plan.database
    if ($LASTEXITCODE -ne 0) { throw 'Reset failed; the database transaction was rolled back.' }
    $applied = $true
    if ($DemoPlate) {
        # Preserve every other local setting, including credentials.
        $envPath = Join-Path $repoRoot 'edge-server/.env'
        if (Test-Path -LiteralPath $envPath) {
            $content = [System.IO.File]::ReadAllText($envPath)
            $setting = 'DEMO_VEHICLE_PLATE=' + $plan.vehicle_change.new_plate
            if ($content -match '(?m)^DEMO_VEHICLE_PLATE=.*$') {
                $content = [regex]::Replace($content, '(?m)^DEMO_VEHICLE_PLATE=.*$', $setting)
            } else { $content = $content.TrimEnd() + "`n" + $setting + "`n" }
            [System.IO.File]::WriteAllText($envPath, $content, [System.Text.UTF8Encoding]::new($false))
        }
    }
} finally {
    if ($wasRunning -and -not $NoRestart) {
        $logDir = Join-Path $repoRoot 'edge-server/var/logs'
        $null = New-Item -ItemType Directory -Force -Path $logDir
        $backendArgs = @('-m','uvicorn','smart_parking.interfaces.http.app:app','--app-dir','edge-server/src',
                  '--host','0.0.0.0','--port',"$($plan.http_port)",'--workers','1')
        $backend = Start-Process -FilePath $pythonExe -ArgumentList $backendArgs -WorkingDirectory $repoRoot -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir 'backend.stdout.log') `
            -RedirectStandardError (Join-Path $logDir 'backend.stderr.log') -PassThru
        Write-Host "Backend restarted (launcher PID $($backend.Id))."
    }
}
if ($applied) { Write-Host 'Reset complete. Power ON both ESP boards, then refresh the dashboard.' }
