# API guide

Prefix `/api`. Register/login with POST `/auth/register` or `/auth/login` using email/password JSON. GET `/auth/session` restores the user and CSRF token. Browser session cookies are HttpOnly. Include `X-CSRF-Token` on authenticated writes and a trusted Origin for browser requests. POST `/auth/logout` revokes the session.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | /v1/portfolios | List/create owned portfolios |
| PATCH | /v1/portfolios/{id} | Change name/description |
| GET/POST | /v1/portfolios/{id}/analyses | List/create saved analyses |
| GET | /v1/analyses | List all owned analyses |
| GET | /v1/analyses/{id} | Retrieve frozen result |
| GET | /v1/analyses/{id}/report?format=json or csv | Download snapshot/value series |
| POST | /v1/comparisons | Compare analysis_ids (2–10, same currency) |
| POST | /v1/imports/prices/preview | Validate csv_text; returns rows/errors/valid |

Use `examples/analysis.json` as a complete analysis request. Analysis creation requires `Idempotency-Key` (1–100 characters). Repeating an identical key/input returns the original record; changed inputs with the same key return 409. Keys are scoped to each portfolio and protected by a database uniqueness constraint.

CSV header must be exactly `date,asset,price`; dates are ISO dates, identifiers are case-sensitive, prices are positive and finite. Maximum 20,000 rows, 20 allocations and 500,000 CSV characters. Every allocated asset and benchmark must have identical calendars and at least three observations. Only nonnegative weights summing to one within 1e-8 are accepted. Errors contain safe field paths and explanatory messages, without echoing passwords.
