# assignment_check.reader

The tool-less claude that reads one site's page text and reports its items.

## Public API

- `READER_LOCKDOWN`, `reader_command(claude_exe)` and `reader_schema()` (`command.py`): no built-in tools, no MCP servers, dontAsk, $1.00. Its init must list exactly `StructuredOutput`.
- `reader_context(now, site, pages)` returns `ReaderContext(text, cut)` (`context.py`): the runner's page list, then the text in one `untrusted_site_content` frame (`SITE_FRAME_TAG`), cut by whole pages at `MAX_READER_CHARS`.
- `parse_reader(run)` returns `ReaderOutput(readable, accounts, items, suspicious)`, or `None` if the run failed (`output.py`). It checks shapes only; `findings/` decides what to believe.

## Dependencies

`mail_digest.claude`, `settings`, `assignment_check.courses`, `signal_untrusted`.
