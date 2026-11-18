"""MailTools: the behaviour behind each mail MCP tool.

Each tool runs its MailService call in a worker thread (they block on the
network, and send_draft on the owner's dialog) and returns compact JSON text
(no indent: it is for the model, and whitespace costs tokens).
Expected failures become ToolError with their secret-free message; anything
else is a crash the SDK reports as "Error executing tool" without details.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from mail_tool.errors import MailError
from mail_tool.gmail import DraftContent
from mail_tool.service import DEFAULT_MAX_RESULTS, MailService


class MailTools:
    """Backs every mail MCP tool. Parameters are named as the tools' schemas show them."""

    def __init__(self, service: MailService) -> None:
        """Args: service: the mail operations (a fake-backed one in tests)."""
        self._service = service

    async def mail_accounts(self) -> str:
        """See descriptions.MAIL_ACCOUNTS."""
        return await _run(self._service.list_accounts)

    async def mail_search(
        self,
        account: str,
        query: str = "",
        max_results: int = DEFAULT_MAX_RESULTS,
        page_token: str = "",
    ) -> str:
        """See descriptions.MAIL_SEARCH."""
        return await _run(self._service.search_page, account, query, max_results, page_token)

    async def mail_read(self, account: str, message_id: str) -> str:
        """See descriptions.MAIL_READ."""
        return await _run(self._service.read, account, message_id)

    async def mail_thread(self, account: str, thread_id: str) -> str:
        """See descriptions.MAIL_THREAD."""
        return await _run(self._service.thread, account, thread_id)

    async def mail_draft(
        self, account: str, to: str, subject: str, body: str, reply_to_message_id: str = ""
    ) -> str:
        """See descriptions.MAIL_DRAFT."""
        content = DraftContent(to=to, subject=subject, body=body)
        return await _run(self._service.create_draft, account, content, reply_to_message_id or None)

    async def mail_send_draft(self, account: str, draft_id: str) -> str:
        """See descriptions.MAIL_SEND_DRAFT."""
        return await _run(self._service.send_draft, account, draft_id)


async def _run(operation: Callable[..., Any], *args: Any) -> str:
    """Run a blocking service call in a thread and return its result as JSON text."""
    try:
        result = await asyncio.to_thread(operation, *args)
    except MailError as error:
        raise ToolError(str(error)) from None
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
