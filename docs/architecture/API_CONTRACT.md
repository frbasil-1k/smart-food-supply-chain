# API CONTRACT

Base URL: `/api` · `application/json; charset=utf-8` (the only exception is an
explicit `?export=csv` report response) · cookies for auth (no bearer tokens).
All list endpoints are paginated and scoped. All quantities are **strings carrying
a Decimal** (e.g. `"12.50"`) so no float ever appears.

Every field below is checked against `database/schema_post_migrations.sql`. Where a
value is *derived* (a sum, a remaining balance, a joined label) it is marked
**derived**; nothing else is invented.

---

## 1. Envelope, pagination, errors

**Success**

```json
{ "data": { }, "meta": { } }
```

**List `meta`**

```json
{ "page": 1, "page_size": 25, "total": 412, "total_pages": 17,
  "has_next": true, "sort": "-pickup_datetime" }
```

Query parameters accepted by every list endpoint: `page` (≥1), `page_size`
(1–100, default 25), `sort` (field name, `-` prefix for descending, whitelisted per
endpoint), `q` (free text), plus endpoint-specific filters. Unknown parameters are
rejected with 422 rather than ignored.

**Error**

```json
{ "error": { "code": "invalid_transition", "message": "APPROVED requires a passed inspection.",
             "details": [ { "field": "status", "issue": "no_passed_inspection" } ] },
  "request_id": "b1f0c3d2" }
```

`message` is written by the application. A raw database trigger message, table
name, column list or SQL fragment is **never** returned.

| HTTP | `code` values |
|---|---|
| 400 | `malformed_request` |
| 401 | `unauthenticated`, `session_expired`, `invalid_credentials`, `account_locked`, `account_inactive`, `token_invalid_or_expired` |
| 403 | `forbidden_role`, `csrf_failed`, `reviewer_not_authorized` |
| 404 | `not_found` — **also used for every out-of-scope record**, so the API never confirms that another donor's, branch's or driver's record exists |
| 409 | `invalid_transition`, `duplicate_review`, `attribution_immutable`, `item_has_allocations`, `below_allocated`, `allocation_exceeds_available`, `duplicate_resource`, `inspection_required`, `driver_required`, `immutable_record`, `business_rule_violation` |
| 422 | `validation_error`, `password_policy`, `temperature_implausible`, `best_before_must_follow_prepared_at`, `driver_not_eligible`, `donor_role_invalid`, `manager_role_invalid`, `inspector_role_invalid`, `invalid_reference`, `item_wrong_donation` |
| 429 | `rate_limited` (+ `Retry-After`) |
| 500 | `internal_error` — never contains SQL, table names or stack traces; always carries `request_id` |

### 1.1 SQLSTATE → code mapping

MySQL errors are matched in the service layer against a fixed table and replaced
with the codes above. Unmatched `1644` becomes `409 business_rule_violation` with a
generic sentence; unmatched `1452`/`3819`/`1062` become the codes below.

| SQLSTATE | Recognised condition | Code | HTTP |
|---|---|---|---|
| 1644 | `Only users with DONOR role…` | `donor_role_invalid` | 422 |
| 1644 | `Only safety inspectors…` / `Inspector must have…` | `inspector_role_invalid` | 422 |
| 1644 | `Regional manager must have NGO_MANAGER role` | `manager_role_invalid` | 422 |
| 1644 | `Only the receiving branch manager…` / `Reviewer must be…` | `reviewer_not_authorized` | 403 |
| 1644 | `Delivery blocked: latest food inspection has not passed` | `inspection_required` | 409 |
| 1644 | `A delivery cannot enter IN_TRANSIT without an attributed driver` | `driver_required` | 409 |
| 1644 | `Delivery driver must have DRIVER role` / `Only users with DRIVER role` / `Designated driver must have DRIVER role` | `driver_not_eligible` | 422 |
| 1644 | `Driver attribution is immutable once the delivery is DELIVERED` | `attribution_immutable` | 409 |
| 1644 | `Food item does not belong to this delivery donation` | `item_wrong_donation` | 422 |
| 1644 | `Total allocated quantity exceeds available donated quantity` / `Spoiled quantity exceeds the available donated quantity` | `allocation_exceeds_available` | 409 |
| 1644 | `Cannot move a donation item to another donation…` | `item_has_allocations` | 409 |
| 1644 | `Reduced quantity is below the quantity already delivered plus spoiled` | `below_allocated` | 409 |
| 1644 | `donation_status_history is append-only…` | `immutable_record` | 409 |
| 3819 | any CHECK | `validation_error` | 422 |
| 1452 | any FK | `invalid_reference` | 422 |
| 1062 | `delivery_review.delivery_id` | `duplicate_review` | 409 |
| 1062 | any other unique key | `duplicate_resource` | 409 |

---

## 2. Authentication

| Method | Path | Roles | Request | Response |
|---|---|---|---|---|
| POST | `/api/auth/login` | public | `{email, password}` | 200 `{user}` + session cookie · 401 `invalid_credentials` (identical for unknown user, no credential row, or wrong password) · **401** `account_locked` with `retry_after_seconds` while `locked_until > NOW()` |
| POST | `/api/auth/logout` | any | — | 204 |
| GET | `/api/auth/me` | any | — | `{user_id, full_name, email, role, account_status, primary_branch_id, branch_name, must_change_password}` |
| GET | `/api/auth/csrf` | public | — | 200 `{csrf_token}` + sets the CSRF cookie (bound after login to the session's random `sid`, `csrf_id` and `uid`; `AUTH_SECURITY_DESIGN.md` §2.1.1–§2.3) |
| POST | `/api/auth/activate` | public | `{token, new_password}` | 200 (sets session) · 401 `token_invalid_or_expired` · 422 `password_policy` |
| POST | `/api/auth/password` | any | `{current_password, new_password}` | 204 · 422 `password_policy` |
| POST | `/api/auth/password-reset/confirm` | public | `{token, new_password}` | 204 · 401 `token_invalid_or_expired` · 422 `password_policy` |
| POST | `/api/users/{id}/activation-token` | NGO_MANAGER (scope) | — | 201 `{expires_at, activation_token, delivery:"shown_once"}` · 404 out of scope · 403 target not invitable by this role |
| POST | `/api/users/{id}/password-reset-token` | NGO_MANAGER (scope) | — | 201 `{expires_at, reset_token, delivery:"shown_once"}` · 404 out of scope · 403 target is another manager, self, or otherwise not resettable |

Login never answers **423**. The lock is a distinct *code* on a normal 401, so a
client cannot distinguish "locked" from "bad password" by status class alone and
proxies do not treat it as a WebDAV error.

`GET /api/auth/me` and every user-bearing response omit `password_hash`,
`reset_token_hash`, `reset_expires_at`, `failed_attempts` and `locked_until`.

**Token issuance responses (the only place a raw token ever appears)**

```json
{ "data": { "expires_at": "2026-11-17T16:20:00+05:30",
            "activation_token": "kS7…(43 chars)…qA",
            "delivery": "shown_once" } }
```

The `password-reset-token` endpoint returns the same shape with `reset_token`.
Rules for both: returned exactly once to the authorized manager (or to the
operator's CLI); never emailed or SMS'd in v1; never written to an application log,
access log, error trace, analytics event or metric label; never stored in plaintext
(the database holds only the SHA-256 hash); never present in `GET /api/users/{id}`,
`GET /api/auth/me`, any list response, any export, or any subsequent call. A lost
token is replaced by re-issuing, which overwrites `reset_token_hash` on the existing
credential row (never a second INSERT — `user_credential.user_id` is the primary key).

There is **no public "email me a reset link" endpoint**: v1 has no mail channel, so
such an endpoint could only enumerate accounts or create an unusable token.

Both redemption endpoints are atomic and single-use (§4 of the security doc): one
`SELECT … FOR UPDATE` by token hash, expiry check inside the lock, password +
token-pair cleared in one `UPDATE`, commit before the session is issued. A second
concurrent attempt returns the same `401 token_invalid_or_expired`.

---

## 3. Donations

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/api/donations` | all (scoped) | filters: `status`, `urgency`, `donor_id` (manager only), `route_id`, `branch_id`, `item_id`; `sort` ∈ `pickup_datetime`, `donation_status`, `donation_id`; `q` matches donor name / item name |
| POST | `/api/donations` | DONOR | creates donation **and** its items in one transaction; `pickup_route_id` is optional but, if supplied, must be an `ACTIVE` `PICKUP`/`MIXED` route of the donor's own `primary_branch_id` |
| GET | `/api/donations/{id}` | scoped | includes items, latest inspection, deliveries summary |
| PATCH | `/api/donations/{id}` | DONOR owner | `pickup_address`, `pickup_pincode`, `pickup_contact` only, while `PENDING`/`SCHEDULED`; `donor_user_id`, `pickup_datetime`, `urgency_level` and `donation_status` are **never** accepted here (status has `/status`) |
| PATCH | `/api/donations/{id}/route` | NGO_MANAGER | `{pickup_route_id}` — the unrouted-donation workflow (§3.2) |
| PATCH | `/api/donations/{id}/status` | DONOR (cancel), NGO_MANAGER, DRIVER (collect) | `{target_status, note?}` → transition matrix (§3.1) |
| GET | `/api/donations/{id}/history` | scoped | ascending by `changed_at`, `history_id` |
| GET | `/api/donations/{id}/items` | scoped | items with **derived** `allocated_kg`, `delivered_kg`, `spoiled_kg`, `available_kg` |
| POST | `/api/donations/{id}/items` | DONOR owner | one item per call, `PENDING` only |
| PATCH | `/api/donation-items/{id}` | DONOR owner, NGO_MANAGER | `quantity_kg`, `item_name`, `best_before`, `donation_id` (re-parent); `food_item_id`, `category_id` and `prepared_at` are never accepted |

**Create donation**

```json
{ "pickup_datetime": "2026-11-20T10:30:00+05:30",
  "pickup_route_id": 3,
  "pickup_address": "12 Market Road, Bengaluru",
  "pickup_pincode": "560001",
  "pickup_contact": "+919876543210",
  "urgency_level": "HIGH",
  "items": [
    { "category_id": 2, "item_name": "Cooked rice", "quantity_kg": "12.50",
      "prepared_at": "2026-11-20T08:00:00+05:30",
      "best_before": "2026-11-20T18:00:00+05:30" }
  ] }
```

Maps exactly to `donation` (`donor_user_id` from the session,
`donation_status` fixed to `PENDING`, never accepted from the client) and
`donation_item`. `pickup_address`, `pickup_pincode`, `pickup_contact` and
`pickup_route_id` are nullable in the schema; the API requires address/pincode/
contact at creation (a pickup without them is unusable) and accepts
`items` with ≥ 1 entry.

`pickup_route_id` **is optional at creation** (`donation.pickup_route_id` is
nullable), but it is **never a free choice of route**. A donor may only select a
route that belongs to their own branch, because a route decides which manager's
scope the donation enters:

1. `pickup_route_id` supplied → the donor's `app_user.primary_branch_id` must be
   **non-NULL**; if it is `NULL` the field is rejected (422 `validation_error`,
   `field: "pickup_route_id"`, `issue: "donor_branch_required"`) and the donation
   must be created unrouted.
2. The selected route's `route.managing_branch_id` must **equal** the donor's
   `primary_branch_id`. A route of any other branch is rejected with 422
   `invalid_reference` (`issue: "route_not_selectable"`) — the same answer as a
   route that does not exist, is `INACTIVE`, or is not
   `route_type IN ('PICKUP','MIXED')`, so the response never confirms that another
   branch's route exists.
3. `route_status = 'ACTIVE'` and `route_type IN ('PICKUP','MIXED')` (a
   `DISTRIBUTION` route is not a pickup route).

A donor therefore cannot place a donation into another manager's branch scope by
naming that manager's route; the only cross-branch assignment path is the
manager's `PATCH /api/donations/{id}/route` (§3.2), which is itself restricted to
routes the manager manages. The check is service-owned — the schema's FK only
proves the route exists — so it is implemented once in the donation-creation
service and asserted by tests (roadmap E8).

When omitted the donation enters the unrouted pool — the branch-scoped manager
queue when the donor has a `primary_branch_id`, otherwise the operator-authorised
queue only (§3.2) — and the inspector queue. A donor with no `primary_branch_id`
**must** omit `pickup_route_id`; supplying one is a 422, never a silent fallback.

Tests that must exist: donor with branch A + route of branch A → 201; donor with
branch A + route of branch B → 422 `invalid_reference` (and no row written); donor
with `primary_branch_id IS NULL` + any route → 422 `validation_error`
(`donor_branch_required`); donor
with branch A + route of branch A that is `INACTIVE` or `DISTRIBUTION` → 422
`invalid_reference`; donor with branch A and no route → 201 and the donation is in
branch A's manager queue.

Validation: `pickup_address` 5–255 chars; `pickup_pincode` `^[1-9][0-9]{5}$` after
stripping spaces; `pickup_contact` `+91[6-9][0-9]{9}`; `quantity_kg` > 0 with two
decimals and ≤ `999999.99` (`DECIMAL(8,2)`); `best_before > prepared_at` when
`prepared_at` is present (`chk_food_dates`); `item_name` 1–150; `category_id` must
exist.

### 3.1 Status transitions (service-owned; not in the schema)

```json
{ "target_status": "APPROVED", "note": "Inspected and cleared" }
```

→ 200 `{donation_id, from_status, to_status, changed_at, history_id}` ·
409 `invalid_transition` · 409 `inspection_required`.

| From | To | Actor | Condition |
|---|---|---|---|
| PENDING | SCHEDULED | NGO_MANAGER | a `pickup_route_id` is assigned |
| PENDING | REJECTED | NGO_MANAGER | `note` recommended |
| PENDING | CANCELLED | DONOR (owner) | no `delivery` row exists |
| SCHEDULED | COLLECTED | **DRIVER (designated on the pickup route)** or NGO_MANAGER | driver path requires `pickup_route_id IS NOT NULL` and `route.designated_driver_user_id = me`; otherwise the driver sees 404 |
| COLLECTED | APPROVED | NGO_MANAGER | latest inspection is `PASSED` |
| COLLECTED | REJECTED | NGO_MANAGER | latest inspection is `FAILED` |
| APPROVED | PARTIALLY_DISTRIBUTED | **system** | `delivered + spoiled > 0` **and** `balance > 0` |
| APPROVED / PARTIALLY_DISTRIBUTED | COMPLETED | **system** | `balance = 0` exactly |

`PARTIALLY_DISTRIBUTED` and `COMPLETED` are **derived states**. They cannot be
requested: a `target_status` of either is `422 validation_error` (`not_a_requestable_status`).
They are written by the same transaction that records a delivery reaching
`DELIVERED` or a spoilage row (§3.3), and each change appends exactly one
`donation_status_history` row with `changed_by_user_id` = the actor whose action
caused the recomputation.

A driver may call this endpoint only for `COLLECTED` on a donation on their
designated pickup route; every other target is 403 `forbidden_role`. This is the
same collection step the UI offers the driver, so no UI action is rejected by the
API.

`note` is stored in `donation_status_history.note` (≤ 255 chars) — that table is
append-only, so the note is a permanent audit line. It is **not** a delivery field.

### 3.2 Unrouted donations (branch-scoped manager queue, operator queue)

A donation with `pickup_route_id IS NULL` has no branch, so the normal manager
scope (branch → route → donation) cannot see it. Two documented paths exist, and
the donor's `app_user.primary_branch_id` separates them strictly.

**Manager queue — branch-scoped, read and write.**

- **Read:** a manager sees an unrouted donation **only** when the donor's
  `app_user.primary_branch_id` is a branch they manage
  (`branch.regional_manager_user_id = me`). The predicate is
  `pickup_route_id IS NULL AND donor.primary_branch_id ∈ managed_branch_ids`.
- **Write:** `PATCH /api/donations/{id}/route` assigns a route. Allowed only while
  the donation is `PENDING`/`SCHEDULED` and only to a route whose
  `managing_branch_id` is a branch the manager manages. 404 when the donation is
  out of read scope or the route belongs to another branch.
- After assignment the donation leaves the unrouted queue and enters that branch's
  normal scope permanently.
- **The donor cannot bypass this gate.** `POST /api/donations` accepts a
  `pickup_route_id` only when it belongs to the donor's own `primary_branch_id`
  (§3), so a donor can neither drop a donation into another manager's queue nor
  pre-route it into a branch they do not belong to. Being unrouted is the only
  state a donor can create; assigning the branch is the manager's action.

**No catch-all fallback.** A donor with `primary_branch_id IS NULL` has no branch
anchor, and a missing anchor is **not** permission to show the record to every
manager. Such a donation is invisible to *every* NGO_MANAGER: not in the unrouted
queue, not in `GET /api/donations`, not in `GET /api/donations/{id}` (404), not in
the `GET /api/reports/overview` counts and not in `/api/activity`. Only the donor's
own scope and the inspector queue (§4) still see it.

**Operator-authorised unrouted queue.** Until an authorised jurisdiction/branch
relationship exists for the donor, the only way these rows are surfaced is the
operator queue, which is a CLI action and not an application capability:

```text
flask queue unrouted --orphans          # run as sfc_ops; read-only
```

- Lists donations with `pickup_route_id IS NULL` **and** donor
  `primary_branch_id IS NULL`: `donation_id`, donor id/name, `pickup_datetime`,
  `donation_status`, item count and total kilograms. No contact details beyond the
  donor name. It is authorised by possession of the operator's `sfc_ops`
  credentials alone — there is no application role that can request it.
- There is **no HTTP equivalent**, deliberately: the schema has no administrator
  role (see `ROLE_PERMISSION_MATRIX.md` preamble), and inventing one to widen a
  donation read is exactly the fallback this section removes. `sfc_app` gains no
  privilege and no endpoint returns these rows.
- Each run appends one structured log line (`event: operator_unrouted_queue`, the
  OS user running the CLI, record count, invocation id). It writes nothing.
- **Resolution is operator provisioning, not a manager action.** The operator
  establishes the missing relationship by setting `app_user.primary_branch_id` for
  the donor to the branch with jurisdiction over that pickup (`sfc_ops` already
  holds `UPDATE app_user`; no new grant). The donation then appears in that
  branch's manager queue above and is routed through
  `PATCH /api/donations/{id}/route`, unchanged. A manager cannot self-authorise
  jurisdiction: no endpoint accepts another user's `primary_branch_id`, and
  branch creation is forced to the caller (§6).

The donor keeps ownership of the donation throughout; assignment changes
`pickup_route_id` and nothing else. Both manager predicates are implemented in the
repository layer, not in the SPA.

### 3.3 Distribution and completion (quantity-based, never allocation-based)

Quantities are computed per donation over `DELIVERED` deliveries only:

```
donated_kg   = SUM(donation_item.quantity_kg)                                   (Decimal(8,2))
delivered_kg = SUM(delivery_item.quantity_delivered_kg)
                 WHERE delivery.delivery_status = 'DELIVERED'
spoiled_kg   = SUM(spoilage_record.quantity_spoiled_kg) over the donation's items
balance_kg   = donated_kg - delivered_kg - spoiled_kg
planned_kg   = SUM(delivery_item.quantity_delivered_kg)
                 WHERE delivery.delivery_status IN ('PLANNED','IN_TRANSIT')
```

- A **planned allocation is not distribution.** Creating a delivery, adding lines or
  moving to `IN_TRANSIT` does not change `donation_status`.
- `PARTIALLY_DISTRIBUTED` requires `delivered_kg + spoiled_kg > 0` **and**
  `balance_kg > 0`.
- `COMPLETED` requires `balance_kg = 0` — every donated kilogram reconciled as
  delivered or spoiled. One successful delivery is never enough unless it consumed
  the whole donation.
- `FAILED` and `CANCELLED` deliveries contribute **zero** to `delivered_kg` and
  never satisfy `PARTIALLY_DISTRIBUTED` or `COMPLETED`; only `DELIVERED` lines are
  distribution.
- The allocation cap is a **different check** from reconciliation. As shipped, the
  `trg_delivery_item_*` and `trg_spoilage_*` triggers sum every `delivery_item` row
  for the item and never join `delivery`, so changing a delivery's status does not
  release its lines. Step 7 releases a cancelled `PLANNED` delivery only by
  deleting its lines in the same transaction; `FAILED` and `IN_TRANSIT` lines are
  never deleted because they are the only record of the attempt. Releasing those
  states requires migration **G15** (`DATABASE_APPLICATION_MAPPING.md` §5); until
  it lands there is no `FAILED → CANCELLED` transition (§5).
- All arithmetic uses `Decimal` at 2 dp. The recomputation runs inside the same
  transaction as the `delivery` status `UPDATE` / the `spoilage_record` `INSERT`,
  with `SELECT … FROM donation WHERE donation_id = :id FOR UPDATE` held first, then
  `UPDATE donation` + `INSERT donation_status_history` when the value changes.
  No background job recalculates this.
- **Multiple deliveries per donation are normal** (`delivery` has no unique key on
  `donation_id`). Each `DELIVERED` one adds its own lines; the `trg_delivery_item_*`
  cap already sums across all of them, so `balance_kg` can never go negative.
- Distribution is monotonic: a `DELIVERED` delivery cannot be un-delivered and
  deliveries cannot be deleted, so `PARTIALLY_DISTRIBUTED` never reverts.
- **A donation whose surplus will never be delivered cannot be closed out.** The
  schema has no "closed / written off" state and spoilage is a factual claim about
  food, not a decision about logistics. Such a donation stays
  `PARTIALLY_DISTRIBUTED` with a visible `balance_kg`. Documented as gap **G13**.

**Item patch** returns the item with the derived kg fields; a reduction below
`delivered + spoiled` → 409 `below_allocated` with `committed_kg`; a re-parent with
allocations → 409 `item_has_allocations`. Only `item_name`, `quantity_kg`,
`best_before` and `donation_id` are writable. `food_item_id`, `category_id` and
`prepared_at` are creation-only: they are not request fields here and `sfc_app`
holds no UPDATE privilege on them (`AUTH_SECURITY_DESIGN.md` §6.2), so an attempt to
change them fails at validation (422) and would fail at the grant layer.

---

## 4. Inspections

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/api/inspections` | DONOR (own donation), NGO_MANAGER (branch scope), SAFETY_INSPECTOR (scope) | filters `donation_id`, `safety_status`, `from`, `to`; sort `-inspected_at`, which is applied as the total order `inspected_at DESC, inspection_id DESC` (never the timestamp alone) |
| GET | `/api/inspections/queue` | SAFETY_INSPECTOR, NGO_MANAGER (read-only coordination) | see predicate below |
| GET | `/api/inspections/{id}` | same as list | — |
| POST | `/api/inspections` | SAFETY_INSPECTOR | see body |

**Queue predicate** — `donation.donation_status = 'COLLECTED'` **and** the latest
inspection for that donation is not `PASSED` (no row at all, or the latest row is
`FAILED`/`NEEDS_REVIEW`). "Latest" is defined once, identically to the delivery
gate:

```sql
ORDER BY inspected_at DESC, inspection_id DESC
LIMIT 1
```

A donation with an old `PASSED` row and a newer `FAILED` row **is** in the queue; a
new `PASSED` row removes it again. Sorted oldest `pickup_datetime` first. The same
ordering string appears in the SQLAlchemy query helper and in the trigger; a test
asserts the two agree on a seeded mixed history.

**Timestamps may tie; the order is still total.** `inspection_log.inspected_at` is
`DATETIME` with **zero fractional digits**, and `NOW()` on a `+05:30` session also
returns whole seconds, so two back-to-back inserts may carry the *same* value. The
contract therefore does **not** promise strictly increasing timestamps. It promises
a deterministic order: `inspection_id` is the auto-increment primary key, so
`inspected_at DESC, inspection_id DESC` selects the later insert even when the
timestamps are equal — and it is the exact same ordering the delivery trigger uses.
Neither the queue helper, the `GET /api/inspections` sort nor the delivery gate may
order by `inspected_at` alone.

**Create inspection — `inspected_at` is server-authoritative**

```json
{ "donation_id": 42,
  "temperature_c": "4.50",
  "packaging_integrity": "INTACT",
  "safety_status": "PASSED",
  "remarks": "Cold chain intact" }
```

`inspected_at` is **not accepted**. The column is `DATETIME NOT NULL` with no
default, so the service writes it in the inserting statement with a single
database-clock value (`NOW()` under the session timezone), then reads the row back
by `LAST_INSERT_ID()` and returns the stored value:

```json
{ "data": { "inspection_id": 91, "donation_id": 42, "inspector_user_id": 7,
            "inspected_at": "2026-11-20T11:02:37+05:30",
            "temperature_c": "4.50", "packaging_integrity": "INTACT",
            "safety_status": "PASSED", "remarks": "Cold chain intact" } }
```

Why this is not negotiable: the queue and the delivery gate both order by
`inspected_at DESC, inspection_id DESC`. A client-supplied timestamp could place a
`PASSED` row in the future, making it permanently "latest" and letting a later
`FAILED` re-inspection be ignored — a real-world safety failure caused by a request
field. Rejecting the
field (`extra="forbid"`, unknown field → 422 `validation_error` with
`field: "inspected_at"`, `issue: "server_authoritative"`) removes the class of bug
rather than sanitising it.

- No request field can backdate or future-date an inspection. The only clock is
  `NOW()` on the app's connection.
- `inspector_user_id` comes from the session, never the body.
- `safety_status` is the only safety verdict; `temperature_c` is a *plausibility*
  reading. Outside −50…150 → 422 `temperature_implausible` (message says
  plausibility, never "unsafe"); `NULL` is allowed. A `FAILED` verdict with a
  normal temperature and a `PASSED` verdict with a high one are both legal — the
  inspector decides, the number does not.
- No PATCH/DELETE exists: no `UPDATE`/`DELETE` privilege on `inspection_log` and no
  API route. Correction would need gap **G6**.

Tests that must exist (roadmap F5): a body containing `inspected_at` → 422; a
created `PASSED` row can never carry a timestamp later than the server's own now
(asserted against `SELECT NOW()` in the same test transaction); and, because
`DATETIME` has second precision and `NOW()` no fractional part, a **deliberate
tie** — two inspections with identical `inspected_at` and ascending
`inspection_id` — must still resolve to the later insert in both the queue helper
and the delivery gate, via the `inspection_id DESC` tie-break. The test asserts the
higher `inspection_id` wins; it does **not** assert `t2 > t1`.

---

## 5. Deliveries and allocation

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/api/deliveries` | scoped | filters `status`, `driver_user_id`, `route_id`, `branch_id`, `donation_id`, `from`, `to` |
| POST | `/api/deliveries` | NGO_MANAGER | `{donation_id, route_id, recipient_branch_id, driver_user_id?, scheduled_for?, items:[{food_item_id, quantity_delivered_kg}]}` |
| GET | `/api/deliveries/{id}` | scoped | includes items, route, branch, review, and **current** status only |
| PATCH | `/api/deliveries/{id}` | NGO_MANAGER | `driver_user_id` (before departure), `scheduled_for`; `donation_id`, `route_id` and `recipient_branch_id` are never accepted |
| PATCH | `/api/deliveries/{id}/status` | DRIVER (own: `IN_TRANSIT`, `DELIVERED`, `FAILED`), NGO_MANAGER (`FAILED`; `CANCELLED` from `PLANNED` only) | `{target_status}` only — **no note field** |
| POST | `/api/deliveries/{id}/items` | NGO_MANAGER | allocation line, locks the item row |
| PATCH | `/api/delivery-items/{id}` | NGO_MANAGER | `quantity_delivered_kg` only, while `PLANNED`; `delivery_id` and `food_item_id` are never accepted |
| DELETE | `/api/delivery-items/{id}` | NGO_MANAGER | while `PLANNED` |
| POST | `/api/deliveries/{id}/review` | NGO_MANAGER (receiving branch) | `{rating, quality_notes?}` · 409 `duplicate_review` |
| GET | `/api/driver/assignments` | DRIVER | today/upcoming deliveries with branch + items |

**Driver on creation.** `delivery.driver_user_id` is nullable, but
`route.designated_driver_user_id` is `NOT NULL`, so an omitted driver is **not**
ambiguous:

- `driver_user_id` omitted → the service assigns `route.designated_driver_user_id`
  and returns it. The delivery is never stored with `NULL` from this endpoint.
- `driver_user_id` supplied → accepted only when that user is either the route's
  designated driver **or** an `ACTIVE` `DRIVER` with a `route_assignment` row for
  that route. Otherwise 422 `driver_not_eligible`. Any other user (another branch's
  driver, a manager, an inactive account) is rejected before the row is written.
- The database still guarantees the role (`trg_delivery_driver_*`) and refuses
  `IN_TRANSIT` without a driver; the service check exists to answer with a code
  instead of a raw trigger string.

`driver_user_id` is not a field of `PATCH /api/deliveries/{id}/status`; attribution
is frozen once `DELIVERED` (`trg_delivery_driver_update`).

**Delivery identity is immutable.** `PATCH /api/deliveries/{id}` writes only
`driver_user_id` and `scheduled_for`; `donation_id`, `route_id` and
`recipient_branch_id` are create-only and are rejected in the body (422). `sfc_app`
holds no UPDATE privilege on those three columns
(`AUTH_SECURITY_DESIGN.md` §6.2), so a delivery can never be re-pointed at another
donation, route or receiving branch — which is what keeps the manager's branch
scope from being rewritten by an edit. `delivery_item.delivery_id` and
`food_item_id` are likewise create-only; only `quantity_delivered_kg` is writable.

**Create delivery fields** map 1:1 to `delivery` (`donation_id`, `route_id`,
`recipient_branch_id`, `driver_user_id`, `scheduled_for`) plus the first allocation
lines for `delivery_item`. `items` is required with ≥ 1 line: a plan with no
allocation has no deliverable quantity, and `delivery_item` is the only place
quantity exists. `delivered_at` is never accepted — it is written with `NOW()` when
the status becomes `DELIVERED`. `delivery_status` is never accepted at creation;
it starts as `PLANNED`.

`recipient_branch_id` must be a branch the manager manages. `route_id` must belong
to a branch the manager manages or to the donation's pickup branch.

**Status transitions:** `PLANNED → IN_TRANSIT` (driver attributed),
`IN_TRANSIT → DELIVERED` (latest inspection `PASSED`), `PLANNED/IN_TRANSIT →
FAILED` (manager or the assigned driver), `PLANNED → CANCELLED` (manager only).
Because the shipped allocation triggers ignore `delivery.delivery_status`, the
`PLANNED → CANCELLED` transaction must delete that delivery's `PLANNED` lines to
release their quantity; this is the only supported release in Step 7. The
cancellation locks each affected `donation_item` row before deleting, in the same
order as allocation, so a concurrent allocation cannot observe a half-released cap.
`FAILED → CANCELLED` is **not** accepted (409 `invalid_transition`); see the
recovery subsection below. No other target is accepted. `DELIVERED` triggers the
donation recomputation of §3.3 in the same transaction.

Allocation responses always include the affected item's derived `available_kg`. An
over-allocation attempt returns 409 `allocation_exceeds_available` with
`requested_kg`, `available_kg`; the service takes `SELECT … FOR UPDATE` on the
`donation_item` row first and the trigger is the backstop.

**Delivery history is explicitly absent.** `delivery` stores one current row
(`delivery_status`, `delivered_at`, `scheduled_for`). There is no event table, so
the API does not accept a transition note, does not return a delivery timeline, and
the UI shows *current status* labelled as such. Donation status is different: it
**does** have an auditable trail (`donation_status_history`) and therefore **does**
accept a `note`. An auditable delivery-status history needs gap **G12**.

**Failed-delivery recovery — deferred (G15, not available in Step 7).** A `FAILED`
delivery is a terminal outcome for that attempt: it contributes zero to
`delivered_kg` and its lines are not distribution. Recovering the undelivered
quantity is a real requirement, but the shipped allocation cap cannot express it.
`trg_delivery_item_insert/update` and `trg_spoilage_quantity_insert/update` sum
**every** `delivery_item` row for the item and never join `delivery`, so changing
`delivery_status` does not remove those kilograms from the cap. Deleting the
`FAILED` lines would release them but destroys the only record of what was loaded,
and `sfc_app`'s table-level `DELETE` cannot distinguish statuses in the database.
Step 7 therefore keeps `FAILED` closed: `FAILED → CANCELLED` returns 409
`invalid_transition`.

The intended workflow, once migration G15 makes the cap status-aware, is:

1. The manager confirms the physical outcome of the failed trip. Nothing is
   auto-recovered.
2. `NGO_MANAGER` in branch scope transitions `FAILED → CANCELLED`. The five-value
   ENUM already stores `CANCELLED`; no database trigger restricts the transition,
   so this is **service-enforced**, exactly like the rest of the status machine.
3. The cancelled delivery and its lines remain stored, but the lines are excluded
   from the allocation cap because their delivery status is `CANCELLED`. Nothing
   is deleted after G15.
4. Quantities actually lost are recorded with `POST /api/spoilage`, never treated
   as recovered stock. Spoilage stays deducted from the item and can never be
   allocated again.
5. The recovered quantity may then be allocated to a new delivery. The cap sees
   `spoiled + active allocations`, so over-allocation is still rejected with 409
   `allocation_exceeds_available`.
6. The donation is reconciled from `delivered_kg + spoiled_kg` only (§3.3).
   `FAILED` and `CANCELLED` never count as delivered; a donation is `COMPLETED`
   only when that sum equals `donated_kg`.

G15 should perform the cancellation and any loss recording in one service
transaction that holds the `donation_item` locks, so no second allocation can
consume released kilograms between the two writes. No transition note is accepted
(G12 still applies). Until G15 lands, tests 2–4 below are blocked; tests 1 and 5
run in Step 7.

**Recovery tests (1 and 5 run now; 2–4 are the G15 acceptance tests and must be
marked blocked rather than silently skipped):**

1. A delivery whose status is `FAILED` contributes **0** to `delivered_kg` and
   cannot make the donation `PARTIALLY_DISTRIBUTED` or `COMPLETED`.
2. After G15, `FAILED → CANCELLED` keeps the delivery and its lines and removes
   the lines' kilograms from the allocation cap.
3. After G15, the released kilograms can be allocated to a new delivery; a request
   above `donated − spoiled − active allocations` returns 409
   `allocation_exceeds_available`.
4. After G15, spoilage entered for the lost portion stays deducted and cannot be
   allocated again; the balance is `donated − delivered − spoiled`.
5. Cancelling a delivery writes no delivery event (no such table exists — G12) and
   appends **no** `donation_status_history` row, because the donation's delivered
   and spoiled totals do not change.

**Review** maps to `delivery_review`: `{rating 1–5, quality_notes?}`; `review_id`,
`delivery_id` (path), `reviewer_user_id` (session) and `review_date`
(`DEFAULT CURRENT_TIMESTAMP`) are server-side. One review per delivery (UNIQUE).

---

## 6. Spoilage, reference data, people

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/api/spoilage` | scoped | filters `food_item_id`, `donation_id`, `from`, `to` |
| POST | `/api/spoilage` | NGO_MANAGER, DRIVER | `{food_item_id, quantity_spoiled_kg, reason}` — no `reported_at` field; the response returns the server-set value |
| GET | `/api/branches` · `/api/branches/{id}` | all | read, scoped |
| POST | `/api/branches` | NGO_MANAGER | `regional_manager_user_id` is **forced to the caller**; never read from the body |
| PATCH | `/api/branches/{id}` | NGO_MANAGER (managing manager) | `branch_name`, `address`, `pincode`, `contact_no` only; `regional_manager_user_id`, `organization_id` and `established_date` are never accepted; 404 if not managed |
| GET | `/api/routes` · `/api/routes/{id}` | all | includes designated driver, branch, area |
| POST | `/api/routes` | NGO_MANAGER | `designated_driver_user_id` must be an ACTIVE `DRIVER`, required by the schema |
| PATCH | `/api/routes/{id}` | NGO_MANAGER (branch scope) | `designated_driver_user_id`, `coverage_area_id`, `route_type`, `route_status` only; `managing_branch_id` is never accepted |
| GET | `/api/route-assignments` | NGO_MANAGER, DRIVER (own) | filter `route_id`, `user_id` |
| POST | `/api/route-assignments` | NGO_MANAGER | `{user_id, route_id, hours_per_week, assigned_date}` |
| DELETE | `/api/route-assignments/{user_id}/{route_id}` | NGO_MANAGER | composite key, both segments required |
| GET | `/api/coverage-areas` · `/api/food-categories` · `/api/organizations` | all | read-only lookups, unpaginated (bounded) |
| GET | `/api/dependents` | DRIVER (own) | — |
| POST | `/api/dependents` | DRIVER (own) | `{full_name, relationship, date_of_birth?, phone?}` |
| PATCH | `/api/dependents/{driver_user_id}/{dependent_no}` | DRIVER (own) | `full_name`, `relationship`, `date_of_birth`, `phone` only; the composite key is in the path and is never a body field; 404 when `driver_user_id` is not self |
| DELETE | `/api/dependents/{driver_user_id}/{dependent_no}` | DRIVER (own) | composite key |
| GET | `/api/users` | NGO_MANAGER | scope-limited directory, paginated |
| GET | `/api/users/{id}` | self, NGO_MANAGER in scope | no credential fields ever |
| PATCH | `/api/users/{id}` | NGO_MANAGER in scope | `{account_status}` only — `ACTIVE`/`INACTIVE`; never `SUSPENDED`, never `user_role`, never `primary_branch_id` |

**POST `/api/dependents` — the composite key is server-allocated.**
`dependent` has PK (`driver_user_id`, `dependent_no`) and no auto-increment, so the
number cannot come from the client and is never accepted in the body.
`driver_user_id` is the session user. Allocation runs inside the transaction:

```sql
SELECT user_id FROM app_user WHERE user_id = :me FOR UPDATE;         -- serialise this driver
SELECT COALESCE(MAX(dependent_no), 0) + 1 FROM dependent WHERE driver_user_id = :me;
INSERT INTO dependent (driver_user_id, dependent_no, full_name, relationship,
                       date_of_birth, phone) VALUES (…);
```

One retry on `1062 duplicate_resource` covers a lost lock race; the numbers are
consecutive but not guaranteed gap-free after a delete, which the UI must not
promise.

**POST `/api/spoilage`** maps to `spoilage_record`: `reported_by_user_id` from the
session, `quantity_spoiled_kg` > 0 and ≤ `999999.99`, `reason` required ≤ 255. The
body is exactly `{food_item_id, quantity_spoiled_kg, reason}` — **`reported_at` is
not a request field at all**. The column is `DATETIME NOT NULL` **with no default**,
so the service supplies it in the inserting statement from the database clock
(`NOW()` under the `+05:30` session timezone) and returns the stored value:

```json
{ "data": { "spoilage_id": 14, "food_item_id": 88, "donation_id": 42,
            "reported_by_user_id": 9, "quantity_spoiled_kg": "2.00",
            "reason": "Chiller failure overnight",
            "reported_at": "2026-11-20T11:04:02+05:30" } }
```

`reported_at` therefore **cannot be backdated or future-dated by the client**: the
request model forbids extra fields, so a body containing it is 422
`validation_error` (`field: "reported_at"`, `issue: "server_authoritative"`), and
no other request field can influence the value. The response echoes the stored
row, not the request. Recording spoilage recomputes the donation status (§3.3).

Contract test for the same reason as `inspected_at`: a body containing
`reported_at` → 422, and the returned value equals the column and lies inside the
test transaction's `NOW()` window (neither earlier nor later than the server clock).

**POST `/api/branches`** — a manager may only create a branch for themselves. The
server writes `regional_manager_user_id = me` and rejects the field in the body
(422 `validation_error`). Assigning a new branch to an arbitrary manager is an
operator CLI action, not an API one. **`PATCH /api/branches/{id}`** writes only
`branch_name`, `address`, `pincode` and `contact_no`; `regional_manager_user_id`,
`organization_id` and `established_date` are never accepted, and `sfc_app` has no
UPDATE privilege on them — so a manager cannot hand themselves a colleague's
branch, move a branch to another organization, or rewrite the date the branch was
established.

**`PATCH /api/routes/{id}`** writes `designated_driver_user_id`, `coverage_area_id`,
`route_type` and `route_status`. `managing_branch_id` is **immutable after
creation** (set by `POST /api/routes` for a branch the caller manages, never
updated): it is not a request field and has no UPDATE privilege. Moving a route between branches
would silently move every donation and delivery it anchors into a different
manager's scope, so it is an explicit future decision (a reviewed migration plus an
event), never an incidental edit.

**`PATCH /api/dependents/{driver_user_id}/{dependent_no}`** writes `full_name`,
`relationship`, `date_of_birth` and `phone`. The composite primary key is carried in
the path and is never a body field; `driver_user_id` and `dependent_no` have no
UPDATE privilege, so a dependent can never be reassigned to another driver or
renumbered by an edit.

**`PATCH /api/users/{id}`** exists so that account deactivation is a real,
documented operation (the role matrix promises it). Scope: target's
`primary_branch_id` ∈ managed branches, target is not an `NGO_MANAGER`, target is
not self. The body is exactly `{account_status}` in `ACTIVE`/`INACTIVE`. Role
changes, branch assignment, e-mail/name edits and account creation are operator-only
and `sfc_app` holds no UPDATE privilege on `user_role`, `primary_branch_id`,
`supervisor_user_id`, `email`, `full_name` or `phone`
(`AUTH_SECURITY_DESIGN.md` §6.2).

---

## 7. Reports and exports

| Method | Path | Roles | Source (see `DATABASE_APPLICATION_MAPPING.md` §2.1) |
|---|---|---|---|
| GET | `/api/reports/overview` | all | role-specific KPI block (§7.1) |
| GET | `/api/reports/donors` | DONOR (own row), NGO_MANAGER | DONOR: `vw_donor_impact` filtered by own id. MANAGER: base-table aggregate over the **scoped-donation relation** (routed ∪ branch-anchored unrouted), branch predicate inside each subquery |
| GET | `/api/reports/donors/{id}` | DONOR self, NGO_MANAGER | same relation and rule, plus item breakdown from base tables |
| GET | `/api/reports/drivers` | NGO_MANAGER, DRIVER (own) | MANAGER: base-table aggregate scoped to managed branches' routes. DRIVER: own `vw_driver_performance` row + attributed kg |
| GET | `/api/reports/branches` | NGO_MANAGER | aggregate over the managed `branch_id` list only |
| GET | `/api/reports/freshness` | DONOR (own items), NGO_MANAGER (branch scope), SAFETY_INSPECTOR (scope) | `donation_item.best_before` vs now, with open allocations |
| GET | `/api/activity` | all (scoped) | `donation_status_history` + `inspection_log` + `delivery.delivered_at` only (§7.2) |

`?export=csv` on any report returns `text/csv; charset=utf-8` with
`Content-Disposition: attachment` and the same filters as the JSON form. Print is a
frontend route (`/print/reports/...`) rendering the same payload, not a second API.

**Metric scoping rule (non-negotiable).** A global aggregate view may be filtered
**only by its own grouping key**: `vw_donor_impact` by `donor_id`,
`vw_driver_performance` by `driver_id`. Filtering either by a *different*
dimension (a branch, a manager's routes) would return global figures wearing a
branch label, because the aggregate is computed over every branch. Manager-facing
donor, driver and branch reports therefore aggregate **from base tables with the
branch predicate applied before aggregation** — never from a view followed by an
outer filter.

**Manager donation scope is one relation, and the donor report uses it.** The
manager read scope of `ROLE_PERMISSION_MATRIX.md` §1 is a *union of two disjoint
arms*, and every manager-facing donation aggregate (`donated_kg`, `delivered_kg`,
`spoiled_kg`, `balance_kg`, `total_donations`) must use exactly that union:

| Arm | Predicate |
|---|---|
| **A — routed** | `donation.pickup_route_id IS NOT NULL` **and** the route's `managing_branch_id` is a branch where `branch.regional_manager_user_id = me` |
| **B — unrouted, branch-anchored** | `donation.pickup_route_id IS NULL` **and** the donor's `app_user.primary_branch_id` is a branch where `branch.regional_manager_user_id = me` |

The arms are mutually exclusive on `pickup_route_id IS NULL`, so `UNION ALL` cannot
double count a donation. A donation whose donor has no `primary_branch_id` is in
**neither** arm: it stays operator-only (§3.2) and never contributes to a manager's
donor report. An unrouted branch-anchored donation therefore contributes its
`quantity_kg` to `total_donated_kg` and to `balance_kg` **before any route is
assigned**, which is exactly what the manager sees in the unrouted queue — queue
and report reconcile by construction.

`CANCELLED` donations are excluded once, inside the relation, so the three
aggregates cannot disagree about which donations they cover. The canonical SQL is
in `DATABASE_APPLICATION_MAPPING.md` §2.1.

### 7.1 `GET /api/reports/overview` by role

| Role | Fields (all real, empty when no data) |
|---|---|
| DONOR | `open_donations`, `kg_donated`, `kg_delivered`, `kg_spoiled`, `balance_kg`, `donations_by_status[]` |
| NGO_MANAGER | `donations_awaiting_review`, `inspections_pending`, `deliveries_in_transit`, `deliveries_today`, `kg_allocated_open`, `expiring_within_48h`, `avg_rating` |
| DRIVER | `assigned_today`, `in_transit`, `delivered_this_week`, `kg_delivered_this_week`, `next_delivery` |
| SAFETY_INSPECTOR | `queue_size`, `inspected_today`, `failed_last_7d`, `avg_temperature_7d` |

Every field is a `COUNT`/`SUM` over scoped rows. If a figure is zero the UI shows
an explicit empty state — no sample numbers, no fabricated trend lines.

`avg_rating` is the **arithmetic mean of review rows** — `delivery_review` has
`UNIQUE(delivery_id)`, so one delivery contributes exactly one rating. It is never
computed by joining `delivery_item` and `delivery_review` together: that repeats a
delivery's rating once per item line and weights the average by item count. The
canonical aggregate is `AVG(rating)` over one row per reviewed delivery, computed
then joined to the branch aggregate (`DATABASE_APPLICATION_MAPPING.md` §2.1);
the branch report's `avg_rating` follows the same rule.

### 7.2 `/api/activity` is an event feed, not a delivery timeline

Sources are only rows that carry a **real event timestamp**:

- `donation_status_history` → `changed_at` (genuine transitions; reconstructed rows
  are `is_reconstructed = 1` with `changed_at IS NULL` and are rendered as the
  fixed sentence, never as a timestamped event),
- `inspection_log` → `inspected_at`,
- `delivery` → `delivered_at` only.

`delivery` has **no** `created_at`, so the feed contains no "delivery planned" or
"in transit" entries. A current `delivery_status` is never rendered as a sequence
of past states; the feed labels the one delivery event it can prove ("delivered at
…"). Delivery history would need gap **G12**.

---

## 8. Contract guarantees

1. Responses never include credentials, session material, or other users' personal
   contact details beyond what the role's scope shows.
2. **Time (§9):** request/response timestamps are ISO-8601 in `Asia/Kolkata` with an
   explicit `+05:30` offset. The database stores naive local `DATETIME`; the API
   never emits `Z` and never claims UTC.
3. All quantities are 2-decimal strings; clients must not do float arithmetic.
4. `ETag`/`If-None-Match` are used on `GET /api/reports/*` only (cheap win, no
   correctness coupling).
5. A 2xx never means "maybe": every mutation is either committed or rolled back
   before the response is written.
6. Status codes are identical in this document, `ROLE_PERMISSION_MATRIX.md` and
   `AUTH_SECURITY_DESIGN.md`: out-of-scope → **404 `not_found`**, in-scope but
   disallowed for the role → **403 `forbidden_role`**, there is no third
   "not yours" code.
7. Event timestamps (`inspected_at`, `reported_at`, `delivered_at`, `changed_at`,
   `review_date`, `password_changed_at`, `last_login_at`) are **server-set**.
   Business dates a human schedules (`pickup_datetime`, `scheduled_for`,
   `assigned_date`, `best_before`, `prepared_at`) are client-supplied and validated.
   No endpoint accepts a field that both sets an audit event and is client-chosen.
8. Content type is JSON for every endpoint except the documented `?export=csv`
   report response.
9. **Manager branch scope has exactly one source.** The managed-branch set is
   `{branch.branch_id WHERE branch.regional_manager_user_id = me}`. Every
   manager-scoped list, detail endpoint, report, activity query and overview
   figure composes it. If the set is **empty**, manager results are empty and every
   detail is 404 — there is no fallback to the manager's own
   `app_user.primary_branch_id`, no "all branches" mode and no derived catch-all.
   `primary_branch_id` anchors a DONOR's donations (the unrouted queue, §3.2) and a
   SAFETY_INSPECTOR's jurisdiction; it never grants a manager scope. The manager
   donor report uses the same two-arm relation (§7), so a branch-anchored unrouted
   donation appears in both the queue and the donor report before routing, while a
   donation from a donor without `primary_branch_id` appears in neither.
10. **The write surface is column-scoped end to end.** Every writable field is a
   declared request field, and `sfc_app`'s database grants match: the nine
   `UPDATE` grants carry explicit column lists
   (`AUTH_SECURITY_DESIGN.md` §6.2). Identity/ownership columns that no request
   field writes — `donor_user_id`, `user_role`, `primary_branch_id`,
   `regional_manager_user_id`, `route.managing_branch_id`, `delivery.donation_id`,
   `delivery.route_id`, `delivery.recipient_branch_id`, `dependent`'s composite key,
   `donation_item.food_item_id`, `donation_item.category_id` — are not writable and
   are also not request fields.

---

## 9. Time

| Concern | Rule |
|---|---|
| Canonical zone | **`Asia/Kolkata` (UTC+05:30, no DST)** — the deployment is Goa/India; no other zone is configured |
| MySQL session | every pooled connection runs `SET time_zone = '+05:30'` on connect, so `NOW()`, `CURRENT_TIMESTAMP` and `DEFAULT CURRENT_TIMESTAMP` produce IST wall-clock values that match the stored `DATETIME`s |
| Stored form | `DATETIME` (no zone). The value stored *is* IST wall clock. Nothing in the database is UTC |
| Input | ISO-8601 with offset (`2026-11-20T10:30:00+05:30`). An offset-less string is accepted as `Asia/Kolkata` and documented; any other offset is converted to `Asia/Kolkata` before storage |
| Output | `2026-11-20T10:30:00+05:30`. Fractional seconds are omitted (the columns have second precision) |
| Date filters | `from`/`to` are inclusive local *dates*, expanded to `[from 00:00, to+1day 00:00)` in `Asia/Kolkata` |
| Browser | strings are parsed as offset-bearing instants and displayed with `Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata' })`; no `new Date("…")` without an offset |
| Never | label a naive `DATETIME` as UTC, emit `Z`, or call `datetime.utcnow()` |
