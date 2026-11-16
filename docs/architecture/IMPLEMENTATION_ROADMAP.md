# IMPLEMENTATION ROADMAP

Ordered so that something real works end-to-end early: **Phase A–E produce the first
vertical slice** (login → role dashboard → create donation → manager approval, all
against `smart_food_supply_chain_dev`). Required/optional is marked per phase.

Estimates are relative sizes (`S` ≈ half a day, `M` ≈ 1–2 days, `L` ≈ 3+ days) for
one developer.

**Two databases, never confused.** `smart_food_supply_chain_dev` is the manual
development/demo target. `smart_food_supply_chain_api_test` is a disposable
database used **only** by automated tests, through a test-only account. The frozen
original `smart_food_supply_chain` is never contacted by the application or by
tests.

---

## A — Repository and application foundation  · required · S

| Step | Deliverable |
|---|---|
| A1 | `apps/api` skeleton: `pyproject.toml`, `src/sfc_api/__init__.py` (`create_app`), `config.py` reading `DATABASE_URL`/`SECRET_KEY`/`APP_TIMEZONE` from env, `.env.example` with names only |
| A2 | `apps/web` skeleton: Vite + React + TS, Tailwind v4 via `@tailwindcss/vite`, `tokens.css` from `UI_DESIGN_SYSTEM.md`, router shell, `/api` dev proxy |
| A3 | `.gitignore` additions: `apps/*/node_modules/`, `.venv/`, `.env`, `dist/`, `coverage/`, `playwright-report/` |
| A4 | `README.md` at root: how to run API + web, which database, which account, how to provision the test database |
| A5 | CI-less quality gates: `ruff`, `black --check`, `mypy` (api); `eslint`, `tsc --noEmit`, `prettier` (web) |

**Exit:** `npm run dev` serves a styled placeholder; `flask run` answers
`GET /api/health` with the DB version; both lint clean; nothing in `database/` or
`reports/` changed.

---

## B — Backend configuration and database integration · required · M

| Step | Deliverable |
|---|---|
| B1 | SQLAlchemy 2.0 models for the **17 business tables + 3 views only** (typed `Mapped[]`). `schema_migrations` is **not** modelled: the app has no privilege on it and the ledger belongs to the runner. No `create_all`, no Alembic; `echo=False`, pool sizing from env |
| B2 | `smart_food_supply_chain_dev` connection via `sfc_app` (created only after this design is approved; grants verified per `AUTH_SECURITY_DESIGN.md` §6.3) |
| B3 | Error mapping layer: the explicit SQLSTATE/message table of `API_CONTRACT.md` §1.1 (1644 → specific 409/422/403 code, 3819 → 422, 1452 → 422, 1062 → 409, unknown → 500 + `request_id`). No raw trigger text ever reaches a response |
| B4 | Envelope + pagination helpers, `sort` whitelist, `LIKE` escaping, `Decimal` serialiser, ISO-8601 `+05:30` datetime serialiser |
| B5 | Structured logging, request ids, `/api/health` |
| B6 | **Time**: one `now_local()` helper (`zoneinfo.ZoneInfo("Asia/Kolkata")`), `SET time_zone = '+05:30'` on every pooled connection, offset-bearing input parsing, and a startup assertion that `@@session.time_zone` is `+05:30`. No `utcnow()` anywhere |
| B7 | `conftest.py` pointing tests at **`smart_food_supply_chain_api_test`** only, restored from `database/schema_post_migrations.sql` by a test bootstrap, through a dedicated test account `sfc_api_test` whose privileges are limited to that database |
| B8 | Test-DB guard: an explicit **allowlist** (`{"smart_food_supply_chain_api_test"}`) checked against the resolved database name, plus a hard refusal if the name is `smart_food_supply_chain` or `smart_food_supply_chain_dev`. A suffix check is **not** sufficient |
| B9 | Privilege test: read `information_schema.TABLE_PRIVILEGES` **and** `information_schema.COLUMN_PRIVILEGES` for `sfc_app` and assert **exact set equality** with `AUTH_SECURITY_DESIGN.md` §6.2 — 36 table-level tuples (17 `SELECT` + 3 view `SELECT` + 13 `INSERT` + 3 `DELETE`, no `UPDATE`) and 35 column-level `UPDATE` tuples, 71 rows total; assert that no table-level `UPDATE` row exists; `SCHEMA_PRIVILEGES` empty; `USER_PRIVILEGES` = `USAGE` only |

**Exit:** a read-only endpoint (`GET /api/branches`) returns real rows through
models; a deliberately bad query returns a 500 with no SQL text; `SELECT` **and**
`INSERT` on `schema_migrations` as `sfc_app` fail with 1142; the privilege test
fails if a single grant is added or removed; a test started with
`SFC_TEST_DB_NAME=smart_food_supply_chain_dev` aborts before connecting.

---

## C — Authentication and activation · required · L

C1 scrypt v1 hashing/verification · C2 activation token issue (API + CLI): INSERT
when no credential row exists, UPDATE when it does, raw token returned once ·
C3 login with lockout and generic failures (locked = **401** `account_locked`) ·
C4 session cookie carrying **no role/branch** (`uid, sid, iat, seen, epoch,
csrf_id`), where `sid` is 16 random bytes minted per authentication session and
rotated on every login/activation (`AUTH_SECURITY_DESIGN.md` §2.1.1), the
per-request reload of `user_role`/`account_status`/`primary_branch_id`, the
credential-version comparison, and idle-8 h-inside-absolute-12 h with an immutable
`iat` · C5 CSRF: pre-auth token, **session-bound HMAC** token after login
(`HMAC("csrf|"+sid+"|"+csrf_id+"|"+uid)` recomputed from the verified session
payload), exact Origin check, rotation on login/activate ·
C6 `/auth/me`, logout, change password · C7 **manager-issued** password-reset token
+ public `password-reset/confirm` · C8 atomic redemption (`SELECT … FOR UPDATE` by
token hash, expiry inside the lock, password + token pair + version in one
`UPDATE`, commit before the session) · C9 role gate + scope predicate dependency
(both fed by the fresh row) · C10 pytest.

C10 must cover: activation happy path; expired, unknown and reused token; **two
threads redeeming one token → exactly one success and one 401**; lockout after 5;
locked login returns 401; CSRF rejection (missing header, wrong MAC, mismatched
Origin, **a token minted for the previous session rejected after re-login because
`sid` rotated**); revocation after password change; reset issuance scope (404
outside branch, 403 for another manager, 403 for self); a body containing a role or
branch field → 422; no hash/token leak in any auth response; and
**role-change-takes-effect-on-the-next-request**.

**Exit:** a real user activates, logs in, hits a protected endpoint, logs out; every
negative path above fails with the documented code; no response contains
`password_hash` or a token; the CSRF token issued before login is rejected after it.

---

## D — Role-based layouts and shared frontend system · required · M

D1 design tokens + Tailwind theme (Forest focus ring on Oat, Oat ring on Forest) ·
D2 rail/top-bar/bottom-nav shells per role · D3 `ProtectedRoute` + `/auth/me`
bootstrap · D4 API client with CSRF + error normalisation · D5 DataTable,
StatusPill (text always visible), Panel, Metric, EmptyState, Skeleton, Toast,
Drawer, ConfirmDialog · D6 Vitest + RTL setup, first component tests.

**Exit:** each of the four roles lands on its own shell with real `/auth/me` data;
keyboard-only navigation works with a visible focus ring on every surface;
table component renders 25 rows from a real paginated endpoint.

---

## E — Donation and food-item workflows · required · L

E1 donation list (scope + filters + server pagination) · E2 create donation wizard
(pickup → items → review, RHF + Zod; `pickup_route_id` optional and its combobox
confined to `ACTIVE` `PICKUP`/`MIXED` routes of the donor's own
`primary_branch_id`, absent when the donor has none) · E3 donation
detail with timeline · E4 status transition service + history writes in one
transaction · E5 item edit (quantity, re-parent) with 409 mapping · E6 pickup
validation (PIN/contact) · E7 **unrouted queue**: manager list of donations with
`pickup_route_id IS NULL` **whose donor's `primary_branch_id` is a branch they
manage** — no catch-all for donors without a branch — plus the read-only operator
queue `flask queue unrouted --orphans` (`sfc_ops` CLI, no HTTP endpoint, logged)
for those donations, and the `PATCH /api/donations/{id}/route` action restricted to
the manager's own routes · E8 tests: transition matrix, history append-only,
reconstructed-row wording, allocation guard boundaries, **driver-confirmed
collection** only for the route's designated driver, 404 for any other driver, a
manager getting 404 for an unrouted donation whose donor has no `primary_branch_id`
and 404 for one anchored to another branch, and the operator CLI queue returning
exactly the orphan rows; **route confinement**: donor of Branch A + route of Branch
A → 201, Branch A + route of Branch B → 422 `invalid_reference` with no row
written, donor without `primary_branch_id` + any route → 422 `validation_error`
(`donor_branch_required`), donor of Branch A + inactive/`DISTRIBUTION` route → 422
`invalid_reference`, and the SPA combobox never offers another branch's route.

**Exit — first vertical slice complete:** a donor creates a multi-item donation, a
manager moves it `PENDING → SCHEDULED`, assigns a route to an unrouted one, the
timeline shows both events, and the donor's dashboard reflects it. No fabricated
numbers anywhere.

---

## F — Inspection and freshness · required · M

F1 inspector queue using the **latest-inspection** predicate
(`COLLECTED` AND latest row is not `PASSED`, ordered by
`inspected_at DESC, inspection_id DESC` — never by timestamp alone), with a test
that the app predicate and the trigger ordering agree on a seeded mixed history ·
F2 inspection form (temperature plausibility wording, packaging, verdict; **no
date/time input**) · F3 manager coordination view (read-only queue) · F4 freshness
monitor from `donation_item.best_before` · F5 tests: −50/150 accepted,
−50.01/150.01 → 422, FAILED blocks delivery, a newer FAILED row re-enters the queue
after an older PASSED one, re-inspection with PASSED removes it, a body containing
`inspected_at` → 422 `validation_error`, a created `PASSED` row can never carry a
timestamp later than the server's own `NOW()`, and a deliberate **timestamp tie**
(two rows with equal `inspected_at`, ascending `inspection_id`) resolves to the
later insert in both the queue and the delivery gate — the test asserts server-set
timestamps and the `inspection_id DESC` tie-break, **not** `t2 > t1`.

**Exit:** inspector records a PASSED inspection; the manager can approve; a FAILED
inspection visibly blocks delivery creation with the trigger-backed message; no
request can influence `inspected_at`.

---

## G — Branch, allocation and inventory · required · L

G1 branch management (scope by `regional_manager_user_id`; creation forces the
caller as manager) · G2 route CRUD with driver eligibility (`designated_driver_user_id`
is required) · G3 route assignments (insert/delete; hours change by replacing) ·
G4 allocation workspace: lock item row, allocate across deliveries, live remaining
kg, allocation alone changes no donation status · G5 spoilage recording
(`{food_item_id, quantity_spoiled_kg, reason}` only — **no `reported_at` field**;
the value comes from the database clock in the INSERT and the stored value is
returned, so it cannot be backdated or future-dated; recomputes the donation) ·
G6 concurrency test (two managers, same item) asserting one 409 and no
over-allocation.

**Exit:** two parallel allocations of the last 10 kg produce exactly one success and
one `allocation_exceeds_available`; the item's available kg never goes negative;
recording spoilage moves the donation to `PARTIALLY_DISTRIBUTED` when a balance
remains.

---

## H — Route and delivery workflows · required · L

H1 delivery list + detail (current status only — no timeline) · H2 create delivery
plan (driver defaults to `route.designated_driver_user_id`; an override must be
that driver or an ACTIVE `DRIVER` assigned to the route) · H3 driver assignment
(pre-departure only) · H4 driver "Today" view · H5 status updates
`PLANNED → IN_TRANSIT → DELIVERED/FAILED` with **no note field** (nothing in the
schema could store it; gap G12); `FAILED` is terminal in Step 7 — no `FAILED →
CANCELLED` recovery until gap G15 · H6 delivery review by the receiving manager ·
H7 **donation reconciliation** in the delivery-completion transaction
(`PARTIALLY_DISTRIBUTED` / `COMPLETED` from quantities, `Decimal`, never from a
delivery count) · H8 tests: transit requires driver, DELIVERED requires PASSED
inspection, attribution immutable, second review → 409, a `note` on a delivery
status change → 422, a donation split across three deliveries completes only when
the last kilogram is reconciled, a `FAILED` delivery contributes zero to
`delivered_kg` and cannot complete the donation, a `PLANNED` cancellation deletes
only its own lines so the quantity can be reallocated, and cancellation appends no
`donation_status_history` row and creates no delivery event.

H9 **(deferred — G15, not a Step 7 exit criterion)** failed-delivery recovery:
after the cap is status-aware, `FAILED → CANCELLED` preserves the delivery and its
lines and releases their capacity; lost kilograms are recorded as spoilage and
stay deducted; recovered kilograms are reallocated; the same spoilage is counted
exactly once. Acceptance tests 2–4 in `API_CONTRACT.md` §5 are blocked until G15
lands and must be reported as blocked, not skipped silently.

**Exit:** a full chain donation → inspection → allocation → delivery → review runs
in the browser on real data; a multi-delivery donation ends `COMPLETED` only at
balance zero; `curl` attempts to violate each database rule return the documented
code.

---

## I — Reviews, donor impact and reporting · required · M

I1 dashboard endpoints per role (`/api/reports/overview`) · I2 donor impact for the
donor from `vw_donor_impact` filtered by their own `donor_id`, with the legacy
metric labelled · I3 **manager donor/driver/branch reports from base tables**
(`DATABASE_APPLICATION_MAPPING.md` §2.1), never a filtered global view: the donor
report aggregates over the **scoped-donation relation** (routed ∪ branch-anchored
unrouted) so visible unrouted donations contribute their donated and balance
kilograms; the branch report aggregates reviews from one row per reviewed delivery
so `avg_rating` is not weighted by `delivery_item` count · I4 driver's own
performance (route-designated
view row vs attributed kg, side by side) · I5 CSV export + print view for the four
reports · I6 Recharts panels (the four in the design system) · I7 tests: every
figure reconciles with a hand-written SQL total on a seeded dataset containing a
donor whose donations span **two** branches (the case a filtered view would get
wrong); the unrouted-report scenario (Manager A/Branch A, Donor A anchored to
Branch A with an unrouted donation — A sees queue + quantities, Manager B sees
neither, a donor with no `primary_branch_id` stays operator-only); and the
unweighted branch average (two deliveries rated 2 and 5 with 1 and 4 item lines →
`avg_rating = 3.50`, not 4.40); empty dataset renders empty states, not zeros
pretending to be data.

**Exit:** every dashboard figure traces to a query; a manager's donor total excludes
another branch's kilograms for the same donor; CSV and print match the screen; no
chart is fed a constant.

---

## J — Performance, security and comprehensive testing · required · L

J1 indexes only where `EXPLAIN` on a generated 10k–50k dataset proves a gain
(candidate gaps G10/G11) via a **separate load-test database** · J2 N+1 audit
(`SQLALCHEMY_WARN_20`, query counting in tests) · J3 pagination/keyset check on the
largest list · J4 permission matrix executed as an automated test per role ×
endpoint, asserting the role sets in `ROLE_PERMISSION_MATRIX.md` and
`API_CONTRACT.md` are identical, **and** the scope policy: a manager with zero
`regional_manager_user_id` branches gets empty lists, zero overview counts and 404
for detail (no `primary_branch_id` fallback), while a manager whose
`primary_branch_id` names a branch they do not manage still cannot read it ·
J5 CSRF/lockout/revocation/token-concurrency
regression suite + the 71-row privilege test (B9: 36 table-level + 35 column-level)
plus its column-denial cases · J6 Playwright: four role
journeys against the **API test database** · J7 accessibility pass (axe,
keyboard-only, **measured** contrast per `UI_DESIGN_SYSTEM.md` §1, no colour-only
status) · J8 documentation refresh (`README`, runbook, this design set) ·
J9 final review against `ROLE_PERMISSION_MATRIX.md` and `API_CONTRACT.md`.

**Exit:** p95 < 400 ms for every list endpoint at 50k donations on the dev machine;
axe reports no serious issues on the eight main screens; no text pair below 4.5:1;
the four Playwright journeys pass repeatedly; every endpoint has a denied-path test.

---

## Optional / deferred (explicitly not required for acceptance)

| Item | Why deferred |
|---|---|
| Notification centre with read/unread | needs a table (gap **G4**) |
| Driver correction workflow | gap **G5** |
| Inspection correction workflow | gap **G6** |
| Beneficiary/household distribution | gap **G7** |
| Map view of coverage areas | `coverage_area` has no geometry |
| Email/SMS delivery of tokens | no mail infrastructure; v1 shows the token once |
| Multi-device session management / per-device revocation | gap **G3** |
| Lockout escalation 15→30→60 | gap **G2** |
| Replacing the two `DEFINER=root` views | gap **G8** |
| Delivery status history | gap **G12** |
| Closing out undelivered surplus | gap **G13** — no written-off state exists |
| Integer credential version / `DATETIME(6)` | gap **G14** — v1 uses the monotonic `password_changed_at` write |

Each becomes a reviewed migration plus a small slice, in that order, if requested.

---

## Dependencies (hard)

```
A → B → C → D → E
            E → F → G → H → I → J
B ⇒ sfc_app created and grants verified (AUTH_SECURITY_DESIGN §6.3)
B ⇒ api_test database + test account exist before any test runs
C ⇒ activation token path exists before any dashboard is usable (all users lack credentials)
F ⇒ required before H can pass: DB blocks delivery without a PASSED inspection
G ⇒ required before H: a delivery needs an allocation to be meaningful
H ⇒ required before I: reports read delivered quantity
```

## Testing strategy per layer

| Layer | Tool | What it must prove |
|---|---|---|
| Service unit | pytest | transition matrix, quantity reconciliation (`Decimal`), scope predicates, lockout arithmetic, allocation maths |
| API integration | pytest + Flask test client against `smart_food_supply_chain_api_test` | status codes, envelopes, denied paths, SQLSTATE→code mapping, server-set timestamps |
| Contract | pytest + shared fixtures | every response validates against its Pydantic model; no credential field ever serialises; unknown fields rejected |
| Component | Vitest + RTL | table sorting/pagination wiring, form validation messages, empty/error states |
| E2E | Playwright | four role journeys, CSRF on a real browser, 409 surfaces as a readable message |
| Data safety | pytest guard | **allowlist** of test database names in `conftest.py`; hard refusal for `smart_food_supply_chain` and `smart_food_supply_chain_dev`; a name ending in `_test` is not enough on its own |
| Privileges | pytest | exact set equality from `information_schema` — 36 `TABLE_PRIVILEGES` rows plus 35 `COLUMN_PRIVILEGES` rows, no table-level `UPDATE` — and the 19 negative access tests + 5 positive controls |

`smart_food_supply_chain_phase2_test_dev` is **not** reused as the API test
database: it belongs to the migration runner's own test harness, and its identity,
owner and grants would have to be re-verified before any reuse — simpler and safer
to keep a separate `smart_food_supply_chain_api_test` with its own account.

## Definition of done for the whole application

1. All four roles complete their journey in a browser against
   `smart_food_supply_chain_dev`, with zero console errors.
2. Every mutation has a denied-path test; every database trigger has a test that
   proves the HTTP mapping, and no response contains raw trigger text.
3. `smart_food_supply_chain` is never contacted; `sfc_app` has exactly the **36
table-level + 35 column-level** privileges of `AUTH_SECURITY_DESIGN.md` §6.2, no
database-wide grant, no table-level `UPDATE`, and **cannot read or write
`schema_migrations`** (`SELECT` → 1142).
4. Automated tests never touch `smart_food_supply_chain_dev` or the original; the
   allowlist guard is exercised by a test that expects the refusal.
5. `inspected_at`/`reported_at`/`delivered_at` are server-set from the database
   clock, returned from the stored row; none is a request field, so none can be
   backdated or future-dated. Tied `inspected_at` values still resolve
   deterministically via `inspection_id DESC`.
6. A donation reaches `COMPLETED` only at balance zero, and no screen shows a
   delivery timeline that the schema cannot support.
7. Manager reports reconcile to branch-scoped SQL, not to a filtered global view.
8. No fabricated data on any screen; empty states everywhere data is absent.
9. Design system applied without a fourth hue, with the full product name intact
   and every text pair measured at ≥ 4.5:1.
10. `pytest`, `vitest`, `playwright`, `tsc --noEmit`, `ruff`, `mypy` all green.
