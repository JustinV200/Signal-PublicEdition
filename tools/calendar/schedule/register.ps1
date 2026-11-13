<#
.SYNOPSIS
Registers the agenda cache refresh as a per-user scheduled task (no admin needed).

.DESCRIPTION
Creates or replaces the task named in schedule.psd1. It runs as the current user, only
while they are logged on (the calendar sign-in is DPAPI-encrypted for this user), without
elevation, every IntervalMinutes. Each run starts
`uvw run --project tools\calendar --frozen --no-sync pythonw -m calendar_tool.cli sync-cache`
from the repo root with no console window. A failed run (offline, signed out) leaves the
old tools\calendar\.state\agenda.json in place and shows as a non-zero last-run result in
Task Scheduler. Read-only: it never changes the calendar. No Claude is involved.
Same pattern as tools\whiteboard\schedule\register.ps1 and tools\mail-digest\register.ps1.

.PARAMETER TaskName
Overrides the task name from schedule.psd1, e.g. to test with a throwaway name.

.PARAMETER RunNow
Starts the task once right after registering it.

.EXAMPLE
.\tools\calendar\schedule\register.ps1 -WhatIf
.\tools\calendar\schedule\register.ps1 -RunNow
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName,
    [switch]$RunNow
)
$ErrorActionPreference = 'Stop'

$config = Import-PowerShellDataFile (Join-Path $PSScriptRoot 'schedule.psd1')
if (-not $TaskName) { $TaskName = $config.TaskName }
$toolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path (Join-Path $toolRoot '..\..')).Path
# uvw is uv's windowless build; with pythonw the scheduled run opens no console.
$uvw = (Get-Command uvw.exe).Source
# uv (with a console) for the venv check below, whose exit code is needed.
$uv = (Get-Command uv.exe).Source

$action = New-ScheduledTaskAction -Execute $uvw `
    -Argument "run --project `"$toolRoot`" --frozen --no-sync pythonw -m calendar_tool.cli sync-cache" `
    -WorkingDirectory $repoRoot
# Once, starting now, repeating forever (no -RepetitionDuration means indefinitely).
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $config.IntervalMinutes)
# -At stores a UTC StartBoundary; a boundary with no zone is local time all year.
$trigger.StartBoundary = (Get-Date).ToString('s')
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
# StartWhenAvailable: a run missed while the PC slept or was off starts once it's back.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $config.TimeLimitMinutes)

if ($PSCmdlet.ShouldProcess("$($config.TaskPath)$TaskName every $($config.IntervalMinutes) min", 'Register scheduled task')) {
    # The task runs with --no-sync, so without a synced venv every run fails with no
    # console to show it. -I: import from the venv, not from the current directory.
    # 'Continue' because Windows PowerShell can turn a native command's stderr into
    # terminating errors.
    $ErrorActionPreference = 'Continue'
    & $uv run --project $toolRoot --frozen --no-sync python -I -c 'import calendar_tool.cli'
    $isSynced = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    if (-not $isSynced) {
        throw "The calendar tool's venv isn't synced, so every scheduled run would fail. From the repo root, run 'uv sync --project tools/calendar --frozen', then register again."
    }
    Register-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath -Action $action `
        -Trigger $trigger -Principal $principal -Settings $settings -Force `
        -Description 'Signal: refreshes the idle board agenda cache from Google Calendar (tools/calendar). Read-only.' | Out-Null
    Write-Host "Registered '$TaskName': every $($config.IntervalMinutes) min."
    if ($RunNow) {
        Start-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath
        Write-Host "Started once."
    }
}
