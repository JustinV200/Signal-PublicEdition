"""Model-facing text for the audiohub MCP server: server instructions and tool descriptions.

A calling model sees only these strings, so each description says what the
tool does, when to reach for it, what its arguments mean and what it returns.
Kept apart from the registration code so wording can be tuned in one place.
"""

SERVER_INSTRUCTIONS = (
    "audiohub is the user's voice hub on this Windows PC. The user wears Bluetooth audio "
    "glasses; anything sent with `notify` is spoken into their ears in a British voice, after "
    "the hub's kernel orders it against other agents' messages. The music_* tools control "
    "the music playing on this PC (Spotify, falling back to Windows media controls)."
)

NOTIFY = """Say something out loud to the user through their glasses, via the audiohub voice hub.

Use it when the user should hear something without looking at the screen: a long task
finished or failed, you need their input or a decision, or something urgent came up.
If you are already talking with the user by voice, your replies are spoken anyway; use
this only for messages outside your normal reply.

Write for the ear: one or two short, plain sentences. No markdown, code, file paths, URLs
or long lists. The hub may queue a message briefly so it doesn't talk over another one,
and shortens only text that is too long to listen to.

Args:
    text: What the user should hear.
    priority: "urgent" (needs them right now, e.g. a failure blocking work), "high",
        "normal" (default) or "low" (nice to know; may wait until the user is free).
    source: Short name for who is speaking, e.g. "build-agent". Default "claude-code".

Returns a confirmation with the message id. If the voice hub isn't running, says the
message was not delivered: the user did not hear it, so tell them another way. While the
user is asleep or away the hub drops the message unspoken and says so ("dropped: the owner
is asleep"); don't resend it."""

MUSIC_NOW_PLAYING = """Find out what music is playing on this PC right now.

Use it when the user asks what song this is, or to check the current track before
changing playback. Returns the title, artist and album, and whether it is playing or
paused, or says nothing is playing."""

MUSIC_PLAY = """Resume music playback on this PC.

Use it when the user asks to play, resume or unpause the music. To start a particular
song, album, playlist or artist, use music_search_and_play instead, and for the user's
Liked Songs, music_play_liked."""

MUSIC_PAUSE = """Pause the music playing on this PC.

Use it when the user asks to pause or stop the music."""

MUSIC_NEXT = """Skip to the next track.

Use it when the user asks to skip this song or play the next one."""

MUSIC_PREVIOUS = """Go back to the previous track.

Use it when the user asks for the last song again or to go back a track."""

MUSIC_SET_VOLUME = """Set Spotify's playback volume.

Use it when the user asks to turn the music up or down or to a specific level. This is
Spotify's own volume, separate from the Windows volume. Needs Spotify Premium and a login.

Args:
    percent: Whole number from 0 (silent) to 100 (full volume)."""

MUSIC_SEARCH_AND_PLAY = """Search Spotify and start playing the best match right away.

Use it when the user names something to play, e.g. "play Bohemian Rhapsody" or "put on
some Miles Davis". Never use it for the user's own Liked Songs (search only finds other
people's playlists with that name); use music_play_liked. Needs Spotify Premium and a login.

Args:
    query: What to search for, e.g. a song title with or without the artist.
    kind: "track" (default), "album", "playlist" or "artist".

Returns what started playing."""

MUSIC_PLAY_LIKED = """Play the user's own Spotify Liked Songs (their saved tracks).

Use it when the user asks for "my liked songs", "my likes", "my saved songs" or "my
library", e.g. "play my liked songs" or "shuffle my liked songs". Needs Spotify Premium
and a login.

Args:
    shuffle: true to shuffle (e.g. "shuffle my liked songs"), false to play in order,
        or leave it out to keep the current shuffle setting.

Returns what started playing."""

MUSIC_QUEUE = """Search Spotify for a track and add the best match to the play queue.

Use it when the user says "play X next", "queue X" or "add X after this song". The
current song keeps playing. Needs Spotify Premium and a login.

Args:
    query: The track to search for, e.g. a song title with or without the artist.

Returns what was queued."""
