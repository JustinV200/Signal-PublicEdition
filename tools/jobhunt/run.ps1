# run.ps1: one headless job-application run (tools/jobhunt).
#
# Starts `claude -p` on Opus from the repo root with the browser-jobs MCP server
# added (Opus so the run matches its Opus reviewers), and the run follows
# life/areas/job-search/runbook.md. Output goes to .logs/<timestamp>.log.
# A lock file keeps two runs from overlapping.
# The scheduled task (install-schedule.ps1) calls this; you can run it by hand.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\run.ps1 [-DryRun]
#
# -DryRun takes the lock and logs the command it would run, without running it.
# Exit codes: 2 lock held by another run, 3 claude not found, 4 lock file
# couldn't be opened for another reason, 124 run timed out; else claude's code.

param([switch]$DryRun)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$LogDir = Join-Path $PSScriptRoot '.logs'
$LockPath = Join-Path $LogDir 'run.lock'
$JobsProfile = Join-Path $RepoRoot 'tools\browser\.profile-jobs'
$Prompt = 'Read AGENTS.md, then life/areas/job-search/runbook.md, and do one job-application run.'
# Under the scheduled task's 3 h limit, so this script (not Task Scheduler,
# which kills only powershell) ends the run and its whole process tree.
$RunTimeoutMs = 165 * 60 * 1000
# Same code as GNU timeout, so a timed-out run reads as one in the log.
$TimeoutExitCode = 124
# Win32 ERROR_SHARING_VIOLATION: another process holds the file open.
$SharingViolation = 32

New-Item -ItemType Directory -Force $LogDir | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd-HHmmss'
$LogPath = Join-Path $LogDir "$stamp.log"

function Write-Log([string]$Message) {
    # Every line gets a timestamp so the log reads on its own.
    $line = '{0} {1}' -f (Get-Date -Format 's'), $Message
    Add-Content -Path $LogPath -Value $line -Encoding utf8
}

function Find-Claude {
    # Returns the claude executable's path, or $null. PATH first, then the usual
    # install spots: npm global, the native installer, the VS Code extension's
    # bundled binary (newest version wins).
    $onPath = Get-Command claude -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $candidates = @(
        (Join-Path $env:APPDATA 'npm\claude.cmd'),
        (Join-Path $env:USERPROFILE '.local\bin\claude.exe')
    )
    foreach ($path in $candidates) { if (Test-Path $path) { return $path } }
    $extensions = Join-Path $env:USERPROFILE '.vscode\extensions'
    $bundled = Get-ChildItem $extensions -Directory -Filter 'anthropic.claude-code-*' -ErrorAction SilentlyContinue |
        Sort-Object { [version](($_.Name -split '-')[2]) } -Descending |
        ForEach-Object { Join-Path $_.FullName 'resources\native-binary\claude.exe' } |
        Where-Object { Test-Path $_ } |
        Select-Object -First 1
    return $bundled
}

function Stop-JobsEdge {
    # Kills any Edge left on .profile-jobs, e.g. by a run this script couldn't
    # clean up (Task Scheduler or a user ended it). The main browser's
    # .profile is never matched: the path must end right after .profile-jobs.
    $pattern = '--user-data-dir="?' + [regex]::Escape($JobsProfile) + '("|\s|$)'
    Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" |
        Where-Object { $_.CommandLine -match $pattern } |
        ForEach-Object {
            Write-Log "stopping leftover jobs Edge (pid $($_.ProcessId))"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Stop-ProcessTree([int]$ProcessId) {
    # Kills a process and all its children. Through cmd so taskkill's stderr
    # (e.g. "process not found" when it already exited) can't throw under
    # ErrorActionPreference Stop; its output goes to the log either way.
    cmd.exe /c "taskkill.exe /T /F /PID $ProcessId 2>&1" | ForEach-Object { Write-Log "$_" }
}

function Invoke-Claude([string]$Claude, [string[]]$ClaudeArgs) {
    # Runs claude with output to side files, waits up to $RunTimeoutMs, kills
    # the whole tree (MCP servers, browser tool, Edge) on timeout. Returns the
    # exit code, 124 on timeout. The output always reaches the log.
    $outPath = Join-Path $LogDir "$stamp.stdout.tmp"
    $errPath = Join-Path $LogDir "$stamp.stderr.tmp"
    $inPath = Join-Path $LogDir 'empty-stdin.txt'
    # Empty stdin: claude -p reads piped stdin and would wait on an open one.
    Set-Content -Path $inPath -Value $null
    # Start-Process joins arguments with spaces, so quote any that have them.
    $quoted = $ClaudeArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
    try {
        $proc = Start-Process -FilePath $Claude -ArgumentList $quoted -WorkingDirectory $RepoRoot -NoNewWindow -PassThru `
            -RedirectStandardInput $inPath -RedirectStandardOutput $outPath -RedirectStandardError $errPath
        # Touching Handle now keeps ExitCode readable after exit (a PowerShell 5.1 quirk).
        $null = $proc.Handle
        if ($proc.WaitForExit($RunTimeoutMs)) { return $proc.ExitCode }
        Write-Log "run passed $($RunTimeoutMs / 60000) min; killing claude's process tree"
        Stop-ProcessTree $proc.Id
        return $TimeoutExitCode
    } finally {
        # Each step catches and logs its own failure, so neither can replace the
        # exit code being returned.
        foreach ($path in @($outPath, $errPath)) {
            if (-not (Test-Path $path)) { continue }
            try { Get-Content $path | Add-Content -Path $LogPath -Encoding utf8 }
            catch { Write-Log "couldn't copy ${path}: $($_.Exception.Message)" }
            try { Remove-Item $path }
            catch { Write-Log "couldn't remove ${path}: $($_.Exception.Message)" }
        }
    }
}

# The lock is an exclusively opened file: Windows frees it when this process
# exits, even on a crash, so a stale lock can't block later runs.
try {
    $lock = [System.IO.File]::Open($LockPath, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    $ex = $_.Exception
    if ($ex.InnerException) { $ex = $ex.InnerException }
    if (($ex.HResult -band 0xFFFF) -eq $SharingViolation) {
        Write-Log "lock held by another run; exiting ($($ex.Message))"
        exit 2
    }
    Write-Log "couldn't open the lock file $LockPath; exiting ($($ex.Message))"
    exit 4
}

try {
    $claude = Find-Claude
    if (-not $claude) {
        Write-Log 'claude executable not found (PATH, %APPDATA%\npm, ~\.local\bin, VS Code extension); exiting'
        exit 3
    }
    $claudeArgs = @('-p', $Prompt, '--mcp-config', 'tools/jobhunt/mcp-jobs.json', '--permission-mode', 'bypassPermissions', '--model', 'opus')
    Write-Log "claude: $claude"
    Write-Log ('args: ' + ($claudeArgs -join ' '))
    if ($DryRun) {
        Write-Log 'dry run: not starting claude'
        exit 0
    }
    # Stays 1 if Invoke-Claude throws (e.g. claude couldn't start).
    $code = 1
    try {
        Stop-JobsEdge
        $code = Invoke-Claude $claude $claudeArgs
    } finally {
        Stop-JobsEdge
        Write-Log "run ended with code $code"
    }
    exit $code
} finally {
    $lock.Dispose()
}
