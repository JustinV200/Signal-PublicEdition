# Validation

Run the checks that fit what you did before you claim any result. The critic
checks the same list.

- **Always:** source quality and dates, sample sizes, counts behind percentages,
  and the confidence word.
- **Inference** (tests, regression): effect sizes, CIs, multiple comparisons.
- **Models** (prediction, clustering, embeddings): baselines, leakage, splits,
  calibration.

## Baselines, always

Every model and every "X is better" claim gets compared to a dumb baseline on
the same data and split. Descriptive findings compare against the obvious
reference instead (last year, the overall average).
- Regression: predict the training mean or median.
- Classification: predict the majority class; also report the class balance.
- Time series: naive (last value) and seasonal naive.
- Comparisons: the obvious alternative explanation (last year's value, the
  overall average, random chance).

If the model doesn't beat the baseline by a margin that matters for the
decision, the finding is "no useful signal", and that is a valid result.

## Leakage checklist

Go through each item and fix any hit before reporting.

- [ ] No feature is computed from the target, or from data recorded after the
      prediction time (outcomes, "status", "final_", future rows).
- [ ] Scaling, imputation, encoding and feature selection are fit on training
      folds only (use a `sklearn` `Pipeline` inside CV).
- [ ] No duplicate or near-duplicate rows straddle train and test.
- [ ] Rows from the same entity (person, company, thread) are in one split
      only: use `GroupKFold`.
- [ ] Time-ordered data uses time-based splits. Test is strictly after train.
- [ ] Target encoding and lag features are computed inside each fold.
- [ ] Hyperparameters were tuned on validation folds, not the final test set.
- [ ] A suspiciously good score (AUC > 0.95, R2 > 0.9 on a messy problem) has
      been explained. Check the top features for leaks.

## Splits and cross-validation

- If rows are independent: `KFold` (5 folds), stratified for classification.
- If rows are grouped by entity: `GroupKFold`.
- If data is time-ordered: `TimeSeriesSplit` or rolling-origin backtests, with
  a gap if features use lags.
- If spatial: group folds by region (see `methods/geo.md`).
- Keep a final held-out test set when you have enough data (> ~2,000 rows) and
  touch it once. Else report CV mean and spread across folds.
- Report the metric as mean plus or minus SD across folds, not the best fold.

## Statistics

- **Effect sizes with CIs, not just p-values.** Report the difference, ratio or
  coefficient with a 95% CI. Use `scipy.stats.bootstrap` when the formula isn't
  obvious.
- **Multiple comparisons.** If you test many things (features, segments, topics),
  correct with Benjamini-Hochberg (`statsmodels.stats.multitest.multipletests`,
  `method="fdr_bh"`) and say how many tests you ran. Findings found by searching
  are hypotheses, not results.
- **Assumptions.** Skewed or heavy-tailed data: use medians, log transforms, or
  rank tests. Heteroscedastic residuals: robust SEs (`cov_type="HC3"`).
- **Correlation vs cause.** Unless the design supports it, say "is associated
  with". See `methods/tabular.md`.
- **Practical significance.** A tiny effect with p < 0.001 on 1M rows may not
  matter. Say whether it matters for the decision.

## Calibration

If probabilities get used (risk, chance of X):
- Plot a reliability curve (`sklearn.calibration.calibration_curve`) and report
  the Brier score.
- Calibrate with `CalibratedClassifierCV` (isotonic if > ~1,000 rows, else
  sigmoid) on held-out folds.
- Forecast intervals: check coverage on the backtest.

## Small-n warnings

- n < 30 per group: Welch t or exact / permutation tests. Use the bootstrap with
  caution, since its CIs are too narrow at small n. Show the raw points.
- n < 100 total: no complex models; regularised linear at most.
- Fewer than ~10 events per predictor in a logistic model: drop predictors.
- Percentages from small bases: always show the count too ("40% (4 of 10)").
- Any finding resting on n < 30: confidence Low unless the effect is huge and
  backed by another source.

## Confidence words

Every finding gets exactly one of these words, plus a one-line reason.

**High**: all of these hold.
- Backed by grade A data or by 2+ independent sources that agree.
- Holds across time windows or subsets. Where a model or test is used: the CI
  excludes no effect and any model beats its baseline across folds.
- Adequate sample (n >= 100, or the effect is huge relative to noise).
- No open critic finding against it.

**Medium**: the direction is solid, but one of these applies.
- One grade A source with a stated caveat, or 2+ independent sources that
  agree on direction but not size.
- CI is wide, or the result shifts noticeably with a reasonable method change.
- Observational association where a confounder is plausible.
- Depends on LLM extracts whose error rate is unmeasured (see
  `methods/text.md`).
- A methods file caps it at Medium (2 to under 3 seasonal cycles; a causal
  question on observational data).

**Low**: any of these applies.
- Rests on a single grade B or C source, or on undated sources.
- Small n (fewer than 30 in a group the finding rests on), unless the effect is
  huge and a second source backs it.
- Found by searching many tests, or the model barely beats the baseline.
- Depends on LLM extracts with a measured error rate above ~10%, measured by
  re-extraction or checks against `data/raw/` (see `methods/text.md`).
- The critic raised an issue that couldn't be fully resolved.

**Precedence.** Apply in order:
1. Any Low bullet applies: Low.
2. Otherwise, any Medium bullet applies: Medium.
3. Otherwise, all High bullets hold: High.
4. Otherwise: Medium.

Descriptive and web-sourced facts skip the model and test checks, so they can
reach High on sources, consistency and sample alone. When unsure between two
words, pick the lower one.
