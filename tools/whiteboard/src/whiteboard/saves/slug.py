"""Turn an owner-given board name ("Q3 roadmap!") into a safe folder name ("q3-roadmap").

The slug is the save's folder under .state/boards/ and part of its ink item id,
so it is kept to lowercase a-z, 0-9 and '-', and capped in length.
"""

import re
import unicodedata

from whiteboard.saves.errors import SaveError

MAX_SLUG_CHARS = 48
_NOT_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
# Windows opens these as devices in any folder, so they can't be folder names.
_DEVICE_NAMES = re.compile(r"con|prn|aux|nul|com\d|lpt\d")
DEVICE_NAME_SUFFIX = "-board"


def slugify(name: str) -> str:
    """Make the folder-safe slug for a board name. A valid slug comes back unchanged.

    Accents are folded to ASCII ("Café" -> "cafe"); every other run of characters
    outside a-z and 0-9 becomes one '-'.

    Args:
        name: The board's name, as the owner gave it.

    Returns:
        1 to MAX_SLUG_CHARS (plus a device-name suffix) characters of [a-z0-9-],
        never starting or ending with '-'.

    Raises:
        SaveError: If the name has no letters or digits at all.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = _NOT_SLUG_CHARS.sub("-", ascii_name.lower()).strip("-")
    slug = slug[:MAX_SLUG_CHARS].rstrip("-")
    if not slug:
        raise SaveError(f"board name {name[:80]!r} needs at least one letter or digit")
    if _DEVICE_NAMES.fullmatch(slug):
        slug += DEVICE_NAME_SUFFIX
    return slug
