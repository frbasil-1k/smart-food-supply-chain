# UI DESIGN SYSTEM

Binding for every screen. The product is a logistics and food-operations console:
dense, calm, editorial. It is **not** a SaaS dashboard template.

Product name, always spelled in full: **Smart Food Supply Chain & Surplus
Redistribution System**. No abbreviated monogram; the brand mark is an abstract,
letter-free glyph (a bowl arc intersecting a leaf vein), used alone or beside the
full name.

---

## 1. Colour

Exactly three chromatic brand colours. Neutrals are permitted; **no fourth hue**
and no gradients between hues.

| Token | Hex | Role |
|---|---|---|
| `--oat` | `#F4F0E6` | 60% — page background, panels, table body, inputs |
| `--forest` | `#21483B` | 30% — navigation rail, table headers, section bands, primary CTA fill, footer |
| `--terracotta` | `#D9844B` | 10% — **decorative accent only**: 3px active-route bar, key metric underline, chart accent, marker dot, icon ≥ 24px. Never text on Oat (2.51:1) |
| `--paper` | `#FFFFFF` | raised surfaces, print background |
| `--charcoal` | `#1C1B18` | primary text |
| `--ink-soft` | `#5F5C53` | secondary text, labels |
| `--line` | `#D9D3C4` | 1px borders, table rules |
| `--line-strong` | `#B9B2A0` | input borders, dividers on Oat |
| `--oat-deep` | `#EAE4D5` | hover on Oat, table zebra, disabled fill |

Derived tints are made with `color-mix(in srgb, …)` against Oat or Forest — never
by introducing a new hue.

### 60-30-10 in practice

| Share | Where it lands |
|---|---|
| **60 Oat** | page canvas, content panels, form fields, table bodies, empty states |
| **30 Forest** | the left rail (full height), the 56px top bar for manager/inspector shells, table header rows, section header bands, the primary CTA, footer, print header rule |
| **10 Terracotta** | 3px active-route bar, focus rings, the single highlighted metric per panel, status pips (`NEEDS_REVIEW`, due-today), chart accent series, link underline on hover |

### Measured contrast (do not restate these from memory)

| Pair | Ratio | Verdict |
|---|---|---|
| Charcoal `#1C1B18` on Oat | **15.1 : 1** | body text, any size |
| Forest `#21483B` on Oat | **8.98 : 1** | body/small text, links, status labels |
| Oat on Forest | **8.98 : 1** | rail, Forest header bands, primary CTA text |
| `--ink-soft` `#5F5C53` on Oat | **5.87 : 1** | ≥ 13px secondary text (AA) |
| Forest on terracotta 14% Oat tint | **7.97 : 1** | status pill text |
| **Terracotta `#D9844B` on Oat** | **2.51 : 1** | ✗ **never text** |
| **Terracotta on its 14% Oat tint** | **2.23 : 1** | ✗ **never text** |
| Terracotta on Forest | 3.58 : 1 | ✗ text; ✓ 3px rules, markers, ≥ 24px decorative icons |
| Forest on Oat, as a focus ring | 8.98 : 1 against the surface it sits on | ✓ the default ring |

So the rule is concrete, not stylistic: **Terracotta is a 10% decorative
accent.** It may be a rule, an underline, a marker, a chart series or a large
non-essential icon. It may not be a label, a value, a status word, a border that
communicates an error on its own, or any text on Oat — at 2.51:1 (2.23:1 on the
tint) nobody should be asked to read it. Everything textual uses Charcoal, Forest
or `--ink-soft`.

| Was | Now |
|---|---|
| Terracotta focus ring on Oat | **Forest** 2px ring, 2px offset, on Oat/paper surfaces (8.98:1) |
| Terracotta focus ring on Forest | **Oat** 2px ring (8.98:1) |
| Terracotta status text on a tinted pill | **Forest** text on the terracotta 14% tint, plus a Terracotta 3px left rule and a glyph |
| Terracotta validation text | **Charcoal** text + Terracotta 3px left rule + icon (`role="alert"`) |

### Semantic status colours (within the palette)

| Meaning | Treatment |
|---|---|
| Success / `PASSED` / `DELIVERED` / `ACTIVE` | Forest text on `color-mix(forest 12%, oat)`, 1px Forest-tint border |
| Attention / `NEEDS_REVIEW` / due soon / `PARTIALLY_DISTRIBUTED` | **Forest** text on `color-mix(terracotta 14%, oat)`, 1px terracotta-tint border, **plus** a 3px terracotta left rule and a glyph (▲ / clock). The colour carries no meaning on its own |
| Failure / `FAILED` / `REJECTED` / `SUSPENDED` | Charcoal text on `color-mix(charcoal 10%, oat)` with a 3px Terracotta left rule |
| Neutral / `PENDING` / `PLANNED` / `INACTIVE` | `--ink-soft` on `--oat-deep` |

Red and green are deliberately absent; severity is carried by weight, rule, glyph
and the label word — which keeps the palette to three hues and stays legible for
colour-blind users and in greyscale. A `StatusPill` must always render its text;
an icon-only pill is not permitted, and no two statuses differ only by tint.

Borders and controls follow the same measured rule: a 1px `--line-strong` border
(3.2:1 on Oat) never carries a state alone — it is paired with text, a glyph or a
3px rule; focus is Forest, not Terracotta, because a focus indicator must be
visible at 3:1 minimum and Terracotta is below that on Oat.

---

## 2. Typography

| Family | Use | Weights |
|---|---|---|
| **Fraunces** (variable, `opsz`) | page titles, panel titles, editorial numbers, print headings | 400, 500, 600 |
| **Manrope** | everything else: body, labels, tables, controls, captions | 400, 500, 600, 700 |

| Style | Size / line | Family | Notes |
|---|---|---|---|
| Display | 40 / 44 | Fraunces 500 | role dashboard greeting only |
| H1 | 30 / 36 | Fraunces 500 | one per page |
| H2 | 22 / 28 | Fraunces 500 | panel titles |
| H3 | 17 / 24 | Manrope 600 | sub-sections, drawer titles |
| Body | 15 / 23 | Manrope 400 | default |
| Body strong | 15 / 23 | Manrope 600 | labels in tables |
| Small | 13 / 19 | Manrope 400/500 | metadata, helper text |
| Micro | 11 / 16 | Manrope 600 | table column headers, uppercase, `letter-spacing: .04em` |
| Metric | 28 / 32 | Fraunces 500, `tabular-nums` | KPI values |
| Table cell | 14 / 20 | Manrope 400, `tabular-nums` | numbers right-aligned |

All numeric cells and metrics use `font-variant-numeric: tabular-nums` so kg
columns align. Units (`kg`, `°C`) are rendered in `Small` at 60% opacity, never
inside the number.

---

## 3. Space, shape, elevation

- Base unit **4px**; scale `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`.
- Page gutters: 24px desktop, 16px tablet, 12px mobile.
- Content max-width 1440px; tables may run full width.
- Radii: `4px` controls, `8px` panels, `12px` sheets/drawers, `2px` tags.
- Borders carry structure: 1px `--line` between sections, `--line-strong` on inputs.
- **Elevation:** one shadow only, for overlays (`0 8px 24px rgb(28 27 24 / .12)`).
  Panels and cards never cast shadows; they are separated by rules and Oat contrast.
- No glassmorphism, no blur, no translucency on data surfaces.

---

## 4. Layout and navigation

```
┌────────────┬──────────────────────────────────────────────┐
│  Forest    │  top bar 56px: breadcrumb · search · role    │
│  rail      ├──────────────────────────────────────────────┤
│  240px     │  content (Oat)                                │
│            │   H1 + page actions (right)                   │
│  full      │   panels · tables · charts                    │
│  height    │                                              │
└────────────┴──────────────────────────────────────────────┘
```

- **Rail (Forest):** brand mark + full product name (two lines, `Small`),
  role-specific sections, user block pinned at the bottom with role and branch.
  Active item: Oat text, 3px Terracotta left bar, `forest 85%` + Oat 15% fill.
- Rail collapses to 64px icon rail at `md`; below `md` it becomes a bottom bar
  (max 5 destinations) plus a “More” sheet.
- **Top bar:** breadcrumb (Fraunces 400, 15px), a global search that scopes to the
  current section, and a role/status chip.
- Page header pattern: H1 + one-line context (`Small`, `--ink-soft`) left; primary
  CTA + secondary actions right. No hero images, no oversized banners.

### Role shells

| Role | Rail destinations |
|---|---|
| DONOR | Overview · Donations · Impact · Activity |
| NGO_MANAGER | Overview · Donations · Inspections (read/coordinate) · Deliveries · Allocation · Branches · Routes · Reports |
| DRIVER | Today · Deliveries · Route · History |
| SAFETY_INSPECTOR | Queue · Inspections · Freshness · Activity |

---

## 5. Components

| Component | Specification |
|---|---|
| **Button** | primary: Forest fill, Oat text, 40px, radius 4, **Oat** 2px focus ring with 2px offset. secondary: transparent, 1px `--line-strong`, charcoal text, **Forest** focus ring. ghost: text only, Forest focus ring. danger: charcoal fill, Oat text, Terracotta 3px left rule. Disabled: `--oat-deep` fill, `--ink-soft` text, no shadow |
| **Input / Select / Textarea** | Oat fill, 1px `--line-strong`, 40px; focus: **Forest** 2px ring + Forest border; invalid: Terracotta 3px left rule **and** Charcoal message in `Small` **and** a glyph; helper text below, never placeholder-only labels |
| **Combobox** | searchable select for donor, route, branch, driver, category; shows code + name; keyboard-first |
| **Route Combobox (donor pickup)** | lists **only** `ACTIVE` `PICKUP`/`MIXED` routes whose `managing_branch_id` equals the signed-in donor's `app_user.primary_branch_id`; never the full route list, never another branch's routes, never a `DISTRIBUTION` route. When the donor has no `primary_branch_id` — or their branch has no selectable pickup route — the field is **absent** (not an empty select) and the pickup step states that routing happens after collection; no error is shown, because creating the donation unrouted is valid. The server re-validates the same rule — the SPA never sends a route the combobox did not offer (`API_CONTRACT.md` §3). |
| **DataTable** | Forest header row, Oat body, 1px rules, `Micro` uppercase headers, sortable headers with Lucide `ArrowUpDown`, 44px rows, sticky header, right-aligned numerics, row actions in a trailing overflow menu; server-side pagination with `Showing 1–25 of 412`; density toggle (comfortable 44px / compact 36px) |
| **StatusPill** | 22px, radius 2, `Micro` uppercase, palette per §1 status table; text always present, glyph for the attention/failure states, never colour-only |
| **Metric** | label (`Micro`), value (Metric style), delta or context (`Small`); one metric per panel may carry a 3px Terracotta underline |
| **Panel** | `--paper` on Oat with 1px `--line`, radius 8, 20px padding, optional Forest header band (H2 in Oat) |
| **Tabs** | Oat underline 2px, active Forest text + Terracotta 2px indicator; no pills |
| **Drawer / Modal** | right drawer 420px for filters and details; modal only for destructive confirms; focus trapped, Esc closes, overlay `rgb(28 27 24 / .4)` |
| **Stepper** (donation wizard) | 3 steps: pickup → items → review; Forest numbered chips, Terracotta current. The pickup step contains the branch-confined route combobox above; the review step shows the chosen route or the explicit sentence *“No route selected — this donation will be routed after collection.”* |
| **Timeline** | vertical rule, Forest dots for genuine events, hollow dot + the exact sentence *"State observed when history tracking began; earlier transitions were not recorded."* for reconstructed rows; no timestamp is shown for those |
| **Toast** | bottom-right, Oat surface, 3px Forest left rule, `Small` text, auto-dismiss 6s, `role="status"` |
| **EmptyState** | glyph, one-sentence explanation, one action. Never sample data |
| **Skeleton** | Oat-deep blocks with a 1.2s shimmer; used instead of spinners in tables |
| **ConfirmDialog** | states the object and the consequence; destructive confirm requires typing nothing but shows the exact status change |

---

## 6. Charts (Recharts) — four only

1. **Donation pipeline** — horizontal bars by status, Forest base, current status
   in Terracotta.
2. **Delivered vs spoiled per week** — stacked bars, Forest + `charcoal 25%`,
   Terracotta axis highlight on the current week.
3. **Donor impact** — horizontal bar of `delivered_kg` for the top 8 donors,
   Forest with a Terracotta marker for `undistributed_balance_kg`.
4. **Freshness strip** — items bucketed `expired · <24h · <72h · ok`, a single-row
   segmented bar in terracotta/oat/forest tints.

Every chart: no 3D, no gradients, no pie charts, no rainbow series, ≤ 3 series,
legend as `Small` text, y-axis with units, accessible `aria-label` summary and a
table fallback behind a “Data” toggle.

---

## 7. Responsive behaviour

| Breakpoint | Behaviour |
|---|---|
| ≥ 1280 (`xl`) | rail 240 + full tables, two-column panels |
| 1024–1279 (`lg`) | rail 240, panels stack to one column, tables keep 8 columns |
| 768–1023 (`md`) | icon rail 64, tables drop low-priority columns, filters in a drawer |
| < 768 (`sm`) | bottom nav (5 items), cards replace tables in list views, filters full-screen sheet, actions in a sticky footer bar |

Mobile keeps the same data, not a reduced feature set: a driver marks a delivery
`DELIVERED` from a phone in one screen with one confirm.

---

## 8. Accessibility

- Contrast: measured pairs in §1. Charcoal/Oat 15.1:1, Forest/Oat 8.98:1,
  Oat/Forest 8.98:1, ink-soft/Oat 5.87:1, Forest on the terracotta tint 7.97:1.
  Terracotta is decorative only — 2.51:1 on Oat, 2.23:1 on its tint — and is never
  used for text. Every interactive state has a non-colour cue (icon, underline,
  weight, rule).
- Focus: **Forest** 2px ring with 2px offset on Oat/paper, **Oat** 2px ring on
  Forest; never removed, `:focus-visible` only. The ring is verified against the
  actual adjacent surface, not assumed.
- Landmarks: `header`, `nav`, `main`, `aside`; a skip link to `#main`.
- Tables: real `<table>` with `<th scope>`, `aria-sort`, caption; row menus are
  reachable by keyboard.
- Forms: label for every field, `aria-describedby` for helper and error text,
  errors announced with `role="alert"`, no error conveyed by colour alone.
- Charts: text summary + data table fallback; no information only in colour.
- Motion: respect `prefers-reduced-motion`; transitions ≤ 150ms, opacity/translate
  only.
- Touch targets ≥ 44px on mobile.

---

## 9. Print

Reports print on `--paper`, Forest 1.5px rule under the full product name, no rail,
no buttons, page numbers, table headers repeated per page, and the filter set
printed above the table so a printed page is self-describing. Print CSS lives with
the report route (`/print/reports/...`).
