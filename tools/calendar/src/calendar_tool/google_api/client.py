"""CalendarClient: JSON requests against the Google Calendar v3 REST API.

Every library failure becomes a CalendarError with a fixed, secret-free
message: refresh failures (invalid_grant means "re-run calendar add"),
network errors, and the API's own error responses. Writes need a client built
with can_write (a sign-in holding the write scope); without it they fail before
any request with "Re-run `calendar add`". The session is an AuthorizedSession
in production and a fake in tests. Same approach as tools/mail's GmailClient.
"""

import re
from typing import Any, Protocol

import requests
from google.auth.exceptions import RefreshError, TransportError

from calendar_tool.errors import ApiError, CalendarError, OfflineError, ReauthRequired

API_BASE = "https://www.googleapis.com/calendar/v3/"
REQUEST_TIMEOUT_S = 30
MAX_ERROR_CHARS = 300
# A runaway nextPageToken loop stops here; 250 items a page is far more than 14 days needs.
MAX_PAGES = 20
# OAuth error codes are short snake_case words such as invalid_grant or invalid_client.
_OAUTH_ERROR_CODE = re.compile(r"[a-z_]{1,64}")
HTTP_NO_CONTENT = 204
HTTP_FORBIDDEN = 403
HTTP_PRECONDITION_FAILED = 412
# Google's 403 text when the access token lacks a scope (a read-only sign-in writing).
_SCOPE_MISSING_TEXT = "insufficient authentication scopes"
READ_ONLY_SIGN_IN = "This calendar sign-in is read-only (saved before the tool could change events)"


class HttpResponse(Protocol):
    """The part of requests.Response the client reads."""

    status_code: int

    def json(self) -> Any: ...


class HttpSession(Protocol):
    """The part of requests.Session (AuthorizedSession) the client calls."""

    def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse: ...


class CalendarClient:
    """Thin JSON client for https://www.googleapis.com/calendar/v3/."""

    def __init__(self, session: HttpSession, can_write: bool = True) -> None:
        """Args: session: sends authorized requests; can_write: the sign-in has the write scope."""
        self._session = session
        self.can_write = can_write

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET calendar/v3/<path> and return the JSON object.

        Raises:
            ReauthRequired, OfflineError, ApiError, CalendarError: See the module docstring.
        """
        return self.send("GET", path, params)

    def send(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        """Send one request and return its JSON object ({} for 204 No Content).

        Args:
            method: GET, POST, PATCH or DELETE.
            path: Below calendar/v3/, already URL-quoted.
            params: Query parameters.
            body: The JSON body, if any.
            etag: Sent as If-Match, so a write to an event that changed since it was read fails.

        Raises:
            ReauthRequired: A write without the write scope, or a revoked sign-in.
            OfflineError, ApiError, CalendarError: See the module docstring.
        """
        if method != "GET" and not self.can_write:
            raise ReauthRequired(READ_ONLY_SIGN_IN)
        extra: dict[str, Any] = {} if body is None else {"json": body}
        if etag:
            extra["headers"] = {"If-Match": etag}
        # from None below: library exceptions may hold the token request/response.
        try:
            response = self._session.request(
                method, API_BASE + path, params=params, timeout=REQUEST_TIMEOUT_S, **extra
            )
        except RefreshError as error:
            raise _refresh_failure(error) from None
        except (TransportError, requests.RequestException) as error:
            raise OfflineError(f"Can't reach Google ({type(error).__name__}).") from None
        return _parse(response)

    def get_all_items(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """GET every page of a list endpoint and return the "items" of all of them.

        Raises:
            As get(), plus ApiError when "items" isn't a list of objects.
        """
        items: list[dict[str, Any]] = []
        page_params = dict(params)
        for _ in range(MAX_PAGES):
            page = self.get(path, page_params)
            page_items = page.get("items", [])
            if not isinstance(page_items, list):
                raise ApiError("The Calendar API sent 'items' that isn't a list.")
            items.extend(item for item in page_items if isinstance(item, dict))
            token = page.get("nextPageToken")
            if not isinstance(token, str) or not token:
                return items
            page_params["pageToken"] = token
        return items


def _refresh_failure(error: RefreshError) -> CalendarError:
    """Map a token refresh failure to a re-auth or plain message (codes only, no details)."""
    reason = str(error.args[0]) if error.args else ""
    code = reason.split(":", 1)[0].strip()
    if code == "invalid_grant":
        return ReauthRequired("Google revoked or expired the calendar sign-in")
    if code == "invalid_scope":
        return ReauthRequired("Google refused the calendar sign-in's scopes")
    if not _OAUTH_ERROR_CODE.fullmatch(code):
        code = "unknown error"
    return CalendarError(f"Couldn't refresh the Google sign-in ({code}).")


def _parse(response: HttpResponse) -> dict[str, Any]:
    """Return the JSON object body, or raise for an error status or bad body."""
    if response.status_code == HTTP_NO_CONTENT:
        return {}
    try:
        data = response.json()
    except ValueError:
        data = None
    if response.status_code >= 400:
        raise _status_error(response.status_code, _error_message(data))
    if not isinstance(data, dict):
        raise ApiError("The Calendar API sent a response that isn't a JSON object.")
    return data


def _status_error(status: int, message: str) -> CalendarError:
    """The error for an error status: a missing scope and a stale event get their own words."""
    if status == HTTP_FORBIDDEN and _SCOPE_MISSING_TEXT in message.lower():
        return ReauthRequired(READ_ONLY_SIGN_IN)
    if status == HTTP_PRECONDITION_FAILED:
        return ApiError("The event changed since it was read, so nothing was changed. Try again.")
    return ApiError(f"Calendar API error {status}: {message}")


def _error_message(data: object) -> str:
    """The API's error.message, capped; it describes the request, never credentials."""
    error = data.get("error") if isinstance(data, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return str(message)[:MAX_ERROR_CHARS] if message else "no details"
