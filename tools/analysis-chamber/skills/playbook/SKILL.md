---
name: playbook
description: >
  Methods playbook for analysis chamber runs. Read it before planning or
  analysing any data in a chamber run: choosing sources, picking methods by data
  type (tabular, time series, text, graph, geo, web research), validating
  models and claims, making colourblind-safe charts, using the GPU lock and run
  venv, writing the report and writeup, and running or answering the critic pass.
  Use when a chamber run plans, collects, explores, models, validates or reports.
---

# Analysis chamber methods playbook

You are the lead agent of a chamber run. This playbook is the house standard for
how analysis is done. Follow it unless the question gives a clear reason not to,
and when you deviate, say why in the report's methods section.

## Choosing the approach

Pick the lightest method that answers the question. Most runs need no model.

| If the question is... | Typical approach |
|---|---|
| "What's the state of X?" / "What do people say about X?" | web research: sourcing, triangulation, synthesis |
| "What happened / what's true about X?" | careful reading of sources and extracts, a fact table |
| "How has my Y changed?" / "How much, how often?" | descriptive stats, tables, time charts |
| "Is A different from B?" / "Does X go with Y?" | comparisons, then a test or regression if it needs inference |
| "What predicts Z?" / "Forecast Z" | modelling, vs a baseline |
| "What groups or themes are in this pile?" | read and code by hand if it's small; clustering or embeddings only at scale |

## How to use it

1. Read this file fully once at the start of the run.
2. Open only the reference files your data needs. Each one is a decision guide:
   "if X then Y, else Z". Don't read them all up front.
3. Re-open `validation.md` before you claim any result, and `charts.md` before
   your first figure.
4. The critic reads `critic.md`. Read it too before the critique phase, so you
   fix the obvious things first.

## Run folder

Everything lives in the run folder. Paths below are relative to it.

| Path | What goes there |
|---|---|
| `data/raw/` | downloads and exports exactly as received |
| `data/clean/` | tidy tables you built (parquet preferred, CSV fine) |
| `extracts/` | fetch sub-agent extracts of web pages and personal free text |
| `code/` | every script you ran, numbered in order (`01_load.py`, `02_eda.py`) |
| `figures/` | PNG charts |
| `models/` | saved models and embeddings |
| `sources.json` | every source you rely on: name, url, status, note (grade, data date), fetched_at |
| `results.md` | numbered findings with numbers, script or source, confidence word (you keep it) |
| `critique.md` | critic findings and resolutions (the chamber writes it) |
| `report.*`, `writeup.md` | outputs, written after the critique |

The chamber owns `manifest.json`, `plan.md`, `critique.md` and `qa.md`. Don't
edit them.

Write code as files in `code/` and run them, not as long inline `python -c`
strings. The Q&A agent re-runs these later, so they must work from a clean start.

## Core workflow

1. **Frame.** Restate the question, split it into sub-questions, and write down
   what answer would change a decision. Name the unit of analysis, the outcome,
   and the time window. If the question is vague, pick the most useful reading
   and say so.
2. **Collect.** Pull only what the sub-questions need, with breadth scaled to the
   question. Log every source you rely on in `sources.json` as you go, with its
   A/B/C grade and data date in `note`. For a URL the tools already recorded,
   only your note is merged; status comes from the tool, so put "skipped" or
   "failed" reasons in the note. You have no browser and no WebSearch. Use:
   - `chamber_search(query)` to search the web. It returns titles, URLs and
     dates only.
   - `chamber_fetch(url, instructions)` to read a page as a structured extract,
     and by default to download data files: it saves them to `data/raw/`,
     checks robots.txt and keeps to 1 request/second/host.
   - `chamber_extract_file(path, instructions)` for text files inside the run
     folder (run-relative path). For a file the user points at, copy it into
     `data/raw/` first. For a PDF, run `analysis-chamber install pypdf` from
     the run folder root, convert it to `.txt` in `data/raw/` in code, and
     never print or read the `.txt` yourself. In code, print only the
     character count per file or page. If it's near zero, the PDF is scanned
     with no text layer: list it in the caveats and in `sources.json`. If
     `chamber_fetch` recorded it, put "failed: scanned, no text layer" in the
     note; for a PDF the user pointed at, add it with status `failed`.
     `chamber_extract_file` reads only the first 200,000 characters, so split
     long text into chunk files, then extract each.
   - `chamber_get_api_key(service, signup_url, env_var)` when a free API needs
     a key. It returns only a status. Read the key in code from the `.env`
     file at `os.environ["CHAMBER_ENV_FILE"]` (snippet in web-research.md).
     Never print the key or the file.

   See [methods/web-research.md](methods/web-research.md).
3. **Explore.** Load into pandas/polars or duckdb. Check shape, types, missing
   values, duplicates, ranges, and time coverage first. Plot the
   distributions of the outcome and key inputs. Write down surprises.
4. **Analyse.** Use the lightest method that answers the question, and stop
   there. In order:
   - sourcing and triangulation, careful reading, tables, counts, descriptive
     stats, comparisons and good charts. Many runs end here.
   - statistical tests or regression, when the question needs inference
     (is this difference real, how big is the effect).
   - ML, deep learning or embeddings, only when the question needs prediction,
     pattern discovery at scale, or text at a volume that can't be read.

   A run with no model is normal and good. When you do model, beat a baseline
   by a margin that matters. Guides by data type:
   - [methods/tabular.md](methods/tabular.md): rows and columns, regression,
     classification, clustering
   - [methods/time-series.md](methods/time-series.md): anything indexed by time
   - [methods/text.md](methods/text.md): documents, emails, posts, extracts
   - [methods/graph.md](methods/graph.md): entities and links between them
   - [methods/geo.md](methods/geo.md): locations, regions, maps
   - [methods/web-research.md](methods/web-research.md): questions answered
     mostly from web sources
5. **Validate.** Run the checks in [validation.md](validation.md) that fit what
   you did: source checks and sample sizes always; effect sizes, CIs and
   multiple comparisons for inference; leakage, splits and baselines for models.
   Assign a confidence word (High / Medium / Low) to each finding using its
   criteria. Keep the findings in `results.md`; charts per [charts.md](charts.md).
6. **Critique.** A fresh critic reviews `results.md` and `code/` per
   [critic.md](critic.md), before any report exists. Fix its findings in
   `code/`, `figures/` and `results.md`, and return the resolution table; the
   chamber writes it into `critique.md`. 1-2 rounds.
7. **Report.** Only then write the report and writeup per
   [reporting.md](reporting.md), with a Critic review section summarising
   `critique.md`.

The chamber runs these as phases: plan (step 1), collect (2), analyse (3-5),
critique (6), report (7).

GPU work and package installs: [gpu-and-installs.md](gpu-and-installs.md).

## Ground rules

- Every number in the report traces to a script in `code/` or a cited source.
- Prefer a simple method you can explain over a complex one. Complexity needs a
  reason the question gives, not a reason the kit gives.
- Never hide a negative or null result. "No clear effect" is a finding.
- Never use colour alone for meaning, in charts or in text. Pair colour with labels, markers, line styles or numbers.
- Never send, post or delete anything. Reads only.
