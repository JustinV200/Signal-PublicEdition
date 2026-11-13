"""Errors for saved whiteboards, mapped onto the scene errors the API already turns into HTTP codes.

display's json_errors middleware answers SceneError with 400 and
ItemNotFoundError with 404, so subclassing them gives the /api/saves routes the
same `{ok: false, error}` replies without another middleware.
"""

from whiteboard.display.scene import ItemNotFoundError, SceneError


class SaveError(SceneError):
    """A bad save name or request, an unreadable save, or a save that already exists (HTTP 400)."""


class SaveNotFoundError(ItemNotFoundError):
    """No saved board has that name (HTTP 404)."""
