# Smart Food Supply Chain & Surplus Redistribution System

A database-backed application for moving surplus food from donors to the
people who need it, with explicit quantities, branch-scoped roles, and a
traceable donation lifecycle.

This repository contains the complete **Step 7** application:

- a Flask API backed by MySQL through SQLAlchemy models;
- four role workspaces for donors, NGO managers, drivers, and safety
  inspectors;
- server-side sessions, CSRF protection, activation/reset tokens, lockout,
  and role/branch scoping;
- integration tests against an isolated test database, plus API, security,
  UI, and reporting coverage.

The approved contracts in [`docs/architecture`](docs/architecture) and the
post-migration schema in
[`database/schema_post_migrations.sql`](database/schema_post_migrations.sql)
remain authoritative. `database/schema.sql` is frozen.

## Repository layout

```text
apps/api/            Flask application factory, API, models, auth, services, tests
apps/web/            React 19 + Vite + TypeScript + Tailwind v4 role workspaces
database/            Existing SQL, migrations, audit material, and frozen schema
docs/architecture/   Approved architecture, API, security, role, and UI contracts
reports/step7/       Stage A and final application reports
```

## Prerequisites

- Python **3.13.5**
- Node.js **22+** (verified on Node 24.20.0) and npm
- MySQL **8.0** for the API and integration tests

## Database boundary

Use only these databases:

| Database | Purpose | Account |
| --- | --- | --- |
| `smart_food_supply_chain` | Frozen original; the application must never access it | none |
| `smart_food_supply_chain_dev` | Manual development/demo database | `sfc_app` |
| `smart_food_supply_chain_api_test` | Automated tests only | `sfc_api_test` |

The schema is created by importing `database/schema_post_migrations.sql`.
There is no `create_all()`, no Alembic migration chain, and no runtime DDL.
Automated mutating tests refuse any database whose name is not exactly
`smart_food_supply_chain_api_test`.

Passwords and secrets live outside the repository. Point the `*_FILE`
variables at protected files; never put a real password in `.env`,
`.env.example`, source code, logs, or a commit.

## Backend (`apps/api`)

```powershell
cd apps/api
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# Edit .env: point SECRET_KEY_FILE and the password files outside the repo.
python -m flask --app sfc_api run --host 127.0.0.1 --port 5000
```

`GET http://127.0.0.1:5000/api/health` returns the API envelope and an
`X-Request-ID`. All success responses use `{"data": …, "meta": {}}`; errors use
`{"error": {"code", "message", "details"?}, "request_id"}`.

Run the backend checks from `apps/api`:

```powershell
python -m pytest
python -m ruff check src tests
python -m black --check src tests
python -m mypy
```

The database-backed tests use `sfc_api_test`, truncate and re-seed the test
tables, and are skipped when the protected test credentials are absent.

Operator provisioning uses `sfc_ops` and never the HTTP-serving account:

```powershell
python -m flask --app sfc_api operator create-user --email ... --full-name ... --phone ... --role DONOR
python -m flask --app sfc_api operator issue-activation --email ...
python -m flask --app sfc_api operator issue-reset --email ...
python -m flask --app sfc_api operator set-donor-branch --email ... --branch-id 1
```

Tokens are printed once and never stored in logs. See
[`apps/api/README.md`](apps/api/README.md) for the API surface and security
details.

## Frontend (`apps/web`)

```powershell
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies same-origin `/api` requests to
`http://127.0.0.1:5000`; run Flask in a second terminal.

```powershell
npm test          # Vitest + Testing Library
npm run typecheck # TypeScript project build
npm run lint      # oxlint
npm run build     # production type-check and assets
```

The interface uses Oat `#F4F0E6`, Forest `#21483B`, and Terracotta
`#D9844B`, with Fraunces headings and Manrope body copy. Terracotta is
decorative only, not body text. Counts and kilograms are read from the API;
the UI does not invent figures or charts.

Role workspaces:

- **Donor** — donations, new donation, impact, freshness, activity.
- **NGO manager** — donations, inspections, deliveries, allocation,
  spoilage, reports, branches, routes, people, freshness, activity.
- **Driver** — today, deliveries, spoilage, routes, history, dependents.
- **Safety inspector** — inspection queue, freshness, activity.

Reports support CSV export, ETag revalidation, and a print view at
`/print/reports/<branches|donors|drivers|freshness>`.

## Known schema limits (documented, not hidden)

- **G12** — the frozen schema has no delivery-status history table. The
  delivery's current status and timestamps are the authoritative record.
- **G13** — there is no donation close-out table; completion is derived from
  delivered and spoiled quantities.
- **G15** — allocation capacity is enforced against the current available
  quantity, not a status-aware reservation ledger.

These limits are documented in the architecture and report rather than
papered over with new tables or fabricated data.

## Status

See [`reports/step7/FINAL_APPLICATION_REPORT.md`](reports/step7/FINAL_APPLICATION_REPORT.md)
for the final implementation manifest, verification commands, results, and
deferred items.
