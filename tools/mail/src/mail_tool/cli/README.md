# mail_tool.cli

The `mail` console script.

```
mail setup                          Google Cloud steps + check .state/google_client.json
mail add ALIAS [--email ADDRESS]    sign in through the browser; --email must match
mail accounts                       aliases, emails, live status
mail check                          offline health check (saved, readable sign-ins + client file); exit 1 and a JSON summary line when not
mail remove ALIAS                   forget the saved sign-in
mail search ACCOUNT QUERY [--max N] [--paged] [--page-token T]
                                    Gmail query syntax; a bare JSON list of summaries by default;
                                    --paged or --page-token prints {messages, next_page_token?, estimated_total?}
mail read ACCOUNT ID                one message as JSON
mail send-self --subject S --body-file F
                                    email the UTF-8 file to SELF_ADDRESS, no dialog
mail mcp                            the stdio MCP server
```

`send-self` has no recipient option on purpose (see `service/self_send.py`).

`ACCOUNT` is an alias or an email address. A `MailError` prints as `mail: error: ...` and exits with code 2.

## Files

`main.py` (parser, dispatch, error line), `commands.py` (handlers), `check.py` (`mail check`: reads the account files and client file, no network; can't see a sign-in Google revoked or expired, only `mail accounts` can), `setup_guide.py` (`mail setup`).

## Depends on

`mail_tool.service`, `mail_tool.auth`, `mail_tool.mcp_server`, `mail_tool.config`, `mail_tool.errors`.
