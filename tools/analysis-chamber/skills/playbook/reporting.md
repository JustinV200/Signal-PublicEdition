# Reporting

A run produces two documents with different jobs:
- **Report:** the evidence. What was found, how, from what, and how sure.
- **Writeup** (`writeup.md`): the take. What it means and what to do.

Keep the overlap small. The writeup can cite a finding by number; it doesn't
repeat the evidence.

## Choosing a report format

| If... | Then |
|---|---|
| mostly prose and a few static charts | `report.md` + PNGs in `figures/` |
| interactive charts help (many series, maps, drill-down) | `report.html`, self-contained, plotly inline |
| the analysis is the point and the user may tinker with it | `report.ipynb`, executed, outputs saved |
| a polished page suits the topic, **and the run is not personal** | HTML written for an artifact; the starting chat publishes it |

- **Personal runs never use the artifact format.** No exceptions, even if asked
  mid-run. Use local HTML or Markdown.
- The run never publishes anything itself. For the artifact format, write the
  HTML in the run folder; the starting chat does the publish.
- When unsure, use Markdown + PNG.

## Report contents

In this order:

1. **Question.** The restated question and sub-questions from the plan.
2. **Findings.** Numbered. Each one has:
   - a one-sentence statement with the key number and its CI or range
   - **Confidence: High / Medium / Low**, as the word, with a one-line reason
     (criteria in `validation.md`)
   - caveats specific to that finding
   - the figure or table that supports it
3. **Methods.** For each analysis:
   - what was done and why it fits the question
   - alternatives tried, and why they were dropped
   - the checks run; if modelled, validation scores vs the baseline (metric,
     folds, mean and spread)
   - packages installed for the run (from `manifest.installs[]`)
4. **Sources.** Every source used (from `sources.json`), with:
   - a link (URL, file path, or Signal tool and query)
   - the date of the data and the date accessed
   - the quality grade (A / B / C, per `methods/web-research.md`)
   - sources that failed or were skipped, and why
5. **Caveats.** Run-wide limits: data gaps, skipped sources, definition
   problems, what the data can't tell you.
6. **Critic review.** A short summary of `critique.md`: what was found and fixed,
   and anything left open.

No reproduce section is needed; the code in `code/` serves that.

## Style for the report

- Plain, direct sentences. Numbers with units and sensible rounding.
- Every number traces to a script or a source.
- Confidence and status are words, never colour alone. Tables that rank or rate
  use text labels or numbers in the cell.
- Charts follow `charts.md`.

## Writeup

`writeup.md` is a 1-2 page plain briefing written to the user. It's internal, so
no special voice rules. Structure:

1. **Findings.** Open with 2-4 sentences answering the question directly,
   then the few findings that matter, each one line with its confidence word,
   referencing the report's finding number.
2. **Recommendation.** What the user should do or believe, concretely.
3. **What would change the conclusion.** The specific evidence or events that would flip
   or weaken the conclusion, and what to watch.

Rules:
- No methods detail, source lists or charts; those live in the report.
- Lead with the answer, not the process.
- If the honest answer is "unclear", say that, and say what data would settle it.

## Done checklist

- [ ] Every finding has a confidence word and a reason
- [ ] Sources have links, data dates and access dates
- [ ] Methods list alternatives, and validation scores vs baseline if modelled
- [ ] Installs listed
- [ ] The report reflects the fixes in `critique.md` and summarises it
- [ ] Personal run: no artifact format, no files under the Signal repo
