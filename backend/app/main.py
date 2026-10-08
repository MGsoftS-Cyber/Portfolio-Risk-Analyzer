"""HTTP application: authentication, unit ownership, and saved analysis workflows."""

import csv
import io
import json
import secrets
import time
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from . import config
from .database import get_db
from .models import User, LoginSession, Portfolio, Analysis
from .schemas import Credentials, PortfolioMetadata, PortfolioInput, ComparisonInput, CsvPreviewInput
from .imports import preview_prices
from .engine import evaluate, ENGINE_VERSION
from .security import current_user, digest, hasher, DUMMY_HASH, require_trusted_origin, throttle


app = FastAPI(
    title="Portfolio Risk Analyzer",
    version="1.0.0",
    description="Historical model-portfolio performance and risk with immutable analysis snapshots.",
)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Never echo submitted values: validation failures may contain passwords.
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Review the highlighted fields.",
                "fields": [{"path": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()],
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)}},
    )


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "engine_version": ENGINE_VERSION}


def issue_session(user, response, db):
    token, csrf = secrets.token_urlsafe(32), secrets.token_hex(32)
    db.add(
        LoginSession(
            token_hash=digest(token), user_id=user.id, csrf_token=csrf, expires_at=time.time() + config.SESSION_SECONDS
        )
    )
    db.commit()
    response.set_cookie(
        "portfolio_session",
        token,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        max_age=config.SESSION_SECONDS,
        path="/",
    )
    return {"user": {"id": user.id, "email": user.email}, "csrf_token": csrf}


@app.post("/api/auth/register", status_code=201)
def register(data: Credentials, request: Request, response: Response, db=Depends(get_db)):
    require_trusted_origin(request)
    throttle(request)
    user = User(email=data.email, password_hash=hasher.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None
    return issue_session(user, response, db)


@app.post("/api/auth/login")
def login(data: Credentials, request: Request, response: Response, db=Depends(get_db)):
    require_trusted_origin(request)
    throttle(request)
    user = db.scalar(select(User).where(User.email == data.email))
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, data.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not valid or user is None:
        raise HTTPException(401, "Email or password is incorrect.")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(data.password)
    return issue_session(user, response, db)


@app.get("/api/auth/session")
def session(request: Request, user=Depends(current_user)):
    return {"user": {"id": user.id, "email": user.email}, "csrf_token": request.state.login_session.csrf_token}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
    db.delete(request.state.login_session)
    db.commit()
    response.delete_cookie("portfolio_session", path="/")


def calculate_safely(data):
    """Reject numerical overflow instead of storing an invalid JSON result."""
    try:
        import numpy as np

        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = evaluate(data)
        json.dumps(result, allow_nan=False)
        return result
    except (FloatingPointError, OverflowError, ValueError):
        raise HTTPException(
            422, "These price changes exceed the numerical calculation range. Review the dataset."
        ) from None


def owned_portfolio(portfolio_id, user, db):
    unit = db.scalar(select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id))
    if unit is None:
        raise HTTPException(404, "Business unit not found in your account.")
    return unit


def portfolio_view(unit):
    return {
        "id": unit.id,
        "name": unit.name,
        "description": unit.description,
        "created_at": unit.created_at,
    }


def analysis_view(analysis):
    return {
        "id": analysis.id,
        "portfolio_id": analysis.portfolio_id,
        "inputs": analysis.inputs,
        "results": analysis.results,
        "engine_version": analysis.engine_version,
        "created_at": analysis.created_at,
    }


@app.get("/api/v1/portfolios")
def portfolios(user=Depends(current_user), db=Depends(get_db)):
    return [
        portfolio_view(p)
        for p in db.scalars(select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at.desc()))
    ]


@app.get("/api/v1/analyses")
def all_analyses(user=Depends(current_user), db=Depends(get_db)):
    """List owned scenarios across portfolios so alternative portfolios can be compared."""
    statement = (
        select(Analysis)
        .join(Portfolio, Analysis.portfolio_id == Portfolio.id)
        .where(Portfolio.user_id == user.id)
        .order_by(Analysis.created_at.desc())
    )
    return [analysis_view(item) for item in db.scalars(statement)]


@app.post("/api/v1/portfolios", status_code=201)
def create_portfolio(data: PortfolioMetadata, user=Depends(current_user), db=Depends(get_db)):
    unit = Portfolio(user_id=user.id, **data.model_dump())
    db.add(unit)
    db.commit()
    return portfolio_view(unit)


@app.patch("/api/v1/portfolios/{portfolio_id}")
def edit_portfolio(portfolio_id: str, data: PortfolioMetadata, user=Depends(current_user), db=Depends(get_db)):
    unit = owned_portfolio(portfolio_id, user, db)
    unit.name, unit.description = data.name, data.description
    db.commit()
    return portfolio_view(unit)


@app.get("/api/v1/portfolios/{portfolio_id}/analyses")
def history(portfolio_id: str, user=Depends(current_user), db=Depends(get_db)):
    owned_portfolio(portfolio_id, user, db)
    return [
        analysis_view(a)
        for a in db.scalars(
            select(Analysis).where(Analysis.portfolio_id == portfolio_id).order_by(Analysis.created_at.desc())
        )
    ]


@app.post("/api/v1/portfolios/{portfolio_id}/analyses", status_code=201)
def run_analysis(
    portfolio_id: str,
    data: PortfolioInput,
    idempotency_key: str = Header(min_length=1, max_length=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    owned_portfolio(portfolio_id, user, db)
    key = idempotency_key
    if not 1 <= len(key) <= 100:
        raise HTTPException(422, "Supply an Idempotency-Key header containing 1–100 characters.")
    snapshot = data.model_dump(mode="json")
    existing = db.scalar(select(Analysis).where(Analysis.portfolio_id == portfolio_id, Analysis.idempotency_key == key))
    if existing:
        if existing.inputs != snapshot:
            raise HTTPException(409, "This idempotency key was already used with different assumptions.")
        return analysis_view(existing)
    analysis = Analysis(
        portfolio_id=portfolio_id,
        idempotency_key=key,
        inputs=snapshot,
        results=calculate_safely(data),
        engine_version=ENGINE_VERSION,
    )
    db.add(analysis)
    try:
        db.commit()
    except IntegrityError:
        # A unique database constraint resolves concurrent submissions, not just
        # a pre-insert lookup. Re-read the winning request after rollback.
        db.rollback()
        existing = db.scalar(
            select(Analysis).where(Analysis.portfolio_id == portfolio_id, Analysis.idempotency_key == key)
        )
        if existing is None or existing.inputs != snapshot:
            raise HTTPException(409, "A conflicting evaluation was submitted. Use a new idempotency key.") from None
        return analysis_view(existing)
    return analysis_view(analysis)


def owned_analysis(analysis_id, user, db):
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found in your account.")
    owned_portfolio(analysis.portfolio_id, user, db)
    return analysis


@app.get("/api/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str, user=Depends(current_user), db=Depends(get_db)):
    return analysis_view(owned_analysis(analysis_id, user, db))


@app.post("/api/v1/comparisons")
def compare(data: ComparisonInput, user=Depends(current_user), db=Depends(get_db)):
    analyses = [owned_analysis(identifier, user, db) for identifier in data.analysis_ids]
    if len({a.inputs["currency"] for a in analyses}) != 1:
        raise HTTPException(422, "Compare analyses in the same currency. Currency conversion is not performed.")
    return {
        "analyses": [analysis_view(a) for a in analyses],
        "message": "Compare periods, data sources, date ranges, rebalancing policy and assumptions before interpreting differences. No currency conversion or period normalization is applied.",
    }


@app.get("/api/v1/analyses/{analysis_id}/report")
def report(analysis_id: str, format: str = "json", user=Depends(current_user), db=Depends(get_db)):
    analysis = owned_analysis(analysis_id, user, db)
    if format == "json":
        return Response(
            json.dumps(analysis_view(analysis), indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="analysis-{analysis.id}.json"'},
        )
    if format != "csv":
        raise HTTPException(422, "Report format must be json or csv.")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "portfolio_value", "drawdown", "benchmark_value"])
    for row in analysis.results["series"]:
        writer.writerow([row["date"], row["value"], row["drawdown"], row["benchmark_value"]])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="portfolio-values-{analysis.id}.csv"'},
    )


@app.post("/api/v1/imports/prices/preview")
def preview_import(data: CsvPreviewInput, user=Depends(current_user)):
    return preview_prices(data.csv_text)


if config.STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def dashboard():
        return FileResponse(config.STATIC_DIR / "index.html")
