# API (`apps/api`)

Flask 3.1 application factory for the Smart Food Supply Chain & Surplus
Redistribution System. It talks to MySQL through SQLAlchemy 2 and PyMySQL and
uses the approved post-migration schema without runtime DDL or `create_all()`.

## Layout

```text
src/sfc_api/
  __init__.py          factory: logging, extensions, errors, request log, auth, blueprints, CLI
  config.py            frozen Settings loaded from environment or protected files
  extensions.py        engine/session lifecycle and request teardown
  models/              SQLAlchemy mappings for 17 tables and 3 reporting views
  api/                 auth, users, donations, inspections, deliveries, spoilage,
                       branches, routes, dependents, lookups, reports
  auth/                session cookies, CSRF/origin guard, middleware, login/reset service
  services/            scope, serializers, reconciliation, accounts, common helpers
  schemas/requests.py  Pydantic v2 strict request models
  security/            scrypt password policy, opaque tokens, HMAC CSRF
  cli.py               operator provisioning and queue commands (sfc_ops)
tests/                 unit, contract, integration and security tests
```

## Configuration

Copy `.env.example` to `.env` for local use. `.env` is ignored by git.

| Variable | Purpose |
| --- | --- |
| `SFC_ENV` | `development`, `testing`, or `production` |
| `SECRET_KEY` / `SECRET_KEY_FILE` | Session signing secret; file is preferred |
| `APP_TIMEZONE` | Display/report timezone, default `Asia/Kolkata` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `APP_ORIGINS` | Comma-separated allowed browser origins for mutating requests |
| `DATABASE_URL` | MySQL URL for `sfc_app`, without a password |
| `SFC_DB_PASSWORD_FILE` | Protected file containing the `sfc_app` password |
| `SFC_OPS_DATABASE_URL` | MySQL URL for `sfc_ops`, operator CLI only |
| `SFC_OPS_PASSWORD_FILE` | Protected file containing the `sfc_ops` password |
| `SFC_API_TEST_PASSWORD_FILE` | Protected file for `sfc_api_test` integration tests |
| `SFC_COOKIE_SECURE` | Set `true` behind HTTPS; otherwise cookies omit `Secure` in local dev |

The application refuses to start in production without a secret. Database
passwords are never embedded in URLs or repr output. Logging redacts the
configured secrets and common credential patterns.

## Run

```powershell
python -m flask --app sfc_api run --host 127.0.0.1 --port 5000
```

Flask CLI loads `.env` automatically. The frontend dev server proxies `/api`
to this port.

## API surface

All routes are under `/api`; successful responses use
`{"data": …, "meta": {}}` and errors use
`{"error": {"code", "message", "details"?}, "request_id"}`. Every response
carries `X-Request-ID`.

| Area | Routes |
| --- | --- |
| Auth | `GET /auth/csrf`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/activate`, `POST /auth/password-reset/confirm`, `POST /auth/password/change` (and `/auth/password`) |
| Users | `GET/PATCH /users`, `GET /users/<id>`, `POST /users/<id>/activation-token`, `POST /users/<id>/reset-token`, `GET /users/me/activity` |
| Donations | `GET/POST /donations`, `GET/PATCH /donations/<id>`, route/status/history/items/inspections sub-resources |
| Inspections | `GET /inspections`, `GET /inspections/queue`, `GET /inspections/<id>`, `POST /inspections`, `POST /donations/<id>/inspections` |
| Deliveries | `GET/POST /deliveries`, detail, status, item add/edit/delete, review, flat `/delivery-items/<id>` |
| Spoilage | `GET/POST /spoilage`, `GET /spoilage/<id>` |
| Branches | `GET/POST /branches`, `GET/PATCH /branches/<id>` |
| Routes | `GET/POST /routes`, `GET/PATCH /routes/<id>`, route assignments, `/route-assignments` alias |
| Lookups | `GET /organizations`, `/coverage-areas`, `/food-categories`, `/lookups/*` |
| Dependents | `GET/POST /dependents`, nested and flat patch/delete |
| Reports | `/reports/overview`, `/reports/donors`, `/reports/donors/<id>`, `/reports/drivers`, `/reports/branches`, `/reports/freshness`, `/activity` |
| Health | `GET /health` |

Reports accept `?export=csv` and emit an ETag with `304` support.

## Security model

- Passwords: Werkzeug scrypt (`scrypt:32768:8:1`), minimum 12 characters,
  maximum 128, common-password/email/name rejection, timing-safe unknown-user
  checks.
- Sessions: signed HttpOnly cookie containing `uid`, `sid`, `iat`, `seen`,
  `epoch`, and `csrf_id`; 8-hour idle and 12-hour absolute limits; current
  role/branch/status reloaded on every request.
- CSRF: session-bound double-submit token; mutating requests must also come
  from an allowed `Origin`/`Referer`.
- Lockout: five failed attempts in fifteen minutes locks the account for
  fifteen minutes; login attempts are rate-limited per IP and email.
- Tokens: opaque activation/reset tokens are stored as SHA-256 hashes, expire
  after 24 h/1 h, and are shown once.
- Scope: managers see only branches where `regional_manager_user_id` is their
  account; out-of-scope records return 404, not 403. Drivers see their own
  deliveries/dependents/routes. Inspectors see the collected queue.

## Tests

```powershell
python -m pytest -q
python -m ruff check src tests
python -m black --check src tests
python -m mypy
```

Integration tests truncate and seed `smart_food_supply_chain_api_test` with
users 1–10, two branches, routes, categories, and credentials. They skip when
the protected test credentials are missing and refuse any other database name.

## Known schema limits

- **G12**: no delivery-status history table; current delivery status and
  timestamps are authoritative.
- **G13**: no donation close-out table; `COMPLETED` is derived from delivered
  and spoiled quantities.
- **G15**: allocation capacity checks available quantity at request time, not
  a status-aware reservation ledger.
