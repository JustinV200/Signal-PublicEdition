"""Shared test fakes: a Calendar API HTTP session with canned routes, and planted secrets.

No test talks to Google. FakeSession stands in for AuthorizedSession.
"""

from typing import Any

from calendar_tool.google_api import API_BASE

# Planted secrets: tests assert these never show up in any output or error.
SECRET_REFRESH_TOKEN = "1//REFRESH-TOKEN-must-never-leak"
SECRET_CLIENT_SECRET = "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k"


class FakeResponse:
    """A requests.Response stand-in."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FakeSession:
    """Serves GET <path below calendar/v3/> from `routes`.

    A route is a JSON dict, a list of page dicts (served by pageToken, with
    nextPageToken filled in), or an exception to raise. Unknown paths answer 404.
    """

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        path = url.removeprefix(API_BASE)
        params = kwargs.get("params") or {}
        self.calls.append((path, params))
        outcome = self.routes.get(path)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            return FakeResponse(404, {"error": {"message": "Not Found"}})
        if isinstance(outcome, list):
            index = int(params.get("pageToken", 0))
            page = dict(outcome[index])
            if index + 1 < len(outcome):
                page["nextPageToken"] = str(index + 1)
            return FakeResponse(200, page)
        return FakeResponse(200, outcome)
