"""GmailClient: GET/POST JSON against the Gmail REST API for one signed-in account.

Every library failure becomes a MailError with a fixed, secret-free message:
refresh failures (invalid_grant means "re-run mail add"), network errors, and
Gmail's own error responses. GETs (idempotent) are retried a few times on
rate limits, Gmail 5xx answers and network errors; POSTs never are, so a send
can't go out twice. The session is an AuthorizedSession in production
and a fake in tests.
"""

import re
import time
from typing import Any, Protocol

import requests
from google.auth.exceptions import RefreshError, TransportError

from mail_tool.errors import GmailError, GmailNotFound, MailError, OfflineError, ReauthRequired

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me/"
REQUEST_TIMEOUT_S = 30
MAX_ERROR_CHARS = 300
MAX_SHOWN_ID_CHARS = 80
# Wait before each GET retry (so 3 attempts in all); a Retry-After header can lengthen it.
RETRY_DELAYS_S = (1.0, 2.0)
MAX_RETRY_AFTER_S = 10.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
NOT_FOUND = 404
# Gmail ids are hex; draft ids look like "r-123...". Anything else could rewrite the URL path.
_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")
# OAuth error codes are short snake_case words such as invalid_grant or invalid_client.
_OAUTH_ERROR_CODE = re.compile(r"[a-z_]{1,64}")


class HttpResponse(Protocol):
    """The part of requests.Response the client reads."""

    status_code: int

    def json(self) -> Any: ...


class HttpSession(Protocol):
    """The part of requests.Session (AuthorizedSession) the client calls."""

    def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse: ...


def checked_id(value: str, kind: str) -> str:
    """Return a Gmail message/thread/draft id unchanged, or refuse it.

    Raises:
        GmailError: It isn't 1-128 letters, digits, '-' or '_'.
    """
    if not _ID_PATTERN.fullmatch(value):
        raise GmailError(f"Invalid Gmail {kind} id {value[:MAX_SHOWN_ID_CHARS]!r}.")
    return value


class GmailClient:
    """Thin JSON client for https://gmail.googleapis.com/gmail/v1/users/me/."""

    def __init__(self, session: HttpSession, alias: str) -> None:
        """Args: session: sends authorized requests; alias: names the account in errors."""
        self._session = session
        self._alias = alias

    def get(
        self, path: str, params: dict[str, Any] | None = None, retry: bool = True
    ) -> dict[str, Any]:
        """GET users/me/<path>; retry=False makes one attempt (a quick status probe).

        Raises:
            ReauthRequired, OfflineError, GmailError, MailError: See module docstring.
            GmailNotFound: Gmail answered 404.
        """
        for delay_s in RETRY_DELAYS_S if retry else ():
            try:
                response = self._send("GET", path, params=params)
            except OfflineError:
                time.sleep(delay_s)
                continue
            if response.status_code not in RETRY_STATUSES:
                return _parse(response)
            time.sleep(_retry_after(response, delay_s))
        return _parse(self._send("GET", path, params=params))

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST a JSON body to users/me/<path>. Raises as get() does."""
        return _parse(self._send("POST", path, json=body))

    def _send(self, method: str, path: str, **kwargs: Any) -> HttpResponse:
        url = API_BASE + path
        # from None below: library exceptions may hold the token request/response.
        try:
            response = self._session.request(method, url, timeout=REQUEST_TIMEOUT_S, **kwargs)
        except RefreshError as error:
            raise _refresh_failure(self._alias, error) from None
        except (TransportError, requests.RequestException) as error:
            raise OfflineError(f"Can't reach Google ({type(error).__name__}).") from None
        return response


def _retry_after(response: HttpResponse, default_s: float) -> float:
    """Seconds to wait before a retry: Retry-After (whole seconds, capped) or default_s."""
    # getattr: headers aren't part of HttpResponse (test fakes leave them out).
    value = str((getattr(response, "headers", None) or {}).get("Retry-After", ""))
    return min(float(value), MAX_RETRY_AFTER_S) if value.isdigit() else default_s


def _refresh_failure(alias: str, error: RefreshError) -> MailError:
    """Map a token refresh failure to a re-auth or setup message (codes only, no details)."""
    reason = str(error.args[0]) if error.args else ""
    code = reason.split(":", 1)[0].strip()
    if code == "invalid_grant":
        return ReauthRequired(alias, f"Google revoked or expired the sign-in for {alias!r}")
    if not _OAUTH_ERROR_CODE.fullmatch(code):
        code = "unknown error"
    return MailError(f"Couldn't refresh the Google sign-in for {alias!r} ({code}).")


def _parse(response: HttpResponse) -> dict[str, Any]:
    """Return the JSON object body, or raise GmailError for an error status or bad body."""
    try:
        data = response.json()
    except ValueError:
        data = None
    if response.status_code == NOT_FOUND:
        raise GmailNotFound(f"Gmail API error 404: {_error_message(data)}")
    if response.status_code >= 400:
        raise GmailError(f"Gmail API error {response.status_code}: {_error_message(data)}")
    if not isinstance(data, dict):
        raise GmailError("Gmail sent a response that isn't a JSON object.")
    return data


def _error_message(data: object) -> str:
    """Gmail's error.message, capped; it describes the request, never credentials."""
    error = data.get("error") if isinstance(data, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return str(message)[:MAX_ERROR_CHARS] if message else "no details"
