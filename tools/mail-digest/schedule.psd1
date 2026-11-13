# Schedule for the mail digest's per-user scheduled task, read by register.ps1 and
# unregister.ps1. The run's own settings (accounts, model, budget, lookback) are in
# src/mail_digest/settings.py. For a run between schedules: `mail-digest --now`.
@{
    TaskName         = 'Signal mail digest'
    TaskPath         = '\'
    # Local times, 24-hour. Change them here, then run register.ps1 again.
    # Scheduled runs are email-only and never trigger Duo (see README).
    RunTimes         = @('07:00')
    # Task Scheduler's backstop. The runner kills claude itself after 30 minutes
    # (RUN_TIMEOUT_S in settings.py), so keep this longer than that.
    TimeLimitMinutes = 45
}
