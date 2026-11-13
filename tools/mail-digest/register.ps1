<#
.SYNOPSIS
Registers the mail digest as a per-user scheduled task (no admin needed).

.DESCRIPTION
Creates or replaces the task named in schedule.psd1. It runs as the current user,
only while they are logged on (the mail tool's sign-ins are DPAPI-encrypted for this
user, so it can't run logged off) and without elevation. Each run starts
`uvw run --project tools\mail-digest --frozen --no-sync pythonw -m mail_digest` from
the repo root with no console window. With --no-sync a run never installs anything
(on a missing venv it just creates an empty one), so sync it by hand first (README,
Setup); registering checks that the job imports and refuses if it doesn't. The
runner writes its log to tools\mail-digest\.state\mail-digest.log.

.PARAMETER TaskName
Overrides the task name from schedule.psd1, e.g. to test with a throwaway name.

.PARAMETER RunNow
Starts the task once right after registering it.

.EXAMPLE
.\tools\mail-digest\register.ps1 -WhatIf
.\tools\mail-digest\register.ps1 -RunNow
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName,
    [switch]$RunNow
)
$ErrorActionPreference = 'Stop'

$config = Import-PowerShellDataFile (Join-Path $PSScriptRoot 'schedule.psd1')
if (-not $TaskName) { $TaskName = $config.TaskName }
$toolRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $toolRoot '..\..')).Path
# uvw is uv's windowless build; with pythonw the scheduled run opens no console.
$uvw = (Get-Command uvw.exe).Source
# uv (with a console) for the venv check below, whose exit code is needed.
$uv = (Get-Command uv.exe).Source

# The scheduled run. It must stay email-only: the owner is asleep at 07:00 and can't
# approve a Duo push, so it never uses a browser or a school/CAS login (the job's
# mcp.json loads only the mail server, whose Gmail API sign-ins need no Duo).
# Anything that may need Duo belongs in an on-demand run (mail-digest --now).
$action = New-ScheduledTaskAction -Execute $uvw `
    -Argument "run --project `"$toolRoot`" --frozen --no-sync pythonw -m mail_digest" `
    -WorkingDirectory $repoRoot
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
    # The task runs with --no-sync, so without a synced venv every run fails with no
    # console to show it (and a no-sync run on a missing venv just makes an empty one).
    # So the job must import before it's registered (-I: from the venv, not from a
    # mail_digest folder in the current directory). 'Continue' because Windows
    # PowerShell can turn a native command's stderr into terminating errors.
    $ErrorActionPreference = 'Continue'
    & $uv run --project $toolRoot --frozen --no-sync python -I -c 'import mail_digest'
    $isSynced = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    if (-not $isSynced) {
        throw "The mail digest's venv isn't synced, so every scheduled run would fail. From the repo root, run 'uv sync --project tools/mail-digest --frozen', then register again."
    }
    Register-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath -Action $action `
        -Trigger $triggers -Principal $principal -Settings $settings -Force `
        -Description 'Signal: digests Gmail into life/ (tools/mail-digest). Leaves edits uncommitted.' | Out-Null
    Write-Host "Registered '$TaskName': daily at $($config.RunTimes -join ', ')."
    if ($RunNow) {
        Start-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath
        Write-Host "Started once. Log: $toolRoot\.state\mail-digest.log"
    }
}
