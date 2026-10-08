"""Pure historical simulation. No HTTP, database, or external data dependency.

Monthly trades occur after the last observed close of a month: the new weights
apply to the next return. Buy-and-hold maintains asset quantities as weights drift.
"""

import math
import numpy as np

ENGINE_VERSION = "1.0.0"


def evaluate(data):
    dates = sorted({p.date for p in data.prices})
    assets = [a.asset for a in data.allocations]
    lookup = {(p.date, p.asset): p.price for p in data.prices}
    prices = np.array([[lookup[d, a] for a in assets] for d in dates])
    weights = np.array([a.weight for a in data.allocations])
    units = 100 * weights / prices[0]
    values = [100.0]
    final_weights = weights
    for i in range(1, len(dates)):
        positions = units * prices[i]
        value = float(positions.sum())
        values.append(value)
        final_weights = positions / value
        if data.rebalancing == "monthly" and (
            i == len(dates) - 1 or dates[i + 1].month != dates[i].month or dates[i + 1].year != dates[i].year
        ):
            units = value * weights / prices[i]
            final_weights = weights
    values = np.array(values)
    returns = values[1:] / values[:-1] - 1
    dd = values / np.maximum.accumulate(values) - 1
    vol = float(np.std(returns, ddof=1) * math.sqrt(data.annualization_factor))
    rf = math.expm1(math.log1p(data.risk_free_annual) / data.annualization_factor)
    days = (dates[-1] - dates[0]).days
    annual_log = math.log(values[-1] / values[0]) * 365.25 / days
    annual_return = math.expm1(annual_log) if annual_log < 700 else None
    sharpe = float(np.mean(returns - rf) * data.annualization_factor / vol) if vol > 1e-12 else None
    asset_returns = prices[1:] / prices[:-1] - 1
    corr = []
    for j in range(len(assets)):
        row = []
        for k in range(len(assets)):
            x, y = asset_returns[:, j], asset_returns[:, k]
            row.append(float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 1e-12 and np.std(y) > 1e-12 else None)
        corr.append(row)
    bench = [None] * len(dates)
    if data.benchmark_asset:
        start = lookup[dates[0], data.benchmark_asset]
        bench = [100 * lookup[d, data.benchmark_asset] / start for d in dates]
    warnings = ["Historical results describe the supplied data; stress shocks are hypothetical scenarios."]
    if data.adjustment_method == "price_only":
        warnings.append("Price-only returns exclude dividend income.")
    if days < 365:
        warnings.append("Less than one year of data: annualized metrics may be unstable.")
    if annual_return is None:
        warnings.append("Annualized growth exceeds numeric range; result is unavailable.")
    return dict(
        cumulative_return=float(values[-1] / 100 - 1),
        annualized_return=annual_return,
        annualized_volatility=vol,
        sharpe_ratio=sharpe,
        maximum_drawdown=float(-min(dd)),
        assets=assets,
        correlations=corr,
        final_weights=dict(zip(assets, map(float, final_weights))),
        concentration=float(sum(final_weights**2)),
        stress_return=float(sum(final_weights[j] * data.stress_shocks.get(a, 0) for j, a in enumerate(assets))),
        series=[
            dict(date=str(d), value=float(values[i]), drawdown=float(dd[i]), benchmark_value=bench[i])
            for i, d in enumerate(dates)
        ],
        warnings=warnings,
        conventions=dict(
            initial_index=100,
            annualization_factor=data.annualization_factor,
            annual_return="calendar days / 365.25",
            volatility="sample standard deviation",
            missing_prices="reject",
            rebalancing=data.rebalancing,
            costs="excluded",
            currency="single currency, no conversion",
        ),
    )
