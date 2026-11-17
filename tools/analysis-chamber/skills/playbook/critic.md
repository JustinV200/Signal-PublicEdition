# Critic pass

The critique phase runs after analyse and before the report exists. A fresh
Opus critic with no shared context reads `plan.md`, `code/`, `figures/`,
`data/clean/`, `extracts/`, `results.md`, `sources.json` and earlier rounds of
`critique.md`, plus this playbook and `validation.md`. It edits no files. The
lead fixes the findings, then the critic re-checks. 1-2 rounds.

## For the critic: how to review

- Re-run key scripts when a number looks off. Don't take `results.md`'s word.
- Hunt for problems that would change a finding or its confidence word. Skip
  style nits.
- Be specific: file, line or figure, what's wrong, and what would fix it.
- If you find nothing serious, say so plainly. Don't invent findings.

## Checklist

### Fit of method to question
- [ ] The method is the lightest that answers the question. Flag unnecessary
      complexity (a model where a table or comparison would do, embeddings for
      text that could be read) as firmly as a weak method.
- [ ] Flag the reverse too: a claim of a real difference or effect with no test
      or CI behind it.

### Leakage and validation (if anything was modelled)
- [ ] Every item in the leakage checklist in `validation.md` holds.
- [ ] Splits match the data (grouped, time-based, spatial where needed).
- [ ] Every model is compared to a baseline on the same split.
- [ ] Scores are from validation or test data, not training data.
- [ ] Tuning didn't touch the final test set.

### Statistics
- [ ] Effect sizes have CIs, not just p-values.
- [ ] Multiple comparisons are corrected, or the findings say they're exploratory.
- [ ] Test assumptions fit the data (skew, independence, variance).
- [ ] Small samples are flagged and the confidence word reflects them.
- [ ] Percentages show their base counts where the base is small.
- [ ] Trending time series aren't correlated without differencing.

### Claims
- [ ] Each finding follows from the evidence shown, at the strength stated.
- [ ] Causal wording only where the design supports it.
- [ ] Confidence words match the criteria in `validation.md`.
- [ ] Null and negative results aren't buried.
- [ ] Each finding in `results.md` is stated no stronger than its evidence, so
      the report and writeup built from it can't overclaim.

### Sources
- [ ] Key findings have 2+ independent sources, or are marked Low, unless the
      one source is grade A.
- [ ] Source grades are fair; no C source carries a finding alone.
- [ ] Every source a finding relies on is in `sources.json` with its A/B/C
      grade and data date in `note`.
- [ ] Sources are dated, and stale sources are flagged on fast-moving topics.
- [ ] Echoed numbers were traced to their origin and counted once.
- [ ] LLM extracts used as data have an error rate measured by re-extraction
      or checks against `data/raw/`, or are marked unmeasured and capped at
      Medium.

### Charts
- [ ] Colourblind-safe palette; no red vs green; every series also has a
      marker, line style, hatch or direct label.
- [ ] Bar axes start at zero; uncertainty is shown and explained.
- [ ] Titles state a finding the chart actually shows.
- [ ] Axis labels have units; key bars have values.
- [ ] No cropped ranges or dual axes that mislead.

### Run hygiene
- [ ] Scripts in `code/` run in order from a clean start.
- [ ] Installs match the manifest's install log (`manifest.installs[]`), and any
      `--allow-shadow` install has a reason.
- [ ] Personal run: nothing written under the Signal repo.

## Severity

| Severity | Meaning |
|---|---|
| **Blocker** | A finding is wrong or unsupported as stated (leakage, a broken stat, a claim the data can't back). Must be fixed or the finding dropped. |
| **Major** | A finding's confidence word or size is likely off, a key check is missing, or the method is far heavier than the question needs. Fix, or lower the confidence and explain. |
| **Minor** | Clarity or presentation issue that doesn't change a conclusion. Fix if cheap. |

## Recording in critique.md

The lead fixes findings in `code/`, `figures/` and `results.md`, then replies
with a resolution table. The chamber writes that table into `critique.md`; the
lead never edits `critique.md` itself. One row per finding:

```markdown
# Critique

## Round 1

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | `code/04_model.py` line 22 fits the scaler on all rows before CV (leakage). | Blocker | Fixed: moved scaler into the Pipeline. AUC 0.91 -> 0.84; finding 2 updated. |
| 2 | Finding 3 rests on one blog post. | Major | Left: no second source found after 6 searches. Confidence lowered to Low, caveat added. |
| 3 | Fig 2 has no units on the y-axis. | Minor | Fixed. |

## Round 2

Critic re-check: 1 and 3 confirmed fixed; 2 accepted as left with reason. No new
Blocker or Major findings.
```

Rules:
- Every finding gets a resolution: "Fixed: <what changed>" or "Left: <why>".
- A Blocker can't be "Left" unless the affected finding is dropped from
  `results.md`.
- If a fix changes a number or confidence word, say which finding and the
  before and after.
- The report, written after the last round, has a "Critic review" section
  summarising `critique.md`.
