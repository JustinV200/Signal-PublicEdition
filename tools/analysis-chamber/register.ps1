<#
.SYNOPSIS
Sets up the analysis chamber: venv, analysis kit, daemon logon task, MCP entry, private folder.

.DESCRIPTION
Run it once from anywhere (no admin needed). It
  1. syncs the tool's venv (`uv sync`);
  2. builds the analysis kit (`analysis-chamber kit build`; slow the first time);
  3. registers a per-user logon task that runs `analysis-chamber serve` with no console window;
  4. adds the "analysis-chamber" entry to the repo's .mcp.json (same mcpshim pattern as the
     other entries; skipped when it's already there; other entries and formatting are untouched);
  5. creates the private folder for personal runs (private_root from the config).
Safe to run again. Undo with unregister.ps1.
With -TaskOnly, only step 3 runs (setup does the other steps itself).

.PARAMETER TaskName
Overrides the task name, e.g. to test with a throwaway name.

.PARAMETER TaskOnly
Only registers the at-login scheduled task: no uv sync, kit build, .mcp.json entry or private folder.

.PARAMETER RunNow
Starts the task once right after registering it.

.EXAMPLE
.\tools\analysis-chamber\register.ps1 -WhatIf
.\tools\analysis-chamber\register.ps1 -RunNow
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'Signal analysis-chamber daemon',
    [switch]$TaskOnly,
    [switch]$RunNow
)
$ErrorActionPreference = 'Stop'

$toolRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $toolRoot '..\..')).Path
$mcpPath = Join-Path $repoRoot '.mcp.json'
# uvw is uv's windowless build; with pythonw the daemon opens no console.
$uvw = (Get-Command uvw.exe).Source
$uv = (Get-Command uv.exe).Source

# The .mcp.json entry, written as text so the file's other entries and layout stay as they are.
$entryLines = @(
    '    "analysis-chamber": {',
    '      "command": "uv",',
    '      "args": ["run", "--project", "packages/mcpshim", "--frozen", "mcpshim", "--", "uv", "run", "--env-file", ".env", "--project", "tools/analysis-chamber", "--frozen", "analysis-chamber", "mcp"]',
    '    }'
)

function Add-McpEntry {
    if (-not (Test-Path $mcpPath)) {
        Write-Host '.mcp.json not found; skipped the MCP entry (re-run once it exists).'
        return
    }
    $text = [IO.File]::ReadAllText($mcpPath)
    if ($text -match '"analysis-chamber"\s*:') {
        Write-Host '.mcp.json already has analysis-chamber.'
        return
    }
    $nl = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    # Insert after the last server's closing brace, before the "servers" object closes.
    $pattern = '(\})(\s*\r?\n\s*\}\s*\r?\n\}\s*)$'
    if ($text -notmatch $pattern) { throw ".mcp.json has an unexpected shape; add the entry by hand." }
    $entry = $entryLines -join $nl
    $updated = [regex]::Replace($text, $pattern, { param($m) $m.Groups[1].Value + ',' + $nl + $entry + $m.Groups[2].Value })
    [IO.File]::WriteAllText($mcpPath, $updated, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Added analysis-chamber to .mcp.json (restart Claude Code sessions to see it).'
}

if ($PSCmdlet.ShouldProcess("$TaskName, .mcp.json, the private folder", 'Set up the analysis chamber')) {
    # 'Continue' because Windows PowerShell can turn a native command's stderr into
    # terminating errors; the exit codes are checked instead.
    $ErrorActionPreference = 'Continue'
    if (-not $TaskOnly) {
        & $uv sync --project $toolRoot --frozen
        $syncCode = $LASTEXITCODE
        if ($syncCode -eq 0) {
            & $uv run --project $toolRoot --frozen --no-sync analysis-chamber kit build
            $kitCode = $LASTEXITCODE
            $privateRoot = & $uv run --project $toolRoot --frozen --no-sync python -I -c 'from analysis_chamber.config import load_config; print(load_config().private_root)'
            $configCode = $LASTEXITCODE
        }
    }
    $ErrorActionPreference = 'Stop'
    if (-not $TaskOnly) {
        if ($syncCode -ne 0) { throw 'uv sync failed.' }
        if ($kitCode -ne 0) { throw 'Building the analysis kit failed.' }
        if ($configCode -ne 0 -or -not $privateRoot) { throw 'Could not read private_root from the config.' }
    }

    # pythonw -m because the console script would open a window. No time limit; IgnoreNew so a
    # second start can't double the daemon.
    $action = New-ScheduledTaskAction -Execute $uvw `
        -Argument "run --project `"$toolRoot`" --frozen --no-sync pythonw -m analysis_chamber serve" `
        -WorkingDirectory $repoRoot
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $TaskName -TaskPath '\' -Action $action `
        -Trigger $trigger -Principal $principal -Settings $settings -Force `
        -Description 'Signal: analysis chamber daemon (tools/analysis-chamber).' | Out-Null
    Write-Host "Registered '$TaskName': at logon."

    if (-not $TaskOnly) {
        Add-McpEntry
        New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
        Write-Host "Private folder: $privateRoot"
    }

    if ($RunNow) {
        Start-ScheduledTask -TaskName $TaskName -TaskPath '\'
        Write-Host 'Started. Log: %LOCALAPPDATA%\analysis-chamber'
    }
}
