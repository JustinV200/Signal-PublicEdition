Collect phase. Gather the data the approved plan (`plan.md`) needs, with breadth scaled to the question. Don't analyse yet beyond basic checks that a download worked.

- Find pages and datasets with `chamber_search` (titles, URLs and dates only). Get them with `chamber_fetch`: pages come back as extracts in `extracts/`, and data files (CSV, JSON, XLSX, API responses) land in `data/raw/`. Tidy tables you build go to `data/clean/`.
- Signal read tools that return free text (email bodies, messages, notes) come back as extracts automatically; their raw output is under `data/raw/signal/` for exact counts in code (never print its free text). Use `chamber_extract_file` for other free text saved in the run folder.
- If a free public API needs a key, call `chamber_get_api_key(service, signup_url, env_var)`. It returns only a status; on success the key is in Signal's `.env` under `env_var`. In code, read it by name from the file whose path is in the `CHAMBER_ENV_FILE` environment variable, and never print it. Free tiers only. If it fails, use a keyless source and note it.
- A source that fails or is rate limited: skip it and note it.
- The chamber tools record each fetch themselves, but keep `sources.json` in the run folder as your log of every source you rely on, including Signal tool reads and files the user named (repeats of tool-recorded URLs are fine): a JSON list of objects with `name`, `url` (or tool and query, or file path), `status` (`ok`, `failed` or `skipped`), `note` (its A/B/C grade and data date, or why it failed) and `fetched_at` (ISO date).

Reply with a short summary of what you collected and what failed.
