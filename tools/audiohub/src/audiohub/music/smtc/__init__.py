"""Public API of audiohub.music.smtc: the Windows media session music backend.

The rest of audiohub.music imports SMTC features from here only.
"""

from audiohub.music.smtc.controller import SmtcController

__all__ = ["SmtcController"]
