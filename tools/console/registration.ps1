<#
.SYNOPSIS
Shared by register.ps1 and unregister.ps1 (dot-sourced): how this checkout's console
registration is named, how to tell a task is this checkout's, and how to remove one.

.DESCRIPTION
One registration is a logon task and a Start-menu shortcut, both named
"Signal console (<checkout folder>, port <port>)". A task or a shortcut is this
checkout's when its arguments name this checkout's tools\console folder in quotes, so a
same-named checkout elsewhere (same folder name) is never touched. Both scripts use these
rules so they can't drift apart. Sets $toolRoot, $repoRoot and $checkoutFolder in the caller's scope.
#>

$toolRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $toolRoot '..\..')).Path
$checkoutFolder = Split-Path -Leaf $repoRoot
$taskNamePrefix = "Signal console ($checkoutFolder, port "

# The task's and the shortcut's name for one port.
function Get-RegistrationName([int]$Port) {
    return "$taskNamePrefix$Port)"
}

# The Start-menu shortcut's path for one port.
function Get-ShortcutPath([int]$Port) {
    return Join-Path ([Environment]::GetFolderPath('Programs')) "$(Get-RegistrationName $Port).lnk"
}

# Case-insensitive "does $text contain $part" (false for an empty $text).
function Test-Contains([string]$text, [string]$part) {
    return [bool]$text -and $text.IndexOf($part, [StringComparison]::OrdinalIgnoreCase) -ge 0
}

# True when the task runs this checkout's console: an action's arguments name "$toolRoot".
function Test-OwnTask($task) {
    return [bool]($task.Actions | Where-Object { Test-Contains $_.Arguments "`"$toolRoot`"" })
}

# True when the shortcut at $path opens this checkout's console: its arguments name
# "$toolRoot", the same rule as Test-OwnTask. Read-only: CreateShortcut on an existing
# file only loads it; nothing is written until Save().
function Test-OwnShortcut([string]$path) {
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
    return Test-Contains $shortcut.Arguments "`"$toolRoot`""
}

# The ports of this checkout's registrations other than $Port: tasks named for this
# checkout on another port that run this checkout's console. Read-only.
function Get-OtherOwnPorts([int]$Port) {
    $pattern = '^' + [regex]::Escape($taskNamePrefix) + '(\d+)\)$'
    $tasks = Get-ScheduledTask -TaskPath '\' -ErrorAction SilentlyContinue |
        Where-Object { $_.TaskName -match $pattern -and (Test-OwnTask $_) }
    foreach ($task in $tasks) {
        $taskPort = [int]([regex]::Match($task.TaskName, $pattern).Groups[1].Value)
        if ($taskPort -ne $Port) { $taskPort }
    }
}

# This checkout's console server processes on $Port, the base Python first; none when it
# isn't running. Read-only. Stopping the task kills only uvw.exe and the server's Python
# processes outlive it (as in tools\rcs\unregister.ps1), so this finds them directly: the
# venv launcher (python.exe from `console open`, pythonw.exe from the task or the
# shortcut) running `-m signal_console serve --port <port>`, and the base Python it started.
function Get-ConsoleServerProcesses([int]$Port) {
    $scripts = Join-Path $toolRoot '.venv\Scripts'
    $launcherPaths = @('python.exe', 'pythonw.exe') | ForEach-Object { Join-Path $scripts $_ }
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'"
    $launchers = @($processes | Where-Object {
        $_.ExecutablePath -in $launcherPaths -and
        $_.CommandLine -match "-m signal_console serve .*--port $Port(\s|$)"
    })
    $launcherIds = $launchers | ForEach-Object { $_.ProcessId }
    $servers = @($processes | Where-Object { $launcherIds -contains $_.ParentProcessId })
    return $servers + $launchers
}

# Stops this checkout's console server on $Port. Returns whether one was running.
function Stop-ConsoleServer([int]$Port) {
    $processes = @(Get-ConsoleServerProcesses $Port)
    # SilentlyContinue: killing one may end the other first (the launcher's job kills its child).
    $processes | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    return $processes.Count -gt 0
}

# Removes this checkout's registration on $Port: deletes its task and its shortcut and,
# unless -KeepServer, stops its server, skipping each part that isn't there. Returns the
# words for what it did. -KeepServer leaves the task's running server alone (register.ps1
# moving the registration, whose wizard that server may be serving).
# Throws, before touching anything, when the task or the shortcut of that name opens
# another checkout's console (that one's to remove).
function Remove-ConsoleRegistration([int]$Port, [switch]$KeepServer) {
    $name = Get-RegistrationName $Port
    $task = Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue
    if ($task -and -not (Test-OwnTask $task)) {
        throw "The task '$name' runs another checkout's console; remove it with that checkout's unregister.ps1."
    }
    $shortcutPath = Get-ShortcutPath $Port
    $hasShortcut = Test-Path -LiteralPath $shortcutPath
    if ($hasShortcut -and -not (Test-OwnShortcut $shortcutPath)) {
        throw "The shortcut '$shortcutPath' opens another checkout's console; remove it with that checkout's unregister.ps1."
    }
    $done = @()
    if (-not $KeepServer) {
        if ($task) { Stop-ScheduledTask -TaskName $name -TaskPath '\' }
        if (Stop-ConsoleServer $Port) { $done += 'stopped its server' }
    }
    if ($task) {
        Unregister-ScheduledTask -TaskName $name -TaskPath '\' -Confirm:$false
        $done += 'removed its logon task'
    }
    if ($hasShortcut) {
        Remove-Item -LiteralPath $shortcutPath
        $done += 'removed its Start-menu shortcut'
    }
    return $done
}
