"""Model-facing text for the sleepmode MCP server: server instructions and tool descriptions.

A calling model (often the voice brain) sees only these strings, so each says
what the tool does, which phrasings it's for, and what the arguments mean.
"""

SERVER_INSTRUCTIONS = (
    "sleepmode is the owner's sleep mode on this Windows PC. It darkens every monitor, turns "
    "the RGB lights off and puts a dim night sky on the whiteboard projector, while the PC and "
    "every agent keep running. "
    "It never sleeps, hibernates or logs off the PC. The screens come back at the wake time, "
    'when the owner asks ("good morning"), or when the owner uses the keyboard or mouse '
    "(media keys, such as a headset's pause, don't count)."
)

SLEEP_MODE_ON = """Turn sleep mode on: monitors off (or black), RGB lights off, a night sky on the
projector.

Use it for "sleep mode", "goodnight", "sleep mode until 7", "lights out". Calling it again while
sleep mode is on updates it (e.g. a new wake time). The night sky always shows; there's no
black option.

Args:
    wake_at: When the screens come back, e.g. "07:00", "7am", "6:30" or an ISO date-time like
        "2026-10-20T07:00". A clock time means its next occurrence. "" sets no wake time, or,
        while sleep mode is already on, keeps the one that's set.

Returns what happened to each display and the lights, the wake time, and any problems (e.g. the
projector is black while it waits for the whiteboard, which sleep mode starts and repairs by
itself)."""

SLEEP_MODE_OFF = """Turn sleep mode off: the monitors, the RGB lights and the projector's usual
view come back.

Use it for "good morning", "wake up the screens", "sleep mode off". It's safe to call when sleep
mode is already off. Returns a sentence, plus anything that didn't come back (e.g. a monitor
that needs its power button)."""

SLEEP_MODE_STATUS = """Say whether sleep mode is on, until when, and what each display is doing.

Use it for "is sleep mode on?", "when do the screens wake?". Read-only."""
