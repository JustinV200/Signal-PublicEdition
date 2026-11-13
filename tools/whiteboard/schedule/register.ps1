<#
.SYNOPSIS
Registers the whiteboard's morning run as a per-user scheduled task (no admin needed):
today's keynotes, then the TODO view's daily refresh.

.DESCRIPTION
Creates or replaces the task named in schedule.psd1. It runs as the current user, only
while they are logged on, without elevation. Each run has two actions, in order, from
the repo root with no console window (uvw and pythonw):
1. `whiteboard.cli keynotes`: one tool-less Claude (Sonnet) call writes today's 2-4
   keynote lines to tools\whiteboard\.state\keynotes.json. If it fails, the views just
   show no keynotes today.
2. `whiteboard.cli todo sync --if-running`: refreshes a running whiteboard daemon and
   does nothing otherwise (it never starts the projector; a daemon syncs by itself
   when it starts). The daemon logs the sync in tools\whiteboard\.state\daemon.log.
Same pattern as tools\mail-digest\register.ps1.

.PARAMETER TaskName
Overrides the task name from schedule.psd1, e.g. to test with a throwaway name.

.PARAMETER RunNow
Starts the task once right after registering it.

.EXAMPLE
.\tools\whiteboard\schedule\register.ps1 -WhatIf
.\tools\whiteboard\schedule\register.ps1 -RunNow
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
# --no-sync: a running daemon holds the venv, so the 06:00 run must never try to change it.
$uvw = (Get-Command uvw.exe).Source

$run = "run --project `"$toolRoot`" --frozen --no-sync pythonw -m whiteboard.cli"
# Task Scheduler runs a task's actions one after another, so the sync sees the new keynotes.
$actions = @(
    (New-ScheduledTaskAction -Execute $uvw -Argument "$run keynotes" -WorkingDirectory $repoRoot),
    (New-ScheduledTaskAction -Execute $uvw -Argument "$run todo sync --if-running" -WorkingDirectory $repoRoot)
)
$triggers = @($config.RunTimes | ForEach-Object {
    $trigger = New-ScheduledTaskTrigger -Daily -At $_
    # -At stores a UTC StartBoundary ("...Z"), so the run drifts an hour when DST
    # starts or ends. A boundary with no zone is local time all year.
    $trigger.StartBoundary = ([datetime]$_).ToString('s')
    $trigger
})
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
# StartWhenAvailable: a run missed while the PC slept or was off starts once it's back.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $config.TimeLimitMinutes)

if ($PSCmdlet.ShouldProcess("$($config.TaskPath)$TaskName at $($config.RunTimes -join ', ')", 'Register scheduled task')) {
    Register-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath -Action $actions `
        -Trigger $triggers -Principal $principal -Settings $settings -Force `
        -Description 'Signal: writes the whiteboard keynotes with Claude, then refreshes the TODO view from life/ (tools/whiteboard). Never edits life/.' | Out-Null
    Write-Host "Registered '$TaskName': daily at $($config.RunTimes -join ', ')."
    if ($RunNow) {
        Start-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath
        Write-Host "Started once."
    }
}
