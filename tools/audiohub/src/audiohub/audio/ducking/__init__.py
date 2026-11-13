"""Music ducking for audiohub.audio: Ducker plus the Windows audio-session helpers it uses.

Re-exported by `audiohub.audio`; other packages import from there.
"""

from audiohub.audio.ducking.ducker import DUCKING_STATE_PATH, Ducker
from audiohub.audio.ducking.sessions import list_session_process_names

__all__ = ["DUCKING_STATE_PATH", "Ducker", "list_session_process_names"]
