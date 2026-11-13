"""Persist the scene to `.state/scene.json` so the board comes back the same after a restart."""

import json
import logging
import os
from pathlib import Path

from whiteboard.display.scene.model import IDLE_VIEW, ITEMS_VIEW, Scene, SceneError, scene_to_dict
from whiteboard.display.scene.parse import scene_from_dict
from whiteboard.shared import write_atomically

log = logging.getLogger(__name__)

# A scene file that fails to load is moved aside with this suffix, not overwritten.
BAD_FILE_SUFFIX = ".bad"


class SceneStore:
    """Loads and saves one scene JSON file."""

    def __init__(self, path: Path) -> None:
        """Args:
        path: The scene file, usually STATE_DIR / "scene.json". Its folder is created on save.
        """
        self.path = path

    def load(self) -> Scene:
        """Read the saved scene, or an empty one if there is no file yet.

        A corrupt or invalid file is renamed to `scene.json.bad` (keeping the
        owner's data for inspection) and an empty scene is returned, so a bad
        file can't stop the daemon from starting.

        Returns:
            The saved Scene, or an empty Scene.

        Raises:
            OSError: If the file exists but can't be read or moved aside.
        """
        if not self.path.is_file():
            return Scene()
        try:
            return scene_from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError, SceneError) as error:
            bad_path = self.path.with_name(self.path.name + BAD_FILE_SUFFIX)
            os.replace(self.path, bad_path)
            log.warning(
                "scene file %s is invalid (%s); moved to %s, starting empty",
                self.path,
                error,
                bad_path,
            )
            return Scene()

    def save(self, scene: Scene) -> None:
        """Write the scene atomically (temp file + rename), so a crash never leaves half a file.

        Raises:
            OSError: If the folder or file can't be written.
        """
        data = scene_to_dict(scene)
        # Outside the night view, leave `night` out: code from before it rejects the key
        # and would move an ordinary scene.json aside (a rollback must keep the items).
        # A rollback while the night view shows still moves it aside; that can't be
        # helped, since older code knows no night view at all.
        if data["night"] is None:
            del data["night"]
        # The idle view is saved as the items for the same reason: older code rejects it.
        # Nothing is lost, since it's a default the daemon's rule brings back by itself.
        elif data["night"]["previous_view"] == IDLE_VIEW:
            data["night"]["previous_view"] = ITEMS_VIEW
        if data["view"] == IDLE_VIEW:
            data["view"] = ITEMS_VIEW
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(self.path, json.dumps(data, indent=1).encode("utf-8"))
