"""Test doubles for the Confirmer and LoginFiller protocols."""

from typing import Any

from browser_tool.credentials import CredentialInfo, FillResult
from browser_tool.gates import ConfirmationRequest

SECRET_PASSWORD = "vault-secret-Pa55-9f3k"
SECRET_USERNAME = "alice.vault@example.test"
SCRUBBED = "[scrubbed]"
DEMO_CREDENTIAL = CredentialInfo(
    id="demo",
    label="Demo site",
    origins=("http://allowed.localhost",),
    username_hint="a***@example.test",
)


class FakeConfirmer:
    """Answers every confirmation with a fixed yes/no and records the requests."""

    def __init__(self, answer: bool = False):
        self.answer = answer
        self.requests: list[ConfirmationRequest] = []

    async def confirm(self, request: ConfirmationRequest) -> bool:
        self.requests.append(request)
        return self.answer


class ApprovesAfterNavigating:
    """Says yes, but while the owner was deciding, the tab went to `url`."""

    def __init__(self, page: Any, url: str):
        self.page = page
        self.url = url
        self.requests: list[ConfirmationRequest] = []

    async def confirm(self, request: ConfirmationRequest) -> bool:
        self.requests.append(request)
        await self.page.goto(self.url)
        return True


class FakeLoginFiller:
    """Fills #username and the password field like the vault would, in-process.

    Attributes:
        error: Raised by fill_login instead of filling, when set.
    """

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.filled_pages: list[Any] = []

    def list_credentials(self) -> list[CredentialInfo]:
        return [DEMO_CREDENTIAL]

    async def fill_login(
        self, page: Any, credential_id: str, *, submit: bool = False
    ) -> FillResult:
        if self.error is not None:
            raise self.error
        await page.locator("#username").fill(SECRET_USERNAME)
        await page.locator("input[type=password]").first.fill(SECRET_PASSWORD)
        self.filled_pages.append(page)
        return FillResult(ok=True, reason="filled")

    async def has_filled_fields(self, page: Any) -> bool:
        return page in self.filled_pages

    def scrub(self, page: Any, text: str) -> str:
        return text.replace(SECRET_PASSWORD, SCRUBBED).replace(SECRET_USERNAME, SCRUBBED)
