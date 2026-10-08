# Contributing

Use Python 3.12 and Node 24. Keep financial functions independent of FastAPI, SQLAlchemy and market providers. Explain timing, undefined metrics and financial assumptions in docstrings rather than narrating obvious assignments. Preserve public contracts, account ownership checks and immutable snapshots.

Backend: `pip install -r requirements-dev.txt`, `pytest -q`, `ruff check app tests migrations`, `ruff format --check app tests migrations`, `alembic upgrade head`, `alembic check`. Frontend: `npm ci`, `npm run format:check`, `npm run build`. GitHub Actions repeats these checks and builds the Docker image.

Add regression tests for changed financial rules. Never commit personal holdings, credentials, .env, databases, generated builds or node_modules. Use synthetic data. PR descriptions should explain the observable change, financial conventions and validation performed.
