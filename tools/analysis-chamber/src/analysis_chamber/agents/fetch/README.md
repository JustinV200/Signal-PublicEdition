# agents.fetch

Getting outside content for the lead without it ever seeing raw pages:

- `HttpDownloader(limiter, get, max_bytes)` (`download.py`): checked redirects, robots.txt (`robots.py`), `SHARED_LIMITER` at 1 req/s per origin, size cap. Both key on `origin_key` (`ratelimit.py`).
- `http_get` (`http.py`): the no-redirect GET under it, plus `FetchError` and `Response`.
- `pages.py`: page-to-text, and the markup and JSON sniffing that decides page or data file.
- `store.py`: run-folder storage.
- `ChamberTools`, `ChamberIO`, `SourceSink`, `result` (`handlers.py`): the logic behind chamber_fetch, chamber_extract_file and chamber_search.
- `signal_swap_matcher`, `signal_failure_matcher`, `PASS_THROUGH_TOOLS` (`signal_swap.py`): the PostToolUse free-text swap, and the PostToolUseFailure warning (it can't replace error text; see the TODO in [../README.md](../README.md)).

See [../README.md](../README.md). Depends on `guard`, `runs`, `agents.nested`, `signal-untrusted`.
