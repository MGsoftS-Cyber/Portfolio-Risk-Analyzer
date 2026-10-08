# Portfolio Risk Analyzer

Standalone account-based web application for historical model portfolios. FastAPI, React, NumPy, SQLAlchemy and Alembic. No bank connection or trading access is required.

## Quick start with Docker

1. Install Docker Desktop with Compose.
2. Copy `.env.example` to `.env` and set a long URL-safe database password.
3. Run `docker compose up --build` in this directory.
4. Open http://localhost:8082 and create an account (password: at least 12 characters).
5. Create a portfolio, use the synthetic sample allocation, and click **Analyze and save scenario**.
6. Change rebalancing to Monthly and save another scenario. Select both scenarios to compare.

PostgreSQL data persists in a named volume. `docker compose down` retains it; adding `-v` deletes it. This app uses separate ports, session cookies and database volume from the other two applications.

## Local development

Use Python 3.12 and Node 24. From backend:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8002
```

In a second terminal, from frontend:

```bash
npm ci
npm run dev
```

Open http://localhost:5175. SQLite is used locally unless DATABASE_URL is configured. The Vite proxy keeps cookie and CSRF requests same-origin. Interactive API documentation: http://localhost:8002/docs.

## Features and scope

Private portfolios; immutable analysis snapshots; idempotent saves; daily CSV validation; buy-and-hold and monthly rebalancing; cumulative and annualized return; volatility; Sharpe; drawdown; correlations; concentration; benchmark value series; stress shocks; comparison; JSON/CSV downloads and printable results.

Only single-currency long-only model portfolios are supported. Prices must have matching dates. No fees, taxes, borrowing, trades, deposits, withdrawals, or FX conversion are modeled. Adjusted price methodology is explicitly recorded. Sample data is synthetic. Billing, team administration, password recovery, real market-data integrations and actual-account transaction performance are future work.

See [Architecture](docs/ARCHITECTURE.md), [Methodology](docs/METHODOLOGY.md), [API](docs/API.md), [Production](docs/PRODUCTION.md), [Verification](docs/VERIFICATION.md) and [Contributing](CONTRIBUTING.md).
