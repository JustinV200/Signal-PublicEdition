"""Shared test fakes: a Calendar API HTTP session with canned routes, the owner's dialog, secrets.

No test talks to Google. FakeSession stands in for AuthorizedSession, FakeOwner
for signal_confirm.confirm.
"""

from dataclasses import dataclass
from typing import Any

from calendar_tool.google_api import API_BASE

# Planted secrets: tests assert these never show up in any output or error.
SECRET_REFRESH_TOKEN = "1//REFRESH-TOKEN-must-never-leak"
SECRET_CLIENT_SECRET = "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k"


class FakeResponse:
    """A requests.Response stand-in."""

    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


@dataclass(frozen=True)
class FakeCall:
    """One request the client sent."""

    method: str
    path: str
    params: dict[str, Any]
    body: Any
    headers: dict[str, str]


class FakeSession:
    """Serves requests from `routes`, keyed by a path (GET) or a (method, path) pair.

    A route is a JSON dict, a list of page dicts (served by pageToken, with
    nextPageToken filled in), a FakeResponse, or an exception to raise. Unknown
    routes answer 404.
    """

    def __init__(self, routes: dict[Any, Any]) -> None:
        self.routes = routes
        self.calls: list[FakeCall] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        path = url.removeprefix(API_BASE)
        params = kwargs.get("params") or {}
        self.calls.append(
            FakeCall(method, path, params, kwargs.get("json"), kwargs.get("headers") or {})
        )
        outcome = self.routes.get((method, path))
        if outcome is None and method == "GET":
            outcome = self.routes.get(path)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, FakeResponse):
            return outcome
        if outcome is None:
            return FakeResponse(404, {"error": {"message": "Not Found"}})
        if isinstance(outcome, list):
            index = int(params.get("pageToken", 0))
            page = dict(outcome[index])
            if index + 1 < len(outcome):
                page["nextPageToken"] = str(index + 1)
            return FakeResponse(200, page)
        return FakeResponse(200, outcome)

    def writes(self) -> list[FakeCall]:
        """Every request that wasn't a GET."""
        return [call for call in self.calls if call.method != "GET"]


class FakeOwner:
    """The owner's Allow/Deny dialog: records each question and gives a fixed answer."""

    def __init__(self, is_allowed: bool) -> None:
        self.is_allowed = is_allowed
        self.questions: list[str] = []

    def __call__(self, title: str, message: str, *, timeout_s: float) -> bool:
        self.questions.append(message)
        return self.is_allowed
