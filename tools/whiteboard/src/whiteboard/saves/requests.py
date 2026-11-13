"""Parse and validate the JSON bodies of the /api/saves routes into typed requests.

Bodies come from the MCP server and CLI, which pass on whatever the model or
owner typed, so every field is checked here and errors name the field.
"""

from dataclasses import dataclass
from typing import Any

from whiteboard.display.scene import check_keys, require_bool, require_str
from whiteboard.saves.errors import SaveError
from whiteboard.saves.meta import check_refresher
from whiteboard.saves.slug import slugify

MAX_NAME_CHARS = 120
MAX_DESCRIPTION_CHARS = 1000
# replace clears the projected items first; overlay adds the saved ones on top.
LOAD_MODES: tuple[str, ...] = ("replace", "overlay")


@dataclass(frozen=True)
class SaveRequest:
    """What to save: the name, its slug (the folder), a description, overwrite and a refresher."""

    name: str
    slug: str
    description: str = ""
    overwrite: bool = False
    refresher: str | None = None


@dataclass(frozen=True)
class LoadRequest:
    """What to load: the save's slug, whether to clear the board first, and whether to add ink."""

    slug: str
    replace: bool = True
    include_ink: bool = True


def parse_save_request(body: dict[str, Any]) -> SaveRequest:
    """Parse `{name, description?, overwrite?, refresher?}` for POST /api/saves.

    `refresher` is one of meta.REFRESHERS, or "" / null for none.

    Raises:
        SaveError / SceneError: An unknown key, a wrong type, an empty or too-long
            name, a name with no letters or digits, a too-long description, or an
            unknown refresher.
    """
    check_keys(body, ("name", "description", "overwrite", "refresher"), "save request")
    name = parse_name(body)
    description = require_str(body.get("description", ""), "description").strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise SaveError(f"description is longer than {MAX_DESCRIPTION_CHARS} characters")
    overwrite = require_bool(body.get("overwrite", False), "overwrite")
    refresher = check_refresher(body.get("refresher") or None)
    return SaveRequest(name, slugify(name), description, overwrite, refresher)


def parse_load_request(body: dict[str, Any]) -> LoadRequest:
    """Parse `{name, mode?: "replace" | "overlay", include_ink?: bool}` for POST /api/saves/load.

    `name` may be the save's name or its slug; both slug to the same folder.

    Raises:
        SaveError / SceneError: An unknown key, a wrong type, a bad name or an unknown mode.
    """
    check_keys(body, ("name", "mode", "include_ink"), "load request")
    mode = require_str(body.get("mode", "replace"), "mode")
    if mode not in LOAD_MODES:
        raise SaveError(f"mode must be one of {', '.join(LOAD_MODES)}, got {mode!r}")
    include_ink = require_bool(body.get("include_ink", True), "include_ink")
    return LoadRequest(slugify(parse_name(body)), mode == "replace", include_ink)


def parse_name(body: dict[str, Any]) -> str:
    """The body's required `name`, stripped.

    Raises:
        SaveError / SceneError: Missing, not a string, empty, or longer than MAX_NAME_CHARS.
    """
    name = require_str(body.get("name"), "name").strip()
    if not name or len(name) > MAX_NAME_CHARS:
        raise SaveError(f"name must be 1 to {MAX_NAME_CHARS} characters")
    return name
