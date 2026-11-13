"""POST /api/away: on with an end gives away, a bad end writes nothing (400), off gives here.

The brief's state lives in the fixture's tmp folder, never the real one.
"""

import pytest

UNTIL_FUTURE = "2099-01-01"


async def test_away_without_an_end_reports_no_end(console):
    """Regression: the 3-day default end showed as "Away until <now's clock time>"."""
    response = await console.client.post(
        "/api/away", json={"on": True, "until": ""}, headers=console.page_headers()
    )
    body = await response.json()
    assert (body["state"], body["endsAt"]) == ("away", None)


@pytest.mark.parametrize(
    ("body", "status", "state"),
    [
        ({"on": True, "until": UNTIL_FUTURE}, 200, "away"),
        ({"on": True, "until": "not a time"}, 400, None),
        ({"on": True, "until": "2000-01-01"}, 400, None),  # already past
        ({"on": False}, 200, "here"),
    ],
)
async def test_away_toggle(console, body, status, state):
    response = await console.client.post("/api/away", json=body, headers=console.page_headers())
    assert response.status == status
    away_file = console.services.brief_paths.away
    if state is None:
        assert not away_file.exists()  # a refused end writes nothing
    else:
        body_json = await response.json()
        assert body_json["state"] == state
        if state == "away":
            assert body_json["endsAt"] is not None  # a given end still shows as "until"
            assert away_file.exists()  # written to the tmp brief folder
        assert console.services.brief_paths.state_dir.is_relative_to(console.state_dir)
