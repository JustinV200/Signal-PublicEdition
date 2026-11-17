<#
.SYNOPSIS
Undoes register.ps1: stops and removes the daemon's logon task and the .mcp.json entry.

.DESCRIPTION
Ends a running daemon, deletes the task, and removes the "analysis-chamber" entry from the
repo's .mcp.json (other entries are untouched). It does NOT delete the analysis kit, the runs
or the private folder. To delete them by hand:
  - kit:     Remove-Item -Recurse $env:LOCALAPPDATA\analysis-chamber
  - runs:    life\analyses\ (in git) and the configured private_root (personal runs)

.PARAMETER TaskName
Overrides the task name, e.g. to remove a throwaway test task.

.EXAMPLE
.\tools\analysis-chamber\unregister.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'Signal analysis-chamber daemon'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$mcpPath = Join-Path $repoRoot '.mcp.json'

if ($PSCmdlet.ShouldProcess("$TaskName and the .mcp.json entry", 'Unregister the analysis chamber')) {
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $TaskName -TaskPath '\'
        # Stopping the task kills only uvw.exe; the daemon's pythonw processes outlive it.
        # Only this checkout's daemon: its venv launcher, and the base pythonw it started.
        $launcherPath = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
        $processes = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'"
        $launchers = @($processes | Where-Object {
            $_.ExecutablePath -eq $launcherPath -and $_.CommandLine -like '*-m analysis_chamber serve*'
        })
        $launcherIds = $launchers | ForEach-Object { $_.ProcessId }
        $daemons = @($processes | Where-Object { $launcherIds -contains $_.ParentProcessId })
        $daemons + $launchers |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\' -Confirm:$false
        Write-Host "Removed '$TaskName'."
    } else {
        Write-Host "No scheduled task '$TaskName'."
    }

    $text = [IO.File]::ReadAllText($mcpPath)
    # The entry is the comma and block before the closing brace of "mcpServers" (or after the
    # previous entry); remove it together with its leading comma.
    $pattern = ',\s*\r?\n\s*"analysis-chamber"\s*:\s*\{.*?\r?\n    \}'
    $updated = [regex]::Replace($text, $pattern, '', 'Singleline')
    if ($updated -ne $text) {
        [IO.File]::WriteAllText($mcpPath, $updated, (New-Object Text.UTF8Encoding $false))
        Write-Host 'Removed analysis-chamber from .mcp.json.'
    } else {
        Write-Host '.mcp.json has no analysis-chamber entry (or it is the first entry; remove by hand).'
    }
    Write-Host 'Kept: the kit, life\analyses and the private folder (see this script''s help to delete).'
}
