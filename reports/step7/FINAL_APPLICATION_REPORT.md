# Step 7 — Final Application Report

**Project:** Smart Food Supply Chain & Surplus Redistribution System  
**Date:** 2026-11-17  
**Branch:** `feature/step-7-application`  
**Commit:** single local commit, `Complete Step 7 full-stack application` (not pushed)

## 1. Outcome

Step 7 is implemented as a complete, database-backed application:

- Flask 3.1 API using SQLAlchemy 2.0 and PyMySQL against the frozen
  post-migration schema.
- Four role workspaces: donor, NGO manager, driver, and safety inspector.
- Server-side sessions, CSRF protection, login lockout, activation/reset
  tokens, role and branch scoping.
- Donation lifecycle from registration through inspection, approval,
  allocation, delivery, review, spoilage, and reconciliation.
- CSV reports, report print views, freshness and activity views.
- Automated backend, frontend, security, and live headless verification.

The approved documents in `docs/architecture/` and
`database/schema_post_migrations.sql` remain authoritative. `database/schema.sql`
was not changed. No Alembic migration chain, runtime DDL, or `create_all()` was
introduced.

## 2. Verification results

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `python -m pytest -q` in `apps/api` | **PASS** — 41 passed |
| Backend lint | `python -m ruff check src tests` | **PASS** — all checks passed |
| Backend format | `python -m black --check src tests` | **PASS** — 55 files unchanged |
| Backend types | `python -m mypy` | **PASS** — no issues in 46 source files |
| Frontend tests | `npm test` in `apps/web` | **PASS** — 16 passed, 3 files |
| Frontend types | `npm run typecheck` | **PASS** — no output/errors |
| Frontend build | `npm run build` | **PASS** — production build completed |
| Frontend lint | `npm run lint` | **PASS** — 0 errors; 3 pre-existing Fast Refresh warnings from shared UI/auth exports |
| Live UI flow | Edge headless via `playwright-core` | **PASS** — 11-step donation-to-review lifecycle, no page errors and no failed API responses |
| Role/navigation sweep | Edge headless | **PASS** — login redirect, all four role landings, manager reports/people, driver routes, inspector queue, mobile menu navigation |
| Accessibility | axe-core, WCAG 2 A/AA + 2.1 A/AA | **PASS** — 32 page/viewport scans, zero violations |
| Print views | `/print/reports/{branches,donors,drivers,freshness}` | **PASS** — all four render from the same API payload without shell navigation |
| Database integration | test DB only | **PASS** — 41 tests seed and mutate `smart_food_supply_chain_api_test`; allowlist assertion refuses other names |

The headless lifecycle created a donor donation, assigned a route, scheduled
and collected it, recorded a passing inspection, approved it, allocated a
delivery, started and completed the delivery as the attributed driver, saved a
receiving-manager review, and confirmed the donation reconciled to
`COMPLETED`.

## 3. Delivered application

### API

- Application factory with logging, request IDs, error envelope, session
  middleware, CSRF/origin guard, blueprint registration, and operator CLI.
- 17 mapped tables and 3 reporting views; no schema edits.
- 82 URL rules covering health, auth, users, donations, inspections,
  deliveries, delivery items, spoilage, branches, routes, route assignments,
  dependents, lookups, reports, and activity.
- Pydantic v2 strict request models; Decimal quantities; IST request handling;
  structured error codes for validation, scope, transitions, and database
  constraints.
- Reconciliation derives `PARTIALLY_DISTRIBUTED` and `COMPLETED` from stored
  delivered and spoiled quantities, with append-only history.
- Manager scope is exactly `branch.regional_manager_user_id = current user`.
  Out-of-scope records return 404.
- Operator-only provisioning uses `sfc_ops`; the HTTP application uses
  `sfc_app`.

### Web

- Auth gate and role guard; signed-out visitors land on `/login` with the
  attempted path remembered.
- Role navigation, full mobile menu, and role-specific dashboards using live
  values only.
- Donor: donation list/create/detail, impact, freshness, activity.
- Manager: donation review and transitions, route assignment, inspection
  queue, allocation, delivery progress/review, spoilage, branches, routes and
  assignments, people, reports, freshness, activity.
- Driver: today, deliveries, start/deliver/fail, routes, history, dependents,
  spoilage.
- Inspector: collected queue, selected donation, result recording, recent
  inspections, freshness, activity.
- Reports: branches/donors/drivers tabs, CSV export, and print views.
- Lazy route chunks reduce the initial production chunk; API envelope and
  pagination metadata are validated in one client.
- Oat/Forest/Terracotta visual system, Fraunces/Manrope, full product name,
  no fabricated counts or charts, 44px mobile targets.

### Database and secrets

- `smart_food_supply_chain` was not accessed.
- Development demo data lives in `smart_food_supply_chain_dev` via `sfc_app`.
- Automated tests use only `smart_food_supply_chain_api_test` via
  `sfc_api_test` and refuse any other database name.
- Secrets are read from protected files outside the repository. `.env` is
  ignored; `.env.example` contains placeholders only.
- Demo credentials provisioned locally for headless verification were not
  committed; only hashes exist in the development database.

## 4. Contract and security checks

- Success envelope `{"data": …, "meta": {}}`; error envelope
  `{"error": {"code", "message", "details"?}, "request_id"}`; every response
  carries `X-Request-ID`; JSON is UTF-8.
- Password hashing: Werkzeug `scrypt:32768:8:1`; 12–128 characters; common
  password, email, and name checks; timing-safe unknown-user handling.
- Session cookie: signed HttpOnly, `SameSite=Lax`, 8-hour idle/12-hour
  absolute limits; `__Host-` names when `Secure` is enabled.
- CSRF: session-bound double-submit token plus allowed `Origin`/`Referer` for
  mutating requests.
- Lockout: 5 failures in 15 minutes locks for 15 minutes; login attempts are
  rate-limited per IP/email.
- Activation/reset tokens are opaque, SHA-256 hashed at rest, single use, and
  shown once.
- Every request reloads current role, branch, and account status so a
  suspended or moved user loses access immediately.
- Append-only inspection/history tables protected by database triggers; UI
  presents them as immutable.
- Log redaction covers configured secrets, database URLs, passwords, and
  common credential patterns.

## 5. Known limits (documented, not hidden)

| ID | Limit | Handling |
| --- | --- | --- |
| G12 | Frozen schema has no delivery-status history table | Delivery current status and timestamps are displayed; the UI explicitly labels this limit |
| G13 | No donation close-out table | `COMPLETED` is derived from delivered + spoiled quantities |
| G15 | Allocation capacity is checked against current available quantity, not a status-aware reservation ledger | Database/service cap is enforced; no invented reservation table |

Additional deliberate choices:

- No fabricated charts. The UI uses numeric summaries and tables from live API
  values.
- No monogram or shortened product name.
- No push and no remote configuration were performed.

## 6. Reproduction

```powershell
# Backend
cd apps/api
python -m pytest -q
python -m ruff check src tests
python -m black --check src tests
python -m mypy
python -m flask --app sfc_api run --host 127.0.0.1 --port 5000

# Frontend
cd ../web
npm ci
npm test
npm run typecheck
npm run lint
npm run build
npm run dev -- --host 127.0.0.1 --port 5173
```

The database-backed tests require the protected test password file and the
`smart_food_supply_chain_api_test` database. Without them the integration
tests skip rather than touching another database.

## 7. Final status

**PASS** for the Step 7 application scope.  
**DEFERRED (documented)** for schema gaps G12, G13, and G15, which cannot be
closed without changing the frozen schema.  
**NOT DONE BY DESIGN** — remote push, production deployment, and credential
rotation outside the repository.
