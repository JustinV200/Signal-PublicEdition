# Tabular data

Rows are units (people, jobs, transactions), columns are attributes.

## Load and clean

- Under ~2 GB: pandas, or polars if it's slow. Bigger, or many files: duckdb
  straight over the CSV/parquet (`duckdb.sql("select ... from 'data/raw/*.csv'")`).
- Save the cleaned table to `data/clean/` as parquet with a short note in the
  script header on every row you dropped and why.
- Check: duplicates on the unit key, impossible values, unit mixups (k vs units,
  cents vs dollars), category spelling variants, and whether missing is random.
- If missing < 5% and looks random, drop rows. Else impute (median or
  `sklearn.impute`) inside the pipeline, and add an "is_missing" flag if
  missingness might carry signal.

## Pick the question type

Most table questions are answered by group-bys, pivots, counts, medians and a
chart. Go down the table only as far as the question needs.

| If the question is... | Then start with | Step up to |
|---|---|---|
| "How much / how many / what's typical?" | counts, medians, quantiles, a pivot table | weighted or per-capita figures |
| "Does X relate to Y?" (explain) | statsmodels OLS / logit with robust SEs | GLM, mixed effects (`statsmodels.api.MixedLM` or `smf.mixedlm`) for grouped data |
| "Predict Y" (numeric) | mean / median baseline, then `Ridge` | lightgbm / xgboost |
| "Predict Y" (class) | majority-class baseline, then `LogisticRegression` | lightgbm / xgboost |
| "Which groups exist?" | `KMeans` on scaled features | `HDBSCAN` (sklearn), Gaussian mixtures |
| "Is A different from B?" | difference + CI, Welch t-test or Mann-Whitney | regression with controls |
| "What drives Y?" | coefficients of a regularised linear model | SHAP on a tree model, permutation importance |

Explaining and predicting are different jobs. If the user wants to know *why*,
prefer an interpretable model and report coefficients with CIs. If the user wants a
forecast or a score, prefer accuracy and report validation error.

## Regression and classification

- Build a `sklearn.pipeline.Pipeline` (impute, scale, encode, model) so every
  transform is fit on train folds only. See `../validation.md`.
- Categoricals: one-hot if under ~20 levels, else target encoding inside CV, or
  let lightgbm handle them natively.
- Trees: lightgbm first (fast, handles missing and categoricals). Tune a few
  params (`num_leaves`, `learning_rate`, `n_estimators` with early stopping),
  not a giant grid.
- Under ~500 rows: skip boosted trees, use regularised linear models and say
  the sample is small.
- Imbalanced classes: report PR-AUC and recall at a useful threshold, not
  accuracy. Use `class_weight` before resampling.
- Metrics: regression MAE plus R2; classification ROC-AUC, PR-AUC, and Brier
  score if probabilities matter.

## Causal-sounding questions

Observational data can't prove cause. If the question asks "does X cause Y":
- Control for obvious confounders in a regression and say which ones.
- If there's a policy change or a cutoff, consider difference-in-differences or
  regression discontinuity.
- Word findings as association unless the design supports more, and set
  confidence no higher than Medium.

## Clustering

- Scale features first (`StandardScaler`). Pick k with silhouette and by whether
  the clusters mean something, not by silhouette alone.
- Describe each cluster by its feature means vs the overall mean, and give its
  size. A cluster of 3 rows isn't a segment.
- Check stability: re-run with different seeds or a bootstrap sample. If the
  clusters move a lot, say they're weak.

## Deliverables

- The summary table or comparison that answers the question.
- If you modelled: model results vs baseline with the validation metric and CI.
- One chart of the effect or importance that answers the question.
- Any final model saved to `models/` if Q&A might reuse it.
