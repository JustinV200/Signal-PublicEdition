# Schedule for the whiteboard's morning run (keynotes, then the TODO view's refresh),
# read by register.ps1 and unregister.ps1. Same layout as tools/mail-digest/schedule.psd1.
# Between runs: `uv run --project tools/whiteboard --frozen --no-sync whiteboard keynotes`
# or `... whiteboard todo sync`.
@{
    TaskName         = 'Signal whiteboard TODO sync'
    TaskPath         = '\'
    # Local time, 24-hour. Change it here, then run register.ps1 again.
    RunTimes         = @('06:00')
    # The keynotes call takes under a minute (its own timeout is 3); this only stops a hung run.
    TimeLimitMinutes = 10
}
