# Time series

Anything indexed by time: prices, counts per day, emails per week, job posts per
month.

## Prepare

- Parse to timezone-aware datetimes, then convert to one zone (the user's local zone: ask, or infer it from the data).
  Say which zone in the report.
- Pick the frequency the question needs and resample (`df.resample("W")`).
  Daily data with weekly questions is noise.
- Fill gaps deliberately: zero for counts with no events, forward-fill for
  levels (prices), NaN otherwise. Never interpolate the target you forecast.
- Plot the raw series first. Look for level shifts, outliers, missing stretches,
  and definition changes (a source that changed how it counts).

## Pick the question type

| If the question is... | Then start with | Step up to |
|---|---|---|
| "What's the trend?" | rolling mean + linear trend, HAC CI | `statsmodels` STL decomposition, LOWESS |
| "Is there seasonality?" | group by weekday/month, ACF plot | STL, Fourier terms in a regression |
| "Did something change at time T?" | before/after means, HAC or block-bootstrap CI | interrupted time series regression, `ruptures` change points |
| "Forecast the next N" | naive and seasonal-naive baselines | ETS / SARIMAX (statsmodels), lightgbm on lag features |
| "Do X and Y move together?" | correlation of *differenced* series | Granger tests, VAR, regression with lags |

For trend and before/after CIs, use Newey-West (HAC) standard errors:
`smf.ols(...).fit(cov_type="HAC", cov_kwds={"maxlags": k})` (`smf` is
`statsmodels.formula.api`), with `k` about one seasonal cycle, or a block
bootstrap. Plain CIs assume independent points.

## Forecasting

Only when the question asks for a forecast. Describing the past needs none.

- Baselines first, always: last value (naive), same period last cycle
  (seasonal naive), and the mean. A model that doesn't beat seasonal naive is
  not worth reporting as a forecast.
- If you have one series and short history, prefer non-seasonal ETS or ARIMA;
  add seasonal terms (seasonal ETS, SARIMAX) only with 2+ full cycles (2 to
  under 3 cycles: tentative, Medium at most; 3 or more: firm). If you
  have many related series or rich covariates, lightgbm on lag and calendar
  features usually wins. Deep models (PyTorch) only for many long series, and
  only if they beat lightgbm.
- Validate with rolling-origin backtests (`TimeSeriesSplit` or a manual loop),
  never a random split. See `../validation.md`.
- Report MAE plus MASE (error relative to seasonal naive), vs every baseline.
  Use MAPE only if values stay well above zero; if they touch zero, use WAPE
  (sum of absolute errors / sum of actuals), not sMAPE.
- Give prediction intervals, not just a line. Check their coverage on the
  backtest (an 80% interval should contain ~80% of actuals).

## Traps

- Neighbouring points are autocorrelated, so plain t-tests and OLS CIs are too
  narrow and p-values too small. Use HAC SEs or a block bootstrap.
- Two trending series always correlate. Difference or detrend before claiming a
  relationship.
- Lag features must only use past data. Compute them with `.shift()` and check
  the first rows by eye.
- Rolling windows must be trailing, not centred, for anything used as a feature.
- Holidays and one-off events (COVID, a strike) distort fits. Flag or exclude
  them and say which.
- Seasonality claims: under 2 full cycles, none; 2 to under 3 cycles: a
  seasonal fit is OK but tentative, Medium at most; 3 or more: firm.

## Deliverables

- A chart of the series with the trend or forecast, intervals shaded and
  labelled, and the key event dates annotated.
- A backtest table: model vs baselines on the same folds.
