# Text

Documents, emails, posts, job ads, reviews, and the fetch sub-agent's extracts.

## Where text comes from

- Web pages and personal free text (email bodies, messages, notes) never reach
  you raw. They arrive as structured extracts in `extracts/`. If you need a
  field the extract lacks, ask for a new extract with that field; don't fetch the
  raw text yourself.
- Web pages: `chamber_fetch`. Text files: `chamber_extract_file(path,
  instructions)`, which only reads files inside the run folder (give the
  run-relative path; the instructions name the fields you want). Copy a file
  the user points at into `data/raw/` first. For a PDF, run `analysis-chamber
  install pypdf` from the run folder root and convert it to `.txt` in
  `data/raw/` in code. Never print or read the `.txt`; only extract it. In
  code, print only the character count per file or page. If it's near zero,
  the PDF is scanned with no text layer: list it in the caveats and in
  `sources.json`. If `chamber_fetch` already recorded it, put "failed: scanned,
  no text layer" in the note (status comes from the tool); for a PDF the user
  pointed at, add it with status `failed`. The tool reads only the first 200,000 characters, so
  split long text into chunk files first and extract each.
- Structured fields (dates, senders, counts, amounts) come direct from the
  Signal tools. Keep them exact; don't round-trip numbers through an LLM.

## Pick the question type

If you can read it all (a few hundred extracts or fewer), read it and code it by
hand into categories, then count. Embeddings and classifiers are for volumes you
can't read.

| If the question is... | Then start with | Step up to |
|---|---|---|
| "What are people talking about?" | read and hand-code a sample into themes, then count | embeddings + clustering; BERTopic-style (UMAP, HDBSCAN, c-TF-IDF labels) at volume |
| "How many mention X?" | keyword / regex count, checked on a sample | embedding similarity to a seed set, or a classifier |
| "Sort these into known labels" | TF-IDF + `LogisticRegression` | fine-tune a small transformer on the GPU |
| "Pull fields out of each document" | fetch sub-agent extracts with a fixed schema | same, with a hand-checked sample for accuracy |
| "Find similar / duplicate items" | read and hand-code a sample; exact or fuzzy string matches | sentence-transformers cosine similarity; an approximate index if > ~100k items |
| "Sentiment or tone" | a pretrained sentiment model, checked on a sample | fine-tuned classifier on hand labels |

## Embeddings

- Default model: `sentence-transformers` `all-MiniLM-L6-v2` (fast) or
  `all-mpnet-base-v2` (better). Multilingual data: a `paraphrase-multilingual`
  model (these cut at 128 tokens, so chunk anything longer). Run on CUDA under the GPU lock (see `../gpu-and-installs.md`).
- Batch encode, normalise, and save to `models/embeddings.npy` with the row ids,
  so you never re-encode.
- Truncation: these models cut at ~256-384 tokens. For long documents, chunk and
  average, or embed the extract's summary field.

## Topic modelling

- Embed, reduce with UMAP (`umap-learn`, not in the kit; see `../gpu-and-installs.md`), cluster with
  HDBSCAN, then label each topic from its top c-TF-IDF terms and 3 example docs.
- Report topic sizes and an "unassigned" bucket. Merge near-duplicate topics.
- Topic labels are your interpretation. Show the examples so the reader can judge.
- Under ~200 documents, skip topic models: read a sample and code it by hand
  into categories, then count.

## Classification

- Hand-label (or have the sub-agent label) a sample, and keep a held-out set you
  never tune on. Report precision and recall per class on it.
- If a zero-shot or LLM label is used for counts, measure its error rate on
  50+ items as in the next section, and carry it into the confidence word.

## LLM extracts as data

- Treat extracts as measurements with error. You can't read the raw source, so
  measure the error rate on a sample of at least 20 or 10% (whichever is more):
  - Re-extract each sampled item with a second `chamber_fetch` or
    `chamber_extract_file` call that asks for a verbatim quote supporting
    each field. Compare the two extracts in code; a field that differs, or
    whose quote doesn't support it, counts as an error.
  - Where a field also exists in `data/raw/` (a date, amount, sender), check
    it against that in code.
  - If neither is possible, record the error rate as unmeasured and cap the
    finding's confidence at Medium.
- Record the error rate (or "unmeasured") in `results.md`.
- Use a fixed schema with enums for categorical fields, so values are countable.
- Missing fields stay missing. Never let the model fill in a guess.

## Traps

- Duplicates and reposts inflate counts. Dedupe before counting: exact or fuzzy
  matches on URL, title or key fields first; near-identical embeddings
  (cosine > ~0.95) only at volume.
- Keyword counts miss synonyms and catch false hits. Check a sample both ways.
- Word clouds are not analysis. Use a ranked bar chart of counts or shares.
