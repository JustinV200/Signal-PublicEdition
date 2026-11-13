"""short_title: plan noise dropped, long lines cut at a clause break, short ones kept."""

import pytest

from whiteboard.todo.view import short_title


@pytest.mark.parametrize(
    ("text", "title"),
    [
        # Source tag and long tail dropped; cut at the first comma.
        (
            "Lab 2 linked list insertion, push to the course repo Labs/Lab2 (site)",
            "Lab 2 linked list insertion",
        ),
        # Short enough after the tag goes: the colon stays.
        ("A25 Graphs: Traversal Part 2 (mail)", "A25 Graphs: Traversal Part 2"),
        # A long file list in parentheses goes wherever it sits.
        (
            "Lab 3 binary search trees (tree.c, tree.h, .out files), push to the course repo",
            "Lab 3 binary search trees",
        ),
        (
            "6. Course Project Demo Recording: slides + live walkthrough, team notes",
            "6. Course Project Demo Recording",
        ),
        # Several trailing notes and tags.
        (
            "Practice Quiz and Study Notes (confirmed by email 2026-10-20) (mail)",
            "Practice Quiz and Study Notes",
        ),
        # A head under 20 characters isn't cut at its break: a later break that keeps
        # 20-40 is used, else a word cut with an ellipsis.
        (
            "Check A3, A5, A7, A9 in Classroom: not marked Completed (A9 was due 2026-10-16)",
            "Check A3, A5, A7, A9 in Classroom",
        ),
        (
            "Group project: pick a topic with your team and add it to the shared sheet",
            "Group project: pick a topic with your…",
        ),
        (
            "Quiz 1, makeup session moved to Wed 2026-10-14, Room 101 (mail)",
            "Quiz 1, makeup session moved to Wed…",
        ),
        # A short note that isn't a source tag stays; short text is untouched.
        ("Guest speaker in class (attend)", "Guest speaker in class (attend)"),
        ("Quiz 1, 20 pts", "Quiz 1, 20 pts"),
        # Struck-through done parts go; all struck leaves nothing.
        ("~~Reading 1 video~~ done 2026-10-09. Quiz 1 moved", "Quiz 1 moved"),
        ("~~Renew library card~~ done 2026-10-22", ""),
    ],
)
def test_short_title(text: str, title: str) -> None:
    assert short_title(text) == title
