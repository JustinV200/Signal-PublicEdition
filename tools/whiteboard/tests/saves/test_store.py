"""Saved boards on disk: slugging, overwrite, the round trip with scaling, image bundling."""

import json

import pytest

from whiteboard.display.scene import item_from_dict
from whiteboard.saves import (
    SaveError,
    SaveNotFoundError,
    SaveStore,
    parse_save_request,
    restored_items,
    slugify,
)

# Image items must point under tools/whiteboard/.state/, so each test fakes a repo in tmp_path.
BOARDS = "tools/whiteboard/.state/boards"


def make_store(tmp_path) -> SaveStore:
    return SaveStore(tmp_path / BOARDS, repo_root=tmp_path)


def save(store: SaveStore, body: dict, items=(), images=None, size=(1000, 500)) -> None:
    store.save(parse_save_request(body), list(items), size, images or {})


def test_slugify_makes_safe_capped_folder_names() -> None:
    assert slugify("  Q3 Roadmap: v2!! ") == "q3-roadmap-v2"
    assert slugify("Café ../..\\evil") == "cafe-evil"
    assert slugify("q3-roadmap-v2") == "q3-roadmap-v2"
    assert slugify("CON") == "con-board"
    long_slug = slugify("word " * 40)
    assert len(long_slug) <= 48 and not long_slug.endswith("-")
    with pytest.raises(SaveError):
        slugify("!!! ...")


def test_save_refuses_to_overwrite_unless_asked(tmp_path) -> None:
    store = make_store(tmp_path)
    save(store, {"name": "Plan"})

    with pytest.raises(SaveError, match="overwrite"):
        save(store, {"name": "plan"})

    save(store, {"name": "Plan", "description": "v2", "overwrite": True}, images={"ink.png": b"x"})
    assert [meta["description"] for meta in store.list_saves()] == ["v2"]
    assert store.load("plan").ink_content == f"{BOARDS}/plan/ink.png"


def test_round_trip_scales_items_to_the_current_board(tmp_path) -> None:
    store = make_store(tmp_path)
    item = item_from_dict(
        {"id": "t1", "kind": "text", "x": 100, "y": 50, "w": 200, "h": 40, "content": "hi"}
    )
    save(store, {"name": "Arch diagram", "description": "boxes"}, [item])

    saved = store.load("Arch Diagram")
    same_size = restored_items(saved, (1000, 500), include_ink=True)
    half_width = restored_items(saved, (500, 500), include_ink=True)

    assert saved.meta["name"] == "Arch diagram" and saved.ink_content is None
    assert same_size == (item,)
    assert (half_width[0].x, half_width[0].y, half_width[0].w, half_width[0].h) == (50, 50, 100, 40)
    assert half_width[0].content == "hi"
    store.delete("arch-diagram")
    with pytest.raises(SaveNotFoundError):
        store.load("arch-diagram")


def test_scaling_that_overflows_or_a_tampered_board_size_is_refused(tmp_path) -> None:
    store = make_store(tmp_path)
    huge = item_from_dict(
        {"id": "big", "kind": "text", "x": 0, "y": 0, "w": 1.5e308, "h": 10, "content": "x"}
    )
    save(store, {"name": "huge"}, [huge], size=(100, 100))
    with pytest.raises(SaveError, match="big"):
        restored_items(store.load("huge"), (1000, 1000), include_ink=False)

    meta_path = tmp_path / BOARDS / "huge" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_path.write_text(json.dumps({**meta, "board_size": [1e-300, 1e-300]}), encoding="utf-8")
    with pytest.raises(SaveError, match="board_size"):
        store.load("huge")


def test_resaving_a_loaded_board_keeps_its_old_ink(tmp_path) -> None:
    store = make_store(tmp_path)
    save(store, {"name": "foo"}, images={"ink.png": b"old drawing"})
    # Loading foo projects its ink; the owner then re-saves foo over itself.
    loaded = restored_items(store.load("foo"), (1000, 500), include_ink=True)
    save(store, {"name": "foo", "overwrite": True}, loaded, images={"ink.png": b"new capture"})

    resaved = store.load("foo")
    old_ink = resaved.items[0]
    assert old_ink.content == f"{BOARDS}/foo/images/item-saved-ink-foo.png"
    assert (tmp_path / old_ink.content).read_bytes() == b"old drawing"
    assert (tmp_path / resaved.ink_content).read_bytes() == b"new capture"
    # Both inks come back, the new one under the old one's id and the old one renamed.
    restored = restored_items(resaved, (1000, 500), include_ink=True)
    assert [item.content for item in restored] == [resaved.ink_content, old_ink.content]
    assert len({item.id for item in restored}) == 2


def test_refresher_is_kept_and_an_unknown_one_is_refused_on_save_and_read(tmp_path) -> None:
    store = make_store(tmp_path)
    save(store, {"name": "grid", "refresher": "tasks"})
    assert store.load("grid").meta["refresher"] == "tasks"
    with pytest.raises(SaveError, match="refresher"):
        parse_save_request({"name": "x", "refresher": "rm -rf"})

    meta_path = tmp_path / BOARDS / "grid" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_path.write_text(json.dumps({**meta, "refresher": "shell"}), encoding="utf-8")
    with pytest.raises(SaveError, match="refresher"):
        store.load("grid")
