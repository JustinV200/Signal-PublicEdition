"""Writing samples for the copytone skill: import files, paste text, pull your own sent mail.

Public API: import_paths, save_sample, sample_count, fetch_sent, save_candidates, collect.
Samples land in .claude/skills/copytone/samples/ (gitignored apart from its README).
"""

from signal_setup.samples.collect import collect
from signal_setup.samples.extract import import_paths
from signal_setup.samples.sent_mail import fetch_sent, save_candidates
from signal_setup.samples.store import TARGET_RANGE, sample_count, save_sample

__all__ = [
    "TARGET_RANGE",
    "collect",
    "fetch_sent",
    "import_paths",
    "sample_count",
    "save_candidates",
    "save_sample",
]
