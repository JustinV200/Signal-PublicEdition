"""Copy the image files a saved scene points at into the save itself.

Image items only hold a path under .state/. Saving that path alone breaks in two
ways: re-saving a loaded board over itself replaces the ink.png its ink item
points at with a fresh capture (taken with the projection blanked, so without the
old drawing), and a projected snapshot is pruned from .state/snapshots/ later.
So each image item's file is copied into the save's images/ folder and the item
is pointed at the copy, before the save folder is renamed into place.
"""

import shutil
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from whiteboard.display.scene import (
    Item,
    SceneError,
    item_from_dict,
    item_to_dict,
    resolve_image_path,
)

IMAGES_DIR = "images"
# Prefixing the id keeps a file name like "nul.png" (a Windows device) impossible.
_FILE_PREFIX = "item-"


def bundle_images(
    items: Sequence[Item], temp_folder: Path, final_prefix: str, repo_root: Path
) -> tuple[Item, ...]:
    """Copy every image item's file into temp_folder/images/ and repoint the item at it.

    Args:
        items: The scene items being saved.
        temp_folder: The save's temp folder, where the copies are written.
        final_prefix: The save folder's repo-relative path once it is renamed into
            place, e.g. "tools/whiteboard/.state/boards/foo".
        repo_root: What image item paths are relative to.

    Returns:
        The items, with image items pointing at their copies (rebuilt through the
        scene parser, so the new path is validated like any other).

    Raises:
        OSError: A copy can't be written.
    """
    return tuple(_bundle_one(item, temp_folder, final_prefix, repo_root) for item in items)


def _bundle_one(item: Item, temp_folder: Path, final_prefix: str, repo_root: Path) -> Item:
    """One item: copied and repointed if it's an image whose file still exists."""
    if item.kind != "image":
        return item
    try:
        source = resolve_image_path(item.content, repo_root)
    except SceneError:
        # The file is already gone; loading leaves such items out and reports their ids.
        return item
    # The suffix comes from the validated path, not the resolved file a link may lead to.
    file_name = f"{_FILE_PREFIX}{item.id}{PurePosixPath(item.content).suffix.lower()}"
    (temp_folder / IMAGES_DIR).mkdir(exist_ok=True)
    shutil.copyfile(source, temp_folder / IMAGES_DIR / file_name)
    content = f"{final_prefix}/{IMAGES_DIR}/{file_name}"
    return item_from_dict({**item_to_dict(item), "content": content})
