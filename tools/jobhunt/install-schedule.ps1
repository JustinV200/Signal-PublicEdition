# install-schedule.ps1: registers (or with -Uninstall removes) the Task Scheduler
# task that runs run.ps1 daily at the times in schedule.psd1 (tools/jobhunt).
#
# Runs as the current user, only while logged on, without elevation, so no admin
# rights are needed. Missed runs (PC off or asleep) start when it's available.
# Also copies browser-jobs.example.toml to tools/browser/browser-jobs.toml if
# that local, gitignored config doesn't exist yet.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\install-schedule.ps1 [-Uninstall]

param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'

$TaskName = 'Signal job applications'
# Run times live in schedule.psd1 (`setup config jobhunt` edits them).
$RunTimes = (Import-PowerShellDataFile (Join-Path $PSScriptRoot 'schedule.psd1')).RunTimes
# A stuck run is stopped after this long so it can't block the next one.
$TimeLimit = New-TimeSpan -Hours 3

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "removed '$TaskName' (if it existed)"
    exit 0
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$browserConfig = Join-Path $repoRoot 'tools\browser\browser-jobs.toml'
if (-not (Test-Path $browserConfig)) {
    Copy-Item (Join-Path $PSScriptRoot 'browser-jobs.example.toml') $browserConfig
    Write-Output "created $browserConfig"
}

# conhost --headless runs PowerShell with no window at all (-WindowStyle Hidden
# still flashes one at every trigger).
$runScript = Join-Path $PSScriptRoot 'run.ps1'
$action = New-ScheduledTaskAction -Execute 'conhost.exe' -WorkingDirectory $repoRoot `
    -Argument "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runScript`""
$triggers = $RunTimes | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit $TimeLimit -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Principal $principal `
    -Settings $settings -Description 'Signal: one headless job-application run (tools/jobhunt/run.ps1).' -Force | Out-Null
Write-Output "registered '$TaskName' daily at $($RunTimes -join ', ')"
