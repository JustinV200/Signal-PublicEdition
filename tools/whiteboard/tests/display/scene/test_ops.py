"""Tests for the pure scene ops and the item parsing they rely on."""

import pytest

from whiteboard.display.scene import (
    ItemNotFoundError,
    Scene,
    SceneError,
    SceneStore,
    clear_items,
    item_from_dict,
    parse_quad,
    patch_item,
    remove_item,
    set_board_quad,
    upsert_item,
)


def _item(item_id: str, **overrides: object):
    data = {"id": item_id, "kind": "text", "x": 10, "y": 20, "w": 100, "h": 50, "content": "hi"}
    return item_from_dict({**data, **overrides})


def test_upsert_appends_new_and_replaces_existing_in_place() -> None:
    scene = upsert_item(upsert_item(Scene(), _item("a")), _item("b"))
    replaced = upsert_item(scene, _item("a", content="new"))
    assert [item.id for item in replaced.items] == ["a", "b"]
    assert replaced.items[0].content == "new"
    assert scene.items[0].content == "hi", "the input scene must not change"


def test_patch_moves_and_merges_style_but_keeps_identity() -> None:
    scene = upsert_item(Scene(), _item("a", style={"color": "#ff0", "opacity": 0.5}))
    patched = patch_item(scene, "a", {"x": 99, "style": {"color": "#0f0"}})
    item = patched.items[0]
    assert (item.x, item.style.color, item.style.opacity) == (99, "#0f0", 0.5)
    assert item.created_at == scene.items[0].created_at
    with pytest.raises(SceneError):
        patch_item(scene, "a", {"kind": "svg"})


def test_remove_and_missing_ids() -> None:
    scene = upsert_item(Scene(), _item("a"))
    assert remove_item(scene, "a").items == ()
    with pytest.raises(ItemNotFoundError):
        remove_item(scene, "zzz")
    with pytest.raises(ItemNotFoundError):
        patch_item(scene, "zzz", {"x": 1})


def test_clear_keeps_board_fit() -> None:
    quad = parse_quad([[100, 50], [1200, 60], [1180, 700], [90, 690]])
    scene = set_board_quad(upsert_item(Scene(), _item("a")), quad)
    cleared = clear_items(scene)
    assert cleared.items == () and cleared.board_quad == quad


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "video"},
        {"w": 0},
        {"x": float("nan")},
        {"x": True},
        {"id": "has space"},
        {"style": {"color": "red; background: url(x)"}},
        {"style": {"opacity": 2}},
        {"bogus": 1},
        {"kind": "rough", "content": '[{"shape": "star"}]'},
        {"kind": "image", "content": "../../outside.png"},
    ],
)
def test_bad_items_are_rejected(overrides: dict) -> None:
    with pytest.raises(SceneError):
        _item("a", **overrides)


def test_generated_id_and_rough_list_content() -> None:
    item = item_from_dict(
        {
            "kind": "rough",
            "x": 0,
            "y": 0,
            "w": 10,
            "h": 10,
            "content": [{"shape": "line", "x1": 0, "y1": 0, "x2": 5, "y2": 5}],
        }
    )
    assert item.id.startswith("rough-")
    assert item.content == '[{"shape":"line","x1":0,"y1":0,"x2":5,"y2":5}]'


def test_store_round_trip_and_corrupt_file(tmp_path) -> None:
    store = SceneStore(tmp_path / "scene.json")
    scene = set_board_quad(
        upsert_item(Scene(), _item("a")), parse_quad([[0, 0], [10, 0], [10, 10], [0, 10]])
    )
    store.save(scene)
    assert store.load() == scene

    store.path.write_text("{not json", encoding="utf-8")
    assert store.load() == Scene()
    assert (tmp_path / "scene.json.bad").read_text(encoding="utf-8") == "{not json"
