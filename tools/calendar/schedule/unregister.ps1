<#
.SYNOPSIS
Removes the agenda cache refresh scheduled task (no admin needed).

.DESCRIPTION
Deletes the task named in schedule.psd1. The token and the cache are untouched.
Same pattern as tools\whiteboard\schedule\unregister.ps1.

.PARAMETER TaskName
Overrides the task name from schedule.psd1, e.g. to remove a throwaway test task.

.EXAMPLE
.\tools\calendar\schedule\unregister.ps1 -WhatIf
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
