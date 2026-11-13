# Schedule for the agenda cache refresh, read by register.ps1 and unregister.ps1.
# Same layout as tools/whiteboard/schedule/schedule.psd1. For a refresh between runs:
# `uv run --project tools/calendar --frozen --no-sync calendar sync-cache`.
@{
    TaskName         = 'Signal calendar agenda cache'
    TaskPath         = '\'
    # How often the cache is rewritten. Change it here, then run register.ps1 again.
    IntervalMinutes  = 10
    # A sync takes a second or two; this only stops a hung run.
    TimeLimitMinutes = 5
}
