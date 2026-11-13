"""SaveStore: saved whiteboards as folders under .state/boards/<slug>/.

Each folder holds:
- meta.json: name, slug, description, created_at (UTC ISO), item_count, board_size [w, h]
  (the board pixel size the items and photo were captured at), has_ink, and refresher
  when the save has one (see meta.py).
- scene.json: a copy of the projected items, in the scene.json format.
- images/: copies of the files the image items point at (see bundle.py).
- photo.png and ink.png: the clean board photo and the owner's extracted strokes,
  only when the camera was calibrated at save time.

A save is written to a hidden temp folder first and renamed into place, so a
failed save never leaves half a folder or destroys the save it was replacing.
"""

import json
import logging
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from whiteboard.config import REPO_ROOT
from whiteboard.display.scene import Item, Scene, scene_from_dict, scene_to_dict
from whiteboard.saves.bundle import bundle_images
from whiteboard.saves.errors import SaveError, SaveNotFoundError
from whiteboard.saves.meta import META_FILE, read_meta
from whiteboard.saves.requests import SaveRequest
from whiteboard.saves.slug import slugify

log = logging.getLogger(__name__)

SCENE_FILE = "scene.json"
PHOTO_FILE = "photo.png"
INK_FILE = "ink.png"
# Slugs never start with '.', so a temp folder can't collide with a save.
_TEMP_PREFIX = ".saving-"


@dataclass(frozen=True)
class SavedBoard:
    """One save read back from disk.

    Attributes:
        meta: The validated meta.json.
        items: The saved projected items, validated like scene.json.
        board_size: (width, height) in board pixels at save time.
        ink_content: ink.png as a repo-relative path for an image item, or None if
            the save has no ink.
    """

    meta: dict[str, Any]
    items: tuple[Item, ...]
    board_size: tuple[float, float]
    ink_content: str | None


class SaveStore:
    """Writes, reads, lists and deletes saved boards in one folder."""

    def __init__(self, root: Path, repo_root: Path = REPO_ROOT) -> None:
        """Args:
        root: The boards folder, usually STATE_DIR / "boards". Created on first save.
            It must be inside repo_root's .state/, where image items may point.
        repo_root: What image item paths are relative to.
        """
        self.root = root
        self._repo_root = repo_root

    def require_free(self, slug: str, overwrite: bool) -> None:
        """Refuse a save whose slug is taken, unless overwrite is set.

        Raises:
            SaveError: A save with this slug exists and overwrite is False.
        """
        if not overwrite and (self.root / slug).exists():
            raise SaveError(
                f"a saved board named {slug!r} already exists; pass overwrite=true to replace it"
            )

    def save(
        self,
        request: SaveRequest,
        items: Sequence[Item],
        board_size: tuple[float, float],
        images: Mapping[str, bytes],
    ) -> dict[str, Any]:
        """Write one save folder (replacing an old one only if request.overwrite).

        Args:
            request: Name, slug, description and overwrite.
            items: The projected items to keep. Image items' files are copied in.
            board_size: (width, height) of the board the items are placed on.
            images: {PHOTO_FILE: png, INK_FILE: png}, or {} for a scene-only save.

        Returns:
            The meta written to meta.json.

        Raises:
            SaveError: The slug is taken and overwrite is False.
            OSError: The folder can't be written.
            ValueError: root isn't inside repo_root.
        """
        self.require_free(request.slug, request.overwrite)
        meta = {
            "name": request.name,
            "slug": request.slug,
            "description": request.description,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "item_count": len(items),
            "board_size": list(board_size),
            "has_ink": INK_FILE in images,
        }
        if request.refresher is not None:
            meta["refresher"] = request.refresher
        final_folder = self.root / request.slug
        temp_folder = self.root / f"{_TEMP_PREFIX}{request.slug}"
        if temp_folder.exists():
            # Left over from a save that crashed part-way.
            shutil.rmtree(temp_folder)
        temp_folder.mkdir(parents=True)
        # Copied before the old folder goes, so a loaded board's own ink survives a re-save.
        final_prefix = final_folder.relative_to(self._repo_root).as_posix()
        items = bundle_images(items, temp_folder, final_prefix, self._repo_root)
        scene = scene_to_dict(Scene(items=items))
        # A save never holds a night view; leave the key out, as SceneStore.save does,
        # so older code can still load the board.
        del scene["night"]
        files = {META_FILE: _json_bytes(meta), SCENE_FILE: _json_bytes(scene), **images}
        for file_name, data in files.items():
            (temp_folder / file_name).write_bytes(data)
        if final_folder.exists():
            shutil.rmtree(final_folder)
        os.replace(temp_folder, final_folder)
        return meta

    def load(self, slug: str) -> SavedBoard:
        """Read one save.

        Raises:
            SaveNotFoundError: No save has this slug.
            SaveError: Its meta.json or scene.json is unreadable or invalid.
        """
        folder = self._existing_folder(slug)
        meta = read_meta(folder)
        try:
            scene = scene_from_dict(json.loads((folder / SCENE_FILE).read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            # ValueError covers bad JSON and SceneError (an invalid item).
            raise SaveError(f"saved board {slug!r} has an unreadable scene: {error}") from error
        ink_path = folder / INK_FILE
        ink_content = (
            ink_path.relative_to(self._repo_root).as_posix() if ink_path.is_file() else None
        )
        width, height = meta["board_size"]
        return SavedBoard(meta, scene.items, (width, height), ink_content)

    def list_saves(self) -> list[dict[str, Any]]:
        """Every readable save's meta, newest first. Unreadable folders are logged and skipped."""
        if not self.root.is_dir():
            return []
        metas = []
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.name.startswith(_TEMP_PREFIX):
                continue
            try:
                metas.append(read_meta(folder))
            except SaveError as error:
                log.warning("skipping saved board folder %s: %s", folder, error)
        return sorted(metas, key=lambda meta: meta["created_at"], reverse=True)

    def delete(self, slug: str) -> dict[str, Any]:
        """Delete one save and return the meta it had.

        Raises:
            SaveNotFoundError: No save has this slug.
            OSError: The folder can't be removed.
        """
        folder = self._existing_folder(slug)
        try:
            meta = read_meta(folder)
        except SaveError:
            # A broken save can still be deleted.
            meta = {"slug": slug}
        shutil.rmtree(folder)
        return meta

    def _existing_folder(self, slug: str) -> Path:
        """The save's folder, after re-slugging so no caller can reach outside root."""
        folder = self.root / slugify(slug)
        if not folder.is_dir():
            raise SaveNotFoundError(f"no saved board named {slug!r}; board_saves lists them")
        return folder


def _json_bytes(data: Mapping[str, Any]) -> bytes:
    """Readable UTF-8 JSON for the files in a save folder."""
    return json.dumps(data, indent=1).encode("utf-8")
