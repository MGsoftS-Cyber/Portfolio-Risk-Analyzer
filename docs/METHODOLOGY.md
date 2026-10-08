# Calculation methodology

The input is a model allocation, not an actual investment account history. Each series starts at an index of 100. The engine buys fractional quantities using initial weights and prices. Buy-and-hold keeps quantities constant. Monthly rebalancing trades at the last observed close of each month and affects the next return. At the final observed date, monthly weights are restored for the stress snapshot too. Prices are sorted by date; no missing values are forward-filled. Each observation is intended to be a daily close; users must verify frequency.

Simple return is V[t]/V[t-1]-1. Cumulative return is final/initial-1. Annualized growth uses the actual calendar duration divided by 365.25. Sample volatility uses ddof=1, multiplied by sqrt(annualization_factor), default 252. Sharpe uses mean periodic excess return times the annualization factor divided by annualized volatility; the annual effective risk-free rate is converted geometrically to a periodic rate. Volatility below 1e-12 gives an undefined Sharpe. Constant asset-return series give undefined correlation.

Drawdown is value/running_peak-1. Maximum drawdown is reported as a positive loss magnitude. Correlations use synchronized asset returns. Concentration is the sum of squared final weights. Stress return is the sum of final weight times a user-supplied asset shock; unlisted shocks are zero. Stress is a hypothetical one-step scenario, not a prediction.

The selected benchmark is normalized independently to 100 using matching dates and exported alongside portfolio values. Total-return adjusted series must already include distributions; dividends are never added again. Price-only mode excludes distributions. Fees and taxes are excluded. Single-currency input is a user assertion; the service cannot infer a CSV's currency.

NumPy float64 is suitable for this statistical model; the service does not calculate payment amounts. Invalid, duplicate or unmatched data is rejected. Numerical overflow rejects the evaluation rather than persisting NaN or infinity. Annualized growth outside numeric range is null with a warning.

Technical references: https://numpy.org/doc/stable/reference/generated/numpy.std.html and https://numpy.org/doc/stable/reference/generated/numpy.corrcoef.html.
