# Web app

React 19 + Vite + TypeScript + Tailwind CSS v4 role workspaces for the Smart
Food Supply Chain & Surplus Redistribution System.

## Commands

```bash
npm ci
npm run dev       # http://localhost:5173; proxies /api to 127.0.0.1:5000
npm test          # Vitest + Testing Library
npm run typecheck # tsc project build, no emit
npm run build     # type-check + production build
npm run preview   # serve the production build
npm run lint      # oxlint
```

Run the Flask API from `apps/api` in a second terminal.

## Structure

- `src/app` — providers, auth guards, lazy page map, router.
- `src/components/layout` — Forest rail, top bar, mobile header with full menu,
  bottom navigation, and role-aware navigation.
- `src/components/ui` — shadcn/ui primitives (Base UI `base-nova` style).
- `src/features/auth` — sign-in, activation, server-session provider.
- `src/features/overview` — role-specific landing dashboard.
- `src/features/donations` — list, create form, detail and transitions.
- `src/features/inspections` — queue, selected donation, result form.
- `src/features/deliveries` — list, allocation, progress/detail, review,
  spoilage.
- `src/features/reports` — donor impact, manager reports, freshness, activity,
  CSV and print views.
- `src/features/operations` — branches, routes/assignments, people, dependents,
  driver routes/history.
- `src/styles/tokens.css` — brand palette, semantic shadcn tokens, fonts.
- `src/lib/api.ts` — fetch client: envelope validation, CSRF, sessions,
  pagination metadata, typed API errors.

## Authentication and API calls

The browser never stores a token in `localStorage`. The server sets a signed
HttpOnly session cookie; the client fetches `/api/auth/csrf` and sends
`X-CSRF-Token` on mutating requests. `fetchMe()` treats a 401 as signed out.

All pages use React Query and keep server data in the query cache. The API
envelope is validated with Zod; failed requests surface the contract error
code and message in `ErrorNotice`.

`apiGetPaged()` preserves the `meta.pagination` object from paged endpoints;
`apiRequest()` treats a real `204 No Content` as a successful empty payload.

## Access rules in the UI

`RequireAuth` redirects signed-out visitors to `/login` with the attempted
path. `RequireRole` shows a clear “not available to your role” screen instead
of leaking another role's page. The server remains the authority: every
request is re-scoped from the current database role/branch, and out-of-scope
records return 404.

Roles:

- Donor: donations, new donation, impact, freshness, activity.
- NGO manager: donations, inspections, deliveries, allocation, spoilage,
  reports, branches, routes, people, freshness, activity.
- Driver: today, deliveries, spoilage, routes, history, dependents.
- Safety inspector: inspection queue, freshness, activity.

## Visual system

Oat `#F4F0E6`, Forest `#21483B`, Terracotta `#D9844B`; Fraunces headings,
Manrope body copy. Terracotta is decorative and is never used for body text
(2.51:1 on Oat). The UI keeps 60-30-10 balance, always prints the full product
name, and never fabricates counts or charts.

The interface is responsive: 240px fixed rail at `xl`, 64px icon rail at
`md`, bottom navigation plus a full mobile menu below `md`. Touch targets are
at least 44px. Focus rings are visible and `prefers-reduced-motion` is
respected by the token layer.

## Reports and print

Manager reports support tabs for branches, donors, and drivers, plus CSV
download. `/print/reports/branches|donors|drivers|freshness` renders the same
API payload on paper with the full product name, a Forest rule, repeated table
headers, and no shell navigation or buttons.
