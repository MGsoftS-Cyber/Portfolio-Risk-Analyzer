import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, setCsrfToken } from "./api";
import AuthScreen from "./components/AuthScreen";
import "./styles.css";
const sample = {
  scenario_name: "Balanced model",
  currency: "USD",
  allocations: [
    { asset: "EQUITY", weight: 0.6 },
    { asset: "BOND", weight: 0.4 },
  ],
  prices: [
    { date: "2026-01-28", asset: "EQUITY", price: 100 },
    { date: "2026-01-28", asset: "BOND", price: 100 },
    { date: "2026-01-29", asset: "EQUITY", price: 120 },
    { date: "2026-01-29", asset: "BOND", price: 101 },
    { date: "2026-01-30", asset: "EQUITY", price: 90 },
    { date: "2026-01-30", asset: "BOND", price: 102 },
    { date: "2026-02-02", asset: "EQUITY", price: 99 },
    { date: "2026-02-02", asset: "BOND", price: 103 },
    { date: "2026-02-03", asset: "EQUITY", price: 105 },
    { date: "2026-02-03", asset: "BOND", price: 104 },
  ],
  rebalancing: "buy_and_hold",
  source: "Synthetic demonstration",
  adjustment_method: "total_return",
  benchmark_asset: "EQUITY",
  stress_shocks: { EQUITY: -0.2, BOND: -0.05 },
};
const pct = (v) => (v == null ? "Unavailable" : (v * 100).toFixed(2) + "%");
function App() {
  const [user, U] = useState(null),
    [units, P] = useState([]),
    [selected, S] = useState(""),
    [data, D] = useState(sample),
    [runs, R] = useState([]),
    [result, V] = useState(null),
    [error, E] = useState(""),
    [busy, B] = useState(false),
    [preview, Q] = useState(null),
    [checked, C] = useState([]),
    [comparison, K] = useState(null);
  async function task(fn) {
    B(true);
    E("");
    try {
      await fn();
    } catch (e) {
      E(e.message);
    } finally {
      B(false);
    }
  }
  async function load() {
    P(await api("/v1/portfolios"));
    R(await api("/v1/analyses"));
  }
  useEffect(() => {
    api("/auth/session")
      .then(async (s) => {
        U(s.user);
        setCsrfToken(s.csrf_token);
        await load();
      })
      .catch(() => {});
  }, []);
  async function auth(registering, body) {
    await task(async () => {
      let s = await api("/auth/" + (registering ? "register" : "login"), {
        method: "POST",
        body: JSON.stringify(body),
      });
      setCsrfToken(s.csrf_token);
      U(s.user);
      await load();
    });
  }
  if (!user) return <AuthScreen onSubmit={auth} busy={busy} error={error} />;
  return (
    <div className="shell">
      <aside>
        <h2>◈ Portfolio Risk</h2>
        <p>Performance & research</p>
        <nav>
          <b>Portfolio analysis</b>
          <p>Saved scenarios</p>
          <p>Methodology</p>
        </nav>
        <small>{user.email}</small>
        <button
          onClick={() =>
            task(async () => {
              await api("/auth/logout", { method: "POST" });
              U(null);
              setCsrfToken("");
            })
          }
        >
          Sign out
        </button>
      </aside>
      <main>
        <header>
          <p className="eyebrow">INVESTMENT ANALYTICS</p>
          <h1>Understand your portfolio risk</h1>
          <p className="muted">
            Compare allocations with transparent data and reproducible
            calculations.
          </p>
        </header>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <section className="card">
          <h2>Your portfolios</h2>
          <label>
            Portfolio
            <select
              aria-label="Portfolio"
              value={selected}
              onChange={(e) => S(e.target.value)}
            >
              <option value="">Select a portfolio</option>
              {units.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const name = new FormData(e.target).get("name");
              task(async () => {
                let p = await api("/v1/portfolios", {
                  method: "POST",
                  body: JSON.stringify({ name, description: "" }),
                });
                S(p.id);
                await load();
                e.target.reset();
              });
            }}
          >
            <label>
              Portfolio name
              <input name="name" required maxLength={120} />
            </label>
            <button disabled={busy}>Create portfolio</button>
          </form>
        </section>
        <section className="card">
          <h2>Model assumptions</h2>
          <div className="grid">
            <label>
              Scenario name
              <input
                value={data.scenario_name}
                onChange={(e) => D({ ...data, scenario_name: e.target.value })}
              />
            </label>
            <label>
              Rebalancing
              <select
                aria-label="Rebalancing"
                value={data.rebalancing}
                onChange={(e) => D({ ...data, rebalancing: e.target.value })}
              >
                <option value="buy_and_hold">Buy and hold</option>
                <option value="monthly">Monthly</option>
              </select>
            </label>
            <label>
              Currency
              <input
                value={data.currency}
                maxLength={3}
                onChange={(e) =>
                  D({ ...data, currency: e.target.value.toUpperCase() })
                }
              />
            </label>
            <label>
              Annual risk-free rate
              <input
                type="number"
                step=".001"
                value={data.risk_free_annual || 0}
                onChange={(e) =>
                  D({ ...data, risk_free_annual: Number(e.target.value) })
                }
              />
            </label>
          </div>
          <p>
            Weights are fractions: 0.60 means 60%. All assets must use the same
            currency and observation dates.
          </p>
          <h3>Allocation and stress assumptions</h3>
          {data.allocations.map((allocation, index) => (
            <div className="grid" key={index}>
              <label>
                Asset identifier
                <input
                  aria-label={`Asset ${index + 1}`}
                  value={allocation.asset}
                  onChange={(e) => {
                    const old = allocation.asset;
                    const allocations = data.allocations.map((a, i) =>
                      i === index ? { ...a, asset: e.target.value } : a,
                    );
                    const shocks = { ...data.stress_shocks };
                    const shock = shocks[old];
                    delete shocks[old];
                    shocks[e.target.value] = shock || 0;
                    D({ ...data, allocations, stress_shocks: shocks });
                  }}
                />
              </label>
              <label>
                Weight
                <input
                  aria-label={`Weight ${index + 1}`}
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={allocation.weight}
                  onChange={(e) =>
                    D({
                      ...data,
                      allocations: data.allocations.map((a, i) =>
                        i === index
                          ? { ...a, weight: Number(e.target.value) }
                          : a,
                      ),
                    })
                  }
                />
              </label>
              <label>
                Hypothetical shock
                <input
                  aria-label={`Shock ${index + 1}`}
                  type="number"
                  min="-1"
                  max="1"
                  step="0.01"
                  value={data.stress_shocks[allocation.asset] || 0}
                  onChange={(e) =>
                    D({
                      ...data,
                      stress_shocks: {
                        ...data.stress_shocks,
                        [allocation.asset]: Number(e.target.value),
                      },
                    })
                  }
                />
              </label>
              <button
                className="text-button"
                disabled={data.allocations.length === 1}
                onClick={() => {
                  const shocks = { ...data.stress_shocks };
                  delete shocks[allocation.asset];
                  D({
                    ...data,
                    allocations: data.allocations.filter((_, i) => i !== index),
                    stress_shocks: shocks,
                  });
                }}
              >
                Remove asset {index + 1}
              </button>
            </div>
          ))}
          <button
            className="text-button"
            disabled={data.allocations.length >= 20}
            onClick={() =>
              D({
                ...data,
                allocations: [
                  ...data.allocations,
                  { asset: `ASSET${data.allocations.length + 1}`, weight: 0 },
                ],
              })
            }
          >
            Add asset
          </button>
          <label>
            Price CSV
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files[0];
                if (f)
                  task(async () => {
                    if (f.size > 500000)
                      throw Error("Maximum CSV size is 500 KB.");
                    Q(
                      await api("/v1/imports/prices/preview", {
                        method: "POST",
                        body: JSON.stringify({ csv_text: await f.text() }),
                      }),
                    );
                  });
              }}
            />
          </label>
          {preview && (
            <div className="import-preview">
              <p>{preview.rows.length} valid observations</p>
              {preview.errors.map((x, i) => (
                <p key={i}>
                  Row {x.row}: {x.message}
                </p>
              ))}
              <button
                disabled={!preview.valid}
                onClick={() => {
                  D({ ...data, prices: preview.rows, source: "User CSV" });
                  Q(null);
                }}
              >
                Apply imported prices
              </button>
            </div>
          )}
          <details>
            <summary>Data provenance and observations</summary>
            <label>
              Source
              <input
                value={data.source}
                onChange={(e) => D({ ...data, source: e.target.value })}
              />
            </label>
            <label>
              Adjustment methodology
              <select
                value={data.adjustment_method}
                onChange={(e) =>
                  D({ ...data, adjustment_method: e.target.value })
                }
              >
                <option value="total_return">Total return adjusted</option>
                <option value="price_only">Price only</option>
              </select>
            </label>
            <label>
              Benchmark asset
              <input
                value={data.benchmark_asset || ""}
                onChange={(e) =>
                  D({ ...data, benchmark_asset: e.target.value || null })
                }
              />
            </label>
            <pre>{JSON.stringify(data.prices, null, 2)}</pre>
          </details>
          <p>
            {data.prices.length} observations loaded. Demonstration prices are
            synthetic.
          </p>
          <button
            disabled={busy || !selected}
            onClick={() =>
              task(async () => {
                V(
                  await api("/v1/portfolios/" + selected + "/analyses", {
                    method: "POST",
                    headers: { "Idempotency-Key": crypto.randomUUID() },
                    body: JSON.stringify(data),
                  }),
                );
                await load();
              })
            }
          >
            Analyze and save scenario
          </button>
        </section>
        {result && (
          <section className="card">
            <h2>Historical results</h2>
            <div className="metrics">
              {[
                ["Total return", pct(result.results.cumulative_return)],
                ["Volatility", pct(result.results.annualized_volatility)],
                ["Max drawdown", pct(result.results.maximum_drawdown)],
                [
                  "Sharpe ratio",
                  result.results.sharpe_ratio?.toFixed(3) || "Unavailable",
                ],
              ].map(([k, v]) => (
                <div className="metric" key={k}>
                  <small>{k}</small>
                  <strong>{v}</strong>
                </div>
              ))}
            </div>
            <h3>Portfolio value · initial index 100</h3>
            <svg
              viewBox="0 0 700 180"
              role="img"
              aria-label="Portfolio value chart"
            >
              <polyline
                fill="none"
                stroke="#16a394"
                strokeWidth="3"
                points={result.results.series
                  .map((x, i) => {
                    let vs = result.results.series.map((x) => x.value),
                      lo = Math.min(...vs),
                      hi = Math.max(...vs);
                    return `${(i * 680) / (vs.length - 1) + 10},${160 - ((x.value - lo) / (hi - lo || 1)) * 140}`;
                  })
                  .join(" ")}
              />
            </svg>
            <p>
              Hypothetical stress return: {pct(result.results.stress_return)}
            </p>
            <h3>Asset correlations</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Asset</th>
                    {result.results.assets.map((a) => (
                      <th key={a}>{a}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.results.correlations.map((row, i) => (
                    <tr key={i}>
                      <th>{result.results.assets[i]}</th>
                      {row.map((v, j) => (
                        <td key={j}>
                          {v == null ? "Undefined" : v.toFixed(3)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {result.results.warnings.map((w) => (
              <p className="muted" key={w}>
                {w}
              </p>
            ))}
            <a href={"/api/v1/analyses/" + result.id + "/report"}>
              Download report
            </a>{" "}
            ·{" "}
            <a href={"/api/v1/analyses/" + result.id + "/report?format=csv"}>
              Download value CSV
            </a>{" "}
            ·{" "}
            <button className="text-button" onClick={() => window.print()}>
              Print report
            </button>
          </section>
        )}
        <section className="card">
          <h2>Saved scenarios</h2>
          {runs.map((a) => (
            <div className="saved" key={a.id}>
              <input
                type="checkbox"
                aria-label={"Compare " + a.inputs.scenario_name}
                checked={checked.includes(a.id)}
                onChange={(e) =>
                  C(
                    e.target.checked
                      ? [...checked, a.id]
                      : checked.filter((x) => x !== a.id),
                  )
                }
              />
              <button className="text-button" onClick={() => V(a)}>
                {a.inputs.scenario_name}
              </button>
              <span>{pct(a.results.cumulative_return)}</span>
            </div>
          ))}
          <button
            disabled={checked.length < 2 || checked.length > 10 || busy}
            onClick={() =>
              task(async () =>
                K(
                  await api("/v1/comparisons", {
                    method: "POST",
                    body: JSON.stringify({ analysis_ids: checked }),
                  }),
                ),
              )
            }
          >
            Compare selected scenarios
          </button>
          {comparison && (
            <div>
              <h3>Scenario comparison</h3>
              <p>{comparison.message}</p>
              {comparison.analyses.map((a) => (
                <p key={a.id}>
                  {a.inputs.scenario_name}: return{" "}
                  {pct(a.results.cumulative_return)} · drawdown{" "}
                  {pct(a.results.maximum_drawdown)}
                </p>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
