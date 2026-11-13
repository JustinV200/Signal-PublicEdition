# approvals

Who may approve a managed session's tool calls, and how.

- `validate_permission_mode(mode)`: allows only `default`, `acceptEdits` and `plan`. `bypassPermissions` (and every other mode) raises `PermissionModeError`.
  - `acceptEdits` runs file edits, the Bash commands `mkdir`, `touch`, `rm`, `rmdir`, `mv`, `cp` and `sed`, and the PowerShell cmdlets `Set-Content`, `Add-Content`, `Clear-Content` and `Remove-Item` (and their aliases) on paths inside the repo without a dialog.
- `Approver` protocol: `async approve(ApprovalRequest) -> bool`. An approver owns its timeout and denies when in doubt.
- `DialogApprover(timeout_s=120, show_dialog=signal_confirm.confirm_async)`: the default approver.
  - Shows the topmost `signal_confirm` Allow/Deny dialog (`packages/confirm`) with the repo and tool, one dialog at a time.
  - Deny is the default button, and Allow has no keyboard shortcut, so a stray keystroke can't approve.
  - It denies by itself after the timeout, which counts from when the call arrives, time queued behind other dialogs included.
  - It calls `request.on_shown()` just as the dialog appears; the session posts its voice note there.
  - A dialog that fails to show denies.
- `describe_tool_call(tool_name, tool_input, title)`: the dialog text. The headline is the CLI's own prompt sentence; below it are the command, path or URL.

Depends on: `config`, `text`, and `signal_confirm` for the dialog (it runs in a child process, so the daemon's event loop never blocks).
