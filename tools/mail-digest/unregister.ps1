<#
.SYNOPSIS
Removes the mail digest's scheduled task (no admin needed).

.DESCRIPTION
Deletes the task named in schedule.psd1. The state and log in
tools\mail-digest\.state\ are kept.

.PARAMETER TaskName
Overrides the task name from schedule.psd1, e.g. to remove a throwaway test task.

.EXAMPLE
.\tools\mail-digest\unregister.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName
)
$ErrorActionPreference = 'Stop'

$config = Import-PowerShellDataFile (Join-Path $PSScriptRoot 'schedule.psd1')
if (-not $TaskName) { $TaskName = $config.TaskName }

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "No scheduled task '$TaskName'; nothing to remove."
    return
}
if ($PSCmdlet.ShouldProcess("$($config.TaskPath)$TaskName", 'Unregister scheduled task')) {
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $config.TaskPath -Confirm:$false
    Write-Host "Removed '$TaskName'."
}
