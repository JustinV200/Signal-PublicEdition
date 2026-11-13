# mail_tool.cli

The `mail` console script.

```
mail setup                          Google Cloud steps + check .state/google_client.json
mail add ALIAS [--email ADDRESS]    sign in through the browser; --email must match
mail accounts                       aliases, emails, live status
mail remove ALIAS                   forget the saved sign-in
mail search ACCOUNT QUERY [--max N] Gmail query syntax; JSON summaries
mail read ACCOUNT ID                one message as JSON
mail send-self --subject S --body-file F
                                    email the UTF-8 file to owner.alt@example.com, no dialog
mail mcp                            the stdio MCP server
```

`send-self` has no recipient option on purpose (see `service/self_send.py`).

`ACCOUNT` is an alias or an email address. A `MailError` prints as `mail: error: ...` and exits with code 2.

## Files

`main.py` (parser, dispatch, error line), `commands.py` (handlers), `setup_guide.py` (`mail setup`).

## Depends on

`mail_tool.service`, `mail_tool.auth`, `mail_tool.mcp_server`, `mail_tool.config`, `mail_tool.errors`.
