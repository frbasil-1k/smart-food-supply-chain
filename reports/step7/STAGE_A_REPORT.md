# Step 7 — Stage A report

**Status:** complete. Stage A was not staged and not committed.

**Branch:** `feature/step-7-application`  
**HEAD:** `1fe25282ec2dd3a83ed2a988c08a3837319a62e9` (unchanged)  
**Parent:** `9bd139650654b5cba84a2a527757003824995d7f`  
**Environment:** Windows, Python 3.13.5, Node 24.20.0, npm 11.19.0

Stage A establishes the monorepo application foundation and development
environment only. It does not implement database access, authentication,
role-specific dashboards, or operational data screens.

## 1. Delivered scope

| Area | Delivered |
| --- | --- |
| Monorepo | `apps/api` (Flask) and `apps/web` (React); `database/`, `docs/`, and existing report material were not changed |
| Backend | Application factory, environment config, blueprint registration, Pydantic validation helper, contract error envelopes, structured/redacting logs, request correlation, liveness endpoint, pytest suite |
| Frontend | Responsive shell, React Router routes, TanStack Query provider, brand-token system, Fraunces/Manrope typography, live API status, empty states, Vitest/Testing Library suite |
| Tooling | Isolated Python virtual environment, pinned Python resolution, npm lockfile, updated root `.gitignore`, root and web setup documentation |
| Safety | No MySQL connection, query, DDL, migration, seed data, auth implementation, SQLAlchemy model, or credential |

## 2. Git and workspace state

Verified before and after the work:

- Branch: `feature/step-7-application`
- HEAD: `1fe25282ec2dd3a83ed2a988c08a3837319a62e9`
- Parent: `9bd139650654b5cba84a2a527757003824995d7f`
- `git diff --cached --stat`: empty (nothing staged)
- No commit was created
- `docs/`, `database/`, and existing `reports/` content: no changes (this new
  report is the only addition under `reports/`)
- Existing untracked ZIP archives were left untouched
- Existing `apps/web` shadcn/ui scaffold was reused rather than regenerated
- Root `.gitignore` was extended with `.env`, cache, coverage, test-report, and
  `*.egg-info/` rules

Final `git status --short`:

```text
 M .gitignore
?? README.md
?? apps/
?? architecture-review-approved.zip
?? architecture-review-final.zip
?? architecture-review.zip
?? reports/step7/
?? step7-architecture-final.zip
?? step7-lock-final.zip
```

The ZIPs predate this stage and were not created, extracted, staged, or deleted
by it.

## 3. Structure

```text
apps/
├── api/
│   ├── .env.example
│   ├── pyproject.toml
│   ├── requirements.lock
│   ├── src/sfc_api/
│   │   ├── __init__.py              create_app factory
│   │   ├── config.py                env-driven Settings
│   │   ├── responses.py             success envelope
│   │   ├── errors.py                ApiError + error handlers
│   │   ├── validation.py            StrictModel + parse_json
│   │   ├── logging_config.py        JSON logs, redaction, request id
│   │   ├── time_utils.py            Asia/Kolkata timestamps
│   │   ├── version.py
│   │   └── api/
│   │       ├── __init__.py          blueprint registration
│   │       └── health.py            GET /api/health
│   └── tests/                       seven pytest modules
└── web/
    ├── index.html
    ├── package.json / package-lock.json
    ├── vite.config.ts
    ├── components.json
    ├── README.md
    └── src/
        ├── App.tsx / main.tsx
        ├── app/                     providers + router
        ├── components/              brand, panel, status pill, layout, ui
        ├── features/                overview + system screens
        ├── lib/                     API client, brand, datetime
        ├── pages/NotFoundPage.tsx
        ├── styles/tokens.css
        ├── index.css
        ├── test/                    setup + render helper
        └── *.test.ts(x)             shell, API, and token tests
```

66 non-ignored files are present under `apps/`; generated `.venv`, `node_modules`,
`dist`, caches, and egg metadata are ignored and not part of the deliverable.

## 4. Backend implementation

### Factory and configuration

`create_app(settings: Settings | None = None)` in
`apps/api/src/sfc_api/__init__.py`:

- Builds the Flask app without creating an engine or opening a connection.
- Reads settings from `SFC_ENV`, `SECRET_KEY`, `APP_TIMEZONE`, `LOG_LEVEL`, and
  an optional `DATABASE_URL`.
- Requires a 32+ character secret outside tests; tests receive a randomly
  generated ephemeral secret when none is supplied.
- Validates the IANA timezone and accepts only a MySQL SQLAlchemy URL shape.
- Sets `PROPAGATE_EXCEPTIONS = False` so the error contract holds in tests and
  production.
- Registers logging, error handlers, request hooks, and blueprints.

`python-dotenv` is installed so the Flask CLI can load a local `.env`; no
`.env` is committed or generated in this deliverable.

### Request/response behaviour

- Success: `{"data": ..., "meta": ...}` with
  `application/json; charset=utf-8`.
- Errors: `{"error": {"code", "message", "details"?}, "request_id"}`.
- Every request gets an `X-Request-ID` response header; error bodies echo it.
- 404, 405, 422 validation, and unexpected 500 responses are covered by tests.
- 500 responses never expose a traceback or exception message to the client.
- API timestamps are timezone-aware and use `APP_TIMEZONE`; the health endpoint
  returns an offset-bearing `+05:30` value, not `Z` or a naive `utcnow()`.
- `parse_json(model, data)` uses Pydantic v2 `extra="forbid"` and converts
  validation failures into the 422 contract details. It is the boundary helper
  future blueprints will use.

### Logging

- One JSON object per log line with timestamp, level, logger, message,
  request id, and allow-listed request fields.
- Access logs contain method, path, status, and duration; query strings,
  bodies, headers, cookies, and credentials are not logged.
- A formatter redacts configured secret values, the database URL, and common
  credential patterns before serialization.
- Tests capture formatted output and confirm that a configured secret and a
  `password=` value never appear in logs.

### Health endpoint

`GET /api/health` returns:

```json
{
  "data": {
    "status": "ok",
    "service": "sfc-api",
    "version": "0.1.0",
    "environment": "development",
    "timezone": "Asia/Kolkata",
    "time": "2026-11-17T00:00:00+05:30"
  },
  "meta": {}
}
```

It performs no database check. A test configures an unreachable MySQL URL and
still receives HTTP 200, proving Stage A liveness has no database dependency.

### Tests

23 backend tests across config, factory, errors, health, logging, and
validation. They use Flask's test client and do not require MySQL.

## 5. Frontend implementation

### Routes and shell

- `/` — Overview: editorial introduction, live API status, operational
  invariants, and a truthful “No operational data yet” empty state.
- `/system` — System status: live liveness values, request ID, data-boundary
  notes, and an explicit refresh action.
- `*` — real not-found screen with a return link.

The shell uses:

- A 240px Forest rail at wide widths, collapsing to 64px icon-only navigation
  at `md`, and hiding in favour of a fixed Forest bottom navigation on small
  screens.
- A 56px Forest top bar on desktop; a compact Forest mobile header showing the
  full product name.
- Full product name everywhere identity is shown; the brand mark is the
  abstract bowl-arc/leaf-vein glyph, not a monogram.
- Oat (`#F4F0E6`) as the dominant surface, Forest (`#21483B`) for structure and
  the primary CTA, and Terracotta (`#D9844B`) for active-route rules, panel
  accents, focus treatment, and the decorative vein only. Terracotta is never
  used for body text.
- Fraunces headings and Manrope body copy, loaded locally through
  `@fontsource-variable`.
- A skip link, one `main` landmark, labelled primary navigation, `aria-current`
  on active routes, visible focus rings, reduced-motion handling, and no
  horizontal overflow at the tested widths.

### Data handling

`src/lib/api.ts` fetches `/api/health`, validates the payload with Zod, reads
`X-Request-ID`, and raises a typed `ApiRequestError` for API error envelopes or
invalid success payloads. TanStack Query owns loading/error state; the Retry
and Refresh buttons call a real refetch. There are no fabricated counts,
charts, users, or operational records.

### Frontend tests

11 Vitest/Testing Library tests:

- shell render, exact product name, exact document title, landmarks
- real route navigation and `aria-current`
- API failure → retry → recovery
- responsive class contract, skip link, heading order, accessible link names
- not-found route
- exact brand palette and Tailwind token/typography mapping
- typed health success, API error envelope, invalid payload rejection

## 6. Dependencies

### Python

Installed in `apps/api/.venv` (ignored). `pyproject.toml` holds ranges;
`requirements.lock` is the `pip freeze --exclude-editable` resolution from this
environment.

| Package | Resolved |
| --- | --- |
| Python | 3.13.5 |
| Flask | 3.1.3 |
| Pydantic | 2.14.3 |
| SQLAlchemy | 2.0.57 (installed for the next stage; no engine or models created) |
| PyMySQL | 1.1.3 (installed for the next stage; never connected) |
| python-dotenv | 1.2.4 |
| tzdata | 2026.6 (Windows IANA timezone data) |
| cryptography | 50.0.2 |
| pytest | 8.4.2 |
| ruff | 0.17.5 |
| black | 26.10.1 |
| mypy | 2.4.1 |

`SQLAlchemy` and `PyMySQL` are pinned within their approved major/minor lines
(`>=2.0,<2.1` and `>=1.1,<1.2`). They are not imported by application code.

### Node

`package-lock.json` is part of the untracked deliverable.

| Package | Resolved |
| --- | --- |
| React / React DOM | 19.3.1 |
| Vite | 8.3.8 |
| TypeScript | 7.0.2 |
| Tailwind CSS / `@tailwindcss/vite` | 4.3.5 |
| shadcn CLI | 4.23.0 (dev-only) |
| Base UI | 1.9.0 |
| React Router DOM | 7.18.5 |
| TanStack Query | 5.107.1 |
| React Hook Form | 7.92.0 |
| Zod | 4.6.7 |
| Recharts | 3.10.1 |
| Lucide React | 1.73.0 |
| Vitest | 5.1.0 |
| React Testing Library | 16.3.3 |
| jest-dom | 7.0.1 |
| jsdom | 31.0.1 |
| oxlint | 1.94.0 |

Vitest 5 is used because the existing Vite 8 scaffold is outside Vitest 3's
supported Vite range. It is the same approved tool, kept compatible with the
installed Vite. `shadcn` and `tailwindcss` were moved to `devDependencies`
because neither is imported by the runtime bundle.

`npm audit --omit=dev` reports **0 production vulnerabilities**. The full audit
still reports 6 low/moderate findings in the shadcn CLI's transitive tooling;
no forced audit fix was applied.

## 7. Configuration and secrets

- `.env.example` contains names and placeholders only.
- `.env` is ignored and was not created in the repository.
- No real credential, API key, default password, or admin account exists in
  the new application files.
- `DATABASE_URL` is optional and unused in Stage A.
- Logs redact configured secrets and common credential patterns.
- Tests do not depend on a committed secret or on MySQL.

## 8. Verification (actually run)

### Backend

From `apps/api`:

```text
python -m pytest -q
23 passed in 0.20s

ruff check .
All checks passed!

black --check .
17 files would be left unchanged.

mypy
Success: no issues found in 10 source files
```

### Frontend

From `apps/web`:

```text
npm test
Test Files  3 passed (3)
Tests       11 passed (11)

npm run typecheck
tsc -b                         # passed

npm run build
dist/assets/index-XwwzG_w9.css   57.63 kB │ gzip: 13.43 kB
dist/assets/index-CvSGCkOq.js   429.89 kB │ gzip: 134.31 kB
✓ built

npm run lint
2 warnings in generated shadcn primitives (button.tsx, badge.tsx):
react(only-export-components). No errors.
```

`npm ci --dry-run` succeeds against the lockfile.

### Browser verification

Automated headless verification used Playwright Core 1.65.1 with installed
Microsoft Edge 157.0.4341.60 (Chromium channel), since this session's Playwright
MCP server could not launch its configured Chrome channel. The MCP config was
updated to `--browser msedge` for future sessions; the already-running MCP
process did not reload it.

Verified:

- Exact document title and full product name visible.
- `GET /api/health` returned 200 through the Vite proxy and the UI reached
  “API online”.
- Route navigation to `/system` and active `aria-current` states.
- No horizontal overflow at 1280×800, 768×900, 390×844, or 320×700.
- Body background `rgb(244, 240, 230)` (Oat), rail `rgb(33, 72, 59)` (Forest),
  active rule `rgb(217, 132, 75)` (Terracotta), 240px rail, 56px top bar.
- Fraunces resolves for the H1 and Manrope for body copy.
- Zero console errors, console warnings, page errors, or 4xx/5xx responses.
  React StrictMode's development double-mount aborted one duplicate health
  request; the retained request completed with 200.
- axe-core WCAG 2 A/AA checks at 390px returned **0 violations** for both the
  Overview and System screens.

Screens were visually reviewed at desktop, tablet, and mobile widths. The
interface uses the real live service state and explicit empty states only.

## 9. Intentionally absent

- MySQL connections, queries, DDL, migrations, seed data, `sfc_app`/`sfc_ops`
  users, and SQLAlchemy models
- Authentication, sessions, CSRF, login, password reset, and provisioning CLI
- Role dashboards and donation/delivery/review/inventory workflows
- Charts and operational tables (dependencies installed; no fabricated data)
- Playwright project configuration (the architecture defers browser tests)
- Production WSGI deployment configuration

## 10. Run locally

```powershell
# Terminal 1 — API
cd apps/api
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# replace SECRET_KEY with 32+ random characters
python -m flask --app sfc_api run --host 127.0.0.1 --port 5000

# Terminal 2 — web
cd apps/web
npm ci
npm run dev
```

See `README.md` for the full command reference and database boundary.

## 11. Final file list

```text
README.md                                   (new)
.gitignore                                  (modified: 18 added lines)
reports/step7/STAGE_A_REPORT.md             (new)

apps/api/.env.example
apps/api/pyproject.toml
apps/api/requirements.lock
apps/api/src/sfc_api/__init__.py
apps/api/src/sfc_api/api/__init__.py
apps/api/src/sfc_api/api/health.py
apps/api/src/sfc_api/config.py
apps/api/src/sfc_api/errors.py
apps/api/src/sfc_api/logging_config.py
apps/api/src/sfc_api/responses.py
apps/api/src/sfc_api/time_utils.py
apps/api/src/sfc_api/validation.py
apps/api/src/sfc_api/version.py
apps/api/tests/conftest.py
apps/api/tests/test_app_factory.py
apps/api/tests/test_config.py
apps/api/tests/test_errors.py
apps/api/tests/test_health.py
apps/api/tests/test_logging.py
apps/api/tests/test_validation.py

apps/web/.gitignore
apps/web/.oxlintrc.json
apps/web/README.md
apps/web/components.json
apps/web/index.html
apps/web/package.json
apps/web/package-lock.json
apps/web/tsconfig.json
apps/web/tsconfig.app.json
apps/web/tsconfig.node.json
apps/web/vite.config.ts
apps/web/src/App.tsx
apps/web/src/main.tsx
apps/web/src/index.css
apps/web/src/app.test.tsx
apps/web/src/app/providers.tsx
apps/web/src/app/router.tsx
apps/web/src/components/BrandMark.tsx
apps/web/src/components/Panel.tsx
apps/web/src/components/StatusPill.tsx
apps/web/src/components/layout/AppShell.tsx
apps/web/src/components/layout/BottomNav.tsx
apps/web/src/components/layout/RailNav.tsx
apps/web/src/components/layout/TopBar.tsx
apps/web/src/components/layout/navigation.ts
apps/web/src/components/ui/badge.tsx
apps/web/src/components/ui/button.tsx
apps/web/src/components/ui/card.tsx
apps/web/src/components/ui/dialog.tsx
apps/web/src/components/ui/dropdown-menu.tsx
apps/web/src/components/ui/input.tsx
apps/web/src/components/ui/label.tsx
apps/web/src/components/ui/sheet.tsx
apps/web/src/features/overview/OverviewPage.tsx
apps/web/src/features/system/SystemPage.tsx
apps/web/src/features/system/useHealth.ts
apps/web/src/lib/api.ts
apps/web/src/lib/api.test.ts
apps/web/src/lib/brand.ts
apps/web/src/lib/brand.test.ts
apps/web/src/lib/datetime.ts
apps/web/src/lib/utils.ts
apps/web/src/pages/NotFoundPage.tsx
apps/web/src/styles/tokens.css
apps/web/src/test/renderApp.tsx
apps/web/src/test/setup.ts
```

Stage A stops here. No Stage B work was started.
