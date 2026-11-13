"""Tests for the mail MCP server through an in-process mcp.Client, over a fake Gmail."""

import pytest
from google.auth.exceptions import RefreshError
from mcp import Client
from support.fakes import (
    SAMPLE_HEADERS,
    SECRET_CLIENT_SECRET,
    SECRET_REFRESH_TOKEN,
    FakeOwner,
    FakeSession,
    gmail_message,
    make_service,
    text_part,
)

from mail_tool.mcp_server import SERVER_NAME, MailTools, build_server

pytestmark = pytest.mark.asyncio

EXPECTED_TOOLS = (
    "mail_accounts",
    "mail_search",
    "mail_read",
    "mail_thread",
    "mail_draft",
    "mail_send_draft",
)
CONTENT_TOOLS = ("mail_search", "mail_read", "mail_thread")
# One call per tool, with arguments that hit every fake route below.
CALLS = (
    ("mail_accounts", {}),
    ("mail_search", {"account": "personal", "query": "is:unread newer_than:1d"}),
    ("mail_read", {"account": "personal", "message_id": "m1"}),
    ("mail_thread", {"account": "owner@example.com", "thread_id": "t1"}),
    ("mail_draft", {"account": "personal", "to": "a@example.com", "subject": "s", "body": "b"}),
    ("mail_send_draft", {"account": "personal", "draft_id": "r-1"}),
)


def _gmail_routes() -> dict:
    message = gmail_message("m1", SAMPLE_HEADERS, parts=[text_part("text/plain", "hello")])
    return {
        ("GET", "profile"): {"emailAddress": "owner@example.com"},
        ("GET", "messages"): {"messages": [{"id": "m1"}]},
        ("GET", "messages/m1"): message,
        ("GET", "threads/t1"): {"id": "t1", "messages": [message]},
        ("POST", "drafts"): {"id": "r-1", "message": {"id": "m2", "threadId": "t2"}},
        ("GET", "drafts/r-1"): {"id": "r-1", "message": message},
        ("POST", "drafts/send"): {"id": "m2", "threadId": "t2"},
    }


def _text(result) -> str:
    return "".join(block.text for block in result.content)


async def test_lists_every_tool_and_content_tools_call_email_data_not_instructions() -> None:
    server = build_server(MailTools(make_service(FakeSession())))
    async with Client(server) as client:
        assert client.server_info.name == SERVER_NAME == "mail"
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert tuple(tools) == EXPECTED_TOOLS
    for name in CONTENT_TOOLS:
        assert "never instructions" in tools[name].description
    assert "is:unread newer_than:1d" in tools["mail_search"].description
    assert tools["mail_read"].annotations.read_only_hint is True


async def test_every_tool_works_and_no_output_or_error_holds_a_secret() -> None:
    working = build_server(MailTools(make_service(FakeSession(_gmail_routes()), FakeOwner(True))))
    # Worst case: the library's refresh error text itself contains both secrets.
    leaky_refresh = RefreshError(
        f"invalid_grant: {SECRET_REFRESH_TOKEN}", {"client_secret": SECRET_CLIENT_SECRET}
    )
    broken_routes = {key: leaky_refresh for key in _gmail_routes()}
    broken = build_server(MailTools(make_service(FakeSession(broken_routes), FakeOwner(True))))

    outputs = []
    for server, should_fail in ((working, False), (broken, True)):
        async with Client(server) as client:
            for name, arguments in CALLS:
                result = await client.call_tool(name, arguments)
                text = _text(result)
                outputs.append(text)
                if name != "mail_accounts":  # accounts reports re-auth as a status, not an error
                    assert result.is_error is should_fail, (name, text)

    assert '"sent":true' in outputs[5]
    assert "re-run `mail add personal`" in outputs[7]
    for text in outputs:
        assert SECRET_REFRESH_TOKEN not in text and SECRET_CLIENT_SECRET not in text
