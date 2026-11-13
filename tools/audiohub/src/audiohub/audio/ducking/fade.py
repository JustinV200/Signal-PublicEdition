"""Linear volume fades over several audio sessions at once, used by Ducker."""

import time

from audiohub.audio.ducking.sessions import SessionVolume

# Interval between volume steps while fading.
FADE_STEP_MS = 10

# (volume control, start level, end level) for one session in a fade.
FadePlan = list[tuple[SessionVolume, float, float]]


def fade_volumes(plan: FadePlan, fade_ms: int) -> None:
    """Move several session volumes linearly from start to end together.

    The final step sets each end level exactly, so a restore returns the
    precise captured volume. Blocks for about `fade_ms`.

    Args:
        plan: (volume control, start level, end level) per session.
        fade_ms: Total fade time in milliseconds; 0 sets the end levels at once.

    Raises:
        COMError | OSError: If setting a volume fails.
    """
    step_count = max(1, fade_ms // FADE_STEP_MS)
    step_seconds = fade_ms / step_count / 1000
    for step in range(1, step_count + 1):
        is_last_step = step == step_count
        fraction = step / step_count
        for volume, start, end in plan:
            volume.SetMasterVolume(end if is_last_step else start + (end - start) * fraction, None)
        if not is_last_step:
            time.sleep(step_seconds)
