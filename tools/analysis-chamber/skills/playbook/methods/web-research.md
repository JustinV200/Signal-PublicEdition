# Web research

Questions answered mostly from web sources: market questions, "what's the state
of X", comparisons, fact-finding.

## Fetching: hard rules

Log every source you rely on in `sources.json`, with its A/B/C grade and data
date in `note`. For a URL the tools already recorded, only your note is
merged; status comes from the tool, so put "skipped" or "failed" reasons in
the note.


- **Search with `chamber_search(query)`.** It returns titles, URLs and dates
  only; you have no WebSearch and no browser. Then read pages with `chamber_fetch`.
- **Pages go through `chamber_fetch`.** It hands the page to the tool-less fetch
  sub-agent and returns a structured extract into `extracts/`. You never see raw
  HTML. Ask it for the fields you need (claim, number, date, author, method).
- **Data files also go through `chamber_fetch` by default.** For a CSV, JSON,
  XLSX, parquet, PDF or ZIP URL it saves the file to `data/raw/` and returns the
  path and first lines. It checks robots.txt and keeps to 1 request/second/host.
- **Scripted requests only for documented API endpoints and bulk loops** (many
  pages of an API, many files from a bulk-download index). Add `time.sleep(1)`
  between requests to the same host, and save responses to `data/raw/`.
- **Never curl, wget, `requests.get` or `urllib` an HTML or text page.** A hook
  blocks it anyway.
- If robots.txt disallows a path, skip it and note it.
- Prefer an official API or bulk download over reading many pages. If it needs
  a free key, call `chamber_get_api_key(service, signup_url, env_var)`; it
  returns only a status and puts the key in `.env`. Read it in code from the
  file at `os.environ["CHAMBER_ENV_FILE"]` (python-dotenv isn't in the kit, so
  parse it with a tiny loop). Never print the key, the file or the request URL
  if it carries the key.
  ```python
  import os
  def env_key(name):
      for line in open(os.environ["CHAMBER_ENV_FILE"], encoding="utf-8"):
          k, sep, v = line.strip().partition("=")
          if sep and k.strip() == name:
              return v.strip().strip('"').strip("'")
      raise KeyError(name)
  ```
- A failed or rate-limited source is skipped, logged in `sources.json` with
  status `failed`, and listed in the report's caveats. Don't retry in a loop.

## How much to collect

Let the question set the breadth.
- If a narrow factual question: stop once 2-3 independent good sources agree.
- If a "state of the market" question: aim for every major primary source
  (official stats, large datasets) plus a spread of secondary ones, and stop when
  new sources stop changing the picture.
- If sources keep disagreeing: keep going until you can explain *why* they
  disagree (different dates, definitions, populations).
- Search with several phrasings, and include terms that would find the opposite
  view ("decline", "criticism", "overestimated").

## Source quality

Rate every source you use as A, B or C, and keep that rating in the source list.

| Grade | What counts |
|---|---|
| A | primary data or official stats (BLS, Census, FRED, company filings), peer-reviewed work, datasets with a documented method |
| B | reputable reporting that cites primary data, industry surveys with stated sample and method, well-known trackers |
| C | blogs, forums, vendor marketing, undated pages, anything with no method or sources |

- A C source alone never supports a finding. Use it only as colour or a lead to
  a better source.
- Surveys: note the sample size, who was sampled, and who paid for it.
- Watch for one number echoed by many sites. Trace it to the origin and count it
  once.

## Dating sources

- Record two dates per source: when the data was collected (or the period it
  covers) and when it was published. Also log the date you accessed it.
- If a page has no date, look for clues (copyright year, cited events, archive
  snapshots) and mark it "undated, about <year>". Undated sources cap at grade C.
- For fast-moving topics (jobs, prices, tech), flag anything older than 12 months
  and prefer newer sources when they conflict.

## Triangulation

- Every key finding needs at least two independent sources, ideally of
  different kinds (official stat plus survey, dataset plus reporting).
- When numbers differ, put them side by side with their dates and definitions,
  then give your best estimate as a range and say why.
- If only one source exists, say so, and the finding is Low confidence at best
  unless that source is grade A.

## Turning extracts into data

- Put numbers pulled from extracts into a table in `data/clean/` with a source
  id, date and grade column. Then analyse that table like any other.
- Quote the extract's exact figure and unit. Don't convert units silently.
