import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.schemas import PortfolioInput
from app.engine import evaluate
from app.imports import preview_prices


def payload():
    return json.loads((Path(__file__).parents[2] / "examples/analysis.json").read_text())


def test_buy_hold():
    result = evaluate(PortfolioInput(**payload()))
    assert result["cumulative_return"] == pytest.approx(0.046)
    assert result["maximum_drawdown"] == pytest.approx(1 - 94.8 / 112.4)
    assert result["final_weights"]["EQUITY"] == pytest.approx(63 / 104.6)


def test_monthly():
    d = payload()
    d["rebalancing"] = "monthly"
    result = evaluate(PortfolioInput(**d))
    assert result["cumulative_return"] != pytest.approx(0.046)
    assert sum(result["final_weights"].values()) == pytest.approx(1)


@pytest.mark.parametrize("change", ["weights", "missing", "duplicate", "negative", "unused", "shock"])
def test_reject_bad_data(change):
    d = payload()
    if change == "weights":
        d["allocations"][0]["weight"] = 0.8
    if change == "missing":
        d["prices"].pop()
    if change == "duplicate":
        d["prices"].append(d["prices"][0])
    if change == "negative":
        d["prices"][0]["price"] = -1
    if change == "unused":
        d["prices"][0]["asset"] = "OTHER"
    if change == "shock":
        d["stress_shocks"]["EQUITY"] = -2
    with pytest.raises(ValidationError):
        PortfolioInput(**d)


def test_zero_volatility():
    d = payload()
    for p in d["prices"]:
        p["price"] = 100
    r = evaluate(PortfolioInput(**d))
    assert r["sharpe_ratio"] is None
    assert r["maximum_drawdown"] == 0
    assert r["correlations"][0][0] is None


def test_single_asset():
    d = payload()
    d["allocations"] = [{"asset": "EQUITY", "weight": 1}]
    d["prices"] = [p for p in d["prices"] if p["asset"] == "EQUITY"]
    d["stress_shocks"] = {}
    r = evaluate(PortfolioInput(**d))
    assert r["maximum_drawdown"] == pytest.approx(0.25)
    assert r["cumulative_return"] == pytest.approx(0.05)


@pytest.mark.parametrize(
    "text", ["bad", "date,asset,price\n2026-01-01,A,-1", "date,asset,price\n2026-01-01,A,1\n2026-01-01,A,2"]
)
def test_csv_invalid(text):
    assert not preview_prices(text)["valid"]


def test_csv_valid():
    assert preview_prices("date,asset,price\n2026-01-01,A,100")["valid"]


def register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "long-test-password"})
    assert r.status_code == 201
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]


def test_owned_analysis_and_exports(client):
    register(client, "one@example.com")
    p = client.post("/api/v1/portfolios", json={"name": "Research"}).json()["id"]
    path = f"/api/v1/portfolios/{p}/analyses"
    a = client.post(path, json=payload(), headers={"Idempotency-Key": "first"})
    assert a.status_code == 201
    a = a.json()
    assert client.post(path, json=payload(), headers={"Idempotency-Key": "first"}).json()["id"] == a["id"]
    d = payload()
    d["scenario_name"] = "Changed"
    assert client.post(path, json=d, headers={"Idempotency-Key": "first"}).status_code == 409
    assert client.get("/api/v1/analyses/" + a["id"] + "/report").status_code == 200
    assert "portfolio_value" in client.get("/api/v1/analyses/" + a["id"] + "/report?format=csv").text
    client.post("/api/auth/logout")
    register(client, "two@example.com")
    assert client.get("/api/v1/analyses/" + a["id"]).status_code == 404
    assert client.get(f"/api/v1/portfolios/{p}/analyses").status_code == 404


def test_csrf(client):
    register(client, "csrf@example.com")
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/portfolios", json={"name": "Forbidden"}).status_code == 403


def test_auth_required(client):
    assert client.get("/api/v1/portfolios").status_code == 401


def test_comparison_and_snapshot(client):
    register(client, "compare@example.com")
    pid = client.post("/api/v1/portfolios", json={"name": "Model"}).json()["id"]
    path = f"/api/v1/portfolios/{pid}/analyses"
    original = payload()
    a = client.post(path, json=original, headers={"Idempotency-Key": "a"}).json()
    modified = payload()
    modified["rebalancing"] = "monthly"
    b = client.post(path, json=modified, headers={"Idempotency-Key": "b"}).json()
    response = client.post("/api/v1/comparisons", json={"analysis_ids": [a["id"], b["id"]]})
    assert response.status_code == 200
    assert client.get("/api/v1/analyses/" + a["id"]).json()["inputs"]["rebalancing"] == "buy_and_hold"
    assert client.post("/api/v1/comparisons", json={"analysis_ids": [a["id"], a["id"]]}).status_code == 422


def test_missing_idempotency(client):
    register(client, "key@example.com")
    pid = client.post("/api/v1/portfolios", json={"name": "Model"}).json()["id"]
    assert client.post(f"/api/v1/portfolios/{pid}/analyses", json=payload()).status_code == 422


def test_benchmark_and_stress():
    r = evaluate(PortfolioInput(**payload()))
    assert r["series"][-1]["benchmark_value"] == pytest.approx(105)
    assert r["stress_return"] == pytest.approx(-(63 / 104.6) * 0.2 - (41.6 / 104.6) * 0.05)
