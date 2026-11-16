# ROLE PERMISSION MATRIX

Four roles exist in `app_user.user_role`: `DONOR`, `NGO_MANAGER`,
`DRIVER`, `SAFETY_INSPECTOR`. There is no administrator role in the schema and
none is invented; privileged provisioning (creating users, creating branches for
another manager) is a **CLI** action run by the operator with a privileged account
(see `AUTH_SECURITY_DESIGN.md` §2 and §6.4).

Legend: **A** allowed · **D** denied · **C** conditional (rule stated) ·
**—** does not apply.

---

## 1. Record scope — separate read and write predicates

Every scoped query composes one of these. Read and write are stated separately
because they are not the same set: a manager may *read* their own branch's data
without being allowed to mutate it, and a branch-anchored unrouted donation is
readable before it is writable (a donation whose donor has no branch is readable by
no manager at all — §3.2).

| Principal | **Read** predicate | **Write** predicate | Source of truth |
|---|---|---|---|
| DONOR | `donation.donor_user_id = me` (and rows hanging off those donations) | own donations while `PENDING`/`SCHEDULED`; own items while `PENDING`; own password only (no profile-edit endpoint exists) | `donation`, `donation_item` |
| NGO_MANAGER | branch → route → donation, and `delivery.recipient_branch_id`, for `branch.regional_manager_user_id = me`; **plus** unrouted donations whose donor's `app_user.primary_branch_id` ∈ my branches (read-only until routed). Unrouted donations whose donor has **no** `primary_branch_id` are **outside every manager's scope** — see §3.2 | the same branch-scoped rows; assigning a pickup route to an unrouted donation **only** to a route whose `managing_branch_id` ∈ my branches; user `account_status` for users in my branches | `branch`, `route`, `donation`, `delivery`, `app_user` |
| DRIVER | `delivery.driver_user_id = me`; routes with `route.designated_driver_user_id = me`; `route_assignment.user_id = me`; own `dependent` rows; **donations on routes they are designated for** (to confirm collection) | own delivery status (`PLANNED → IN_TRANSIT → DELIVERED`), the collection step on their designated pickup route, own dependents, spoilage on their own deliveries | `delivery`, `route`, `donation`, `dependent` |
| SAFETY_INSPECTOR | donations with `pickup_route_id IS NULL`, or whose pickup route is managed by a branch equal to their `app_user.primary_branch_id`, or that they already inspected | creating an inspection for a donation in read scope; nothing else | `app_user`, `route`, `inspection_log` |

**Unrouted donations are not a shared queue.** The manager read predicate above is
the **only** manager path to `pickup_route_id IS NULL` rows. There is no fallback
that reveals a donation to every manager because its donor lacks a
`primary_branch_id`: a missing branch anchor is not an authorisation. Such rows
return **404** to every manager (list, detail, activity feed and overview counts)
and are surfaced only through the documented operator-authorised queue in
`API_CONTRACT.md` §3.2, a read-only `sfc_ops` CLI (`flask queue unrouted
--orphans`) that writes nothing. Resolution is operator provisioning: the
operator sets the donor's `app_user.primary_branch_id` to the branch with
jurisdiction, after which the donation appears in that branch's queue and the
manager routes it normally. The inspector queue (§4) is unaffected — inspectors
read by donation, not by branch.

**A manager with no managed branches has no branch-level scope.**
`branch.regional_manager_user_id` is the **only** manager scope key. If it matches
no row, the manager's branch-level read and write scope is *empty*: manager-scoped
lists return no rows, `/api/reports/*` returns empty aggregates and zero counts
(empty states, never fabricated figures), every detail-by-id answer is **404**,
`/api/activity` is empty and the overview counts are 0. There is deliberately no
fallback to the manager's own `app_user.primary_branch_id`: that column anchors a
DONOR's donations (and the unrouted queue, §1 above) and a SAFETY_INSPECTOR's
jurisdiction — it is not a manager scope anchor and cannot be used to read or write
a branch the manager does not manage. The operator fixes an unassigned manager by
provisioning `branch.regional_manager_user_id`; the application never infers it.
No "all branches" mode, no derived anchor, no catch-all.

The right-hand column of a row above is the *only* accepted source. No endpoint
takes a `user_id`, `donor_id` or `branch_id` that decides scope from the client.

Scoping is applied in the **repository layer as a mandatory predicate** — every
scoped query starts from a `scope_read(user)` / `scope_write(user)` helper; a
blueprint cannot opt out.

---

## 2. Authentication surface

| Operation | DONOR | NGO_MANAGER | DRIVER | SAFETY_INSPECTOR |
|---|---|---|---|---|
| Login / logout | A | A | A | A |
| `GET /api/auth/me` | A | A | A | A |
| Activate account with token | A | A | A | A |
| Change own password | A | A | A | A |
| Use a reset token (confirm step) | A | A | A | A |
| Request a password reset (public "email me" flow) | **D — does not exist in v1** | D | D | D |
| Issue an activation token (`POST /api/users/{id}/activation-token`) | D | C — only users whose `primary_branch_id` is a branch they manage, and never another NGO_MANAGER | D | D |
| Issue a password-reset token (`POST /api/users/{id}/password-reset-token`) | D | C — same scope rules; never another manager, never self | D | D |
| Create a user account | D | **D — operator CLI only** | D | D |
| Change a user's role | D | **D — operator CLI only** | D | D |
| Activate / deactivate a user (`PATCH /api/users/{id}` → `account_status`) | D | C — users in managed branches, never another manager, never self | D | D |

There is no mail channel in v1, so reset and activation are **assisted**: the
manager (or the operator CLI) issues the token and the API returns the raw value
exactly **once** in that 201 response. It is never logged, never stored in
plaintext, and never appears in `GET /api/users/{id}`, `GET /api/auth/me`, a list,
an export or any later response. The holder completes the flow through
`POST /api/auth/password-reset/confirm` (or `POST /api/auth/activate`), both of
which redeem the token atomically (`AUTH_SECURITY_DESIGN.md` §1.5).

---

## 3. Donations

| Operation | DONOR | NGO_MANAGER | DRIVER | INSPECTOR |
|---|---|---|---|---|
| List donations | C — own only | C — branch scope (incl. branch-anchored unrouted read; no catch-all) | C — donations on deliveries assigned to them | C — inspection scope |
| Read one donation | C — own | C — scope | C — designated capture route / own deliveries | C — scope |
| Create donation (+ items, one transaction) | A | D | D | D |
| Set `pickup_route_id` at creation | C — optional, but only an `ACTIVE` route of type PICKUP/MIXED whose `managing_branch_id` **equals my own `primary_branch_id`**; with no `primary_branch_id` the field must be omitted (422 if supplied) | — | — | — |
| Assign a pickup route to an unrouted donation (`PATCH /api/donations/{id}/route`) | D | C — donor's `primary_branch_id` must be a branch they manage; route must belong to a branch they manage; `PENDING`/`SCHEDULED` only; otherwise 404 | D | D |
| Edit pickup address/pincode/contact | C — own, `PENDING`/`SCHEDULED` | D | D | D |
| Add item to a donation | C — own, `PENDING` | D | D | D |
| Edit item fields (`item_name`, `quantity_kg`, `best_before`) | C — own, `PENDING`; never below delivered + spoiled | C — branch scope, `APPROVED`+ only, never below delivered + spoiled | D | D |
| Change an item's `food_item_id`, `category_id` or `prepared_at` | D — creation-only: no request field and no UPDATE grant | D | D | D |
| Re-parent an item to another donation | C — own, `PENDING`, only if it has no delivery/spoilage rows | D | D | D |
| Delete a donation or an item | D — no DELETE grant on `donation`/`donation_item` | D | D | D |
| Confirm collection (`SCHEDULED → COLLECTED`) | D | A — branch scope | C — **only the route's `designated_driver_user_id`** | D |
| Change status (other targets) | C — `PENDING → CANCELLED` only | C — see §3.1 | D | D |
| Read status history | C — own | C — scope | C — assigned | C — scope |
| Read the reconstructed-snapshot note | A | A | A | A |

**Donor route selection is branch-confined.** A route's `managing_branch_id`
decides which manager's scope a donation enters, so a donor may only name a route
of their **own** `app_user.primary_branch_id`; with no primary branch the field
must be omitted. Without that check a donor could prepopulate another manager's
queue and, worse, place a donation into a branch they have no relationship with.
The service enforces it at creation (`API_CONTRACT.md` §3); the schema only
enforces that the route exists. Managers remain the only cross-branch routing
path, and that path is limited to routes they manage.

### 3.1 Donation status transitions (service-enforced; the schema does not)

| From | To | Who | Extra condition |
|---|---|---|---|
| PENDING | SCHEDULED | NGO_MANAGER | `pickup_route_id` assigned |
| PENDING | REJECTED | NGO_MANAGER | reason in the history note |
| PENDING | CANCELLED | DONOR (owner) | no delivery exists |
| SCHEDULED | COLLECTED | DRIVER (designated on the pickup route) **or** NGO_MANAGER | driver path requires `donation.pickup_route_id` → `route.designated_driver_user_id = me` |
| COLLECTED | APPROVED | NGO_MANAGER | latest inspection `PASSED` (the DB also blocks delivery, not this transition) |
| COLLECTED | REJECTED | NGO_MANAGER | latest inspection `FAILED` |
| APPROVED | PARTIALLY_DISTRIBUTED | **system** | `delivered_kg + spoiled_kg > 0` and `balance_kg > 0` |
| APPROVED / PARTIALLY_DISTRIBUTED | COMPLETED | **system** | `balance_kg = 0` exactly |

**Collection has exactly one driver and one manager path, and the driver path is
verifiable from the schema:** `donation.pickup_route_id → route.designated_driver_user_id`.
A driver who is merely assigned to the route via `route_assignment` cannot confirm
collection; if they are not the designated driver the donation is out of their read
scope and the API answers 404. The SPA only renders the "Confirm collection" action
when `/api/donations/{id}` returns that donation, so the button and the permission
cannot disagree.

**Distribution is quantity-based.** A planned allocation is not distribution:
creating a delivery or moving it to `IN_TRANSIT` changes no donation status.
`PARTIALLY_DISTRIBUTED` needs delivered-or-spoiled quantity > 0 with a positive
balance; `COMPLETED` needs the balance to be exactly zero — never "one delivery
succeeded". `FAILED`/`CANCELLED` deliveries contribute zero delivered kilograms.
The full calculation, the `Decimal` rule, the same-transaction recomputation and the
multiple-deliveries rule are in `API_CONTRACT.md` §3.3.

Every accepted transition writes exactly one `donation_status_history` row with
`changed_by_user_id = actor`, `changed_at = NOW()`, `is_reconstructed = 0`.
Illegal transitions → **409 `invalid_transition`**; `PARTIALLY_DISTRIBUTED` and
`COMPLETED` are not requestable (422 `validation_error`).

A donation whose remaining kilograms will never be delivered cannot be formally
closed out — there is no "written off" state (gap **G13**). It stays
`PARTIALLY_DISTRIBUTED` with a visible balance rather than a fabricated completion.

---

## 4. Inspections

| Operation | DONOR | NGO_MANAGER | DRIVER | INSPECTOR |
|---|---|---|---|---|
| List the inspection queue | D | C — branch scope, **read-only** coordination view | D | A — scope |
| Read inspections | C — own donations | C — scope | D | C — scope |
| Create an inspection | D | D | D | A — `inspector_user_id` must be self (trigger checks role) |
| Supply `inspected_at` | — | — | — | **D — server-set only** (unknown field → 422) |
| Edit or delete an inspection | D | D | D | **D** — no `UPDATE`/`DELETE` grant; a correction needs gap **G6** |
| Set `temperature_c` | — | — | — | C — `NULL` or −50…150; outside → 422 phrased as *plausibility*, never "unsafe" |
| Decide `safety_status` | — | — | — | A — independent of temperature |

A FAILED inspection blocks delivery (DB trigger) and lets the manager reject the
donation. Re-inspection is allowed: a later PASSED inspection unblocks delivery and
removes the donation from the queue, because the queue reads the **latest** row
(`inspected_at DESC, inspection_id DESC`).

"Latest" is that pair, never the timestamp alone. `inspected_at` is `DATETIME` with
**zero fractional digits** and `NOW()` is whole-second, so two inspections recorded
back-to-back may share a timestamp; `inspection_id` (auto-increment PK) is the
tie-break that makes the order total and deterministic, in favour of the later
insert. The service therefore guarantees **server-controlled** timestamps, not
strictly increasing ones, and uses the identical ordering as the delivery trigger.

`inspected_at` is written by the database clock inside the inserting statement and
returned from the stored row. Letting a client choose it would let a future-dated
`PASSED` row outrank every real inspection in the delivery gate — see
`API_CONTRACT.md` §4.

---

## 5. Deliveries and allocation

| Operation | DONOR | NGO_MANAGER | DRIVER | INSPECTOR |
|---|---|---|---|---|
| List deliveries | C — own donations | C — recipient-branch scope | C — `driver_user_id = me` | D |
| Create delivery (plan) | D | A — branch scope; donation must be `APPROVED`/`PARTIALLY_DISTRIBUTED` | D | D |
| Choose the driver at creation | — | A — defaults to `route.designated_driver_user_id`; an override must be that driver or an ACTIVE `DRIVER` with a `route_assignment` on the route | — | — |
| Add/adjust allocation lines | D | A — before the delivery leaves `PLANNED` | D | D |
| Remove an allocation line | D | A — while `PLANNED` (DELETE granted) | D | D |
| Assign or change driver later | D | A — **only while status < IN_TRANSIT** | D | D |
| Change a delivery's `donation_id`, `route_id` or `recipient_branch_id` | D | D — create-only: no request field and no UPDATE grant | D | D |
| Start trip (`PLANNED → IN_TRANSIT`) | D | D | A — own delivery, driver already attributed | D |
| Mark `DELIVERED` | D | D — the driver records it | A — own delivery; attribution stays fixed | D |
| Mark `FAILED` | D | A — branch scope | A — own delivery | D |
| Cancel a delivery | D | A — `PLANNED` only; deletes its `PLANNED` lines in the same transaction to release their quantity. `FAILED → CANCELLED` is not available in Step 7 (G15) | D | D |
| Submit a delivery review | D | C — **only the receiving branch's `regional_manager_user_id`** (trigger-enforced), one per delivery | D | D |
| Read a review | C — own donation | C — scope | C — own delivery | D |

A delivery status change carries **no note**. `delivery` holds only the current
status and timestamps; there is no delivery-status history table, so nothing here is
presented as history or reconstructed. The UI labels it "current status". An
auditable delivery event log would require gap **G12**
(`DATABASE_APPLICATION_MAPPING.md` §5).

Delivery status changes are service-enforced. The five-value ENUM accepts
`CANCELLED` from any state and no trigger restricts the sequence, so the database
would permit `FAILED → CANCELLED`; Step 7 does not. The allocation cap is why: the
triggers sum every `delivery_item` row regardless of the parent delivery's status,
so a status-only cancellation releases nothing, and deleting a `FAILED` delivery's
lines would destroy the only record of the attempt. Until **G15** makes the cap
status-aware, `FAILED` is terminal, the API returns 409 `invalid_transition`, and
the UI must not offer a cancel action for it. `sfc_app` also holds a table-level
`DELETE` on `delivery_item`, so "only `PLANNED` lines may be deleted" is a service
rule rather than a grant. See `API_CONTRACT.md` §5 for the deferred recovery
workflow and its tests.

Marking `DELIVERED` is the trigger for the donation reconciliation in §3.1: the
same transaction locks the donation, recomputes delivered/spoiled/balance from
committed `DELIVERED` rows, and writes `PARTIALLY_DISTRIBUTED` or `COMPLETED` plus
the history row. A manager cannot set those two statuses directly.

Allocation is the concurrency-sensitive path: the service takes
`SELECT … FOR UPDATE` on each `donation_item` row **before** reading existing
deliveries/spoilage, and performs the insert inside the same transaction. The
`trg_delivery_item_*` cap is the backstop, so a lost lock race becomes a 409, not
silent over-allocation.

---

## 6. Spoilage

| Operation | DONOR | NGO_MANAGER | DRIVER | INSPECTOR |
|---|---|---|---|---|
| Record spoilage | D | A — scope | A — deliveries they carried | C — may flag on a FAILED inspection; recording is the manager's action |
| Read spoilage for own donation | A | A | C — own deliveries | C — scope |
| Supply `reported_at` | — | — | — | — (no role may: not a request field) |
| Delete spoilage | D — no DELETE grant | D | D | D |

Spoilage counts against the item's allocation cap (trigger) **and** against the
donation's reconciliation, so recording it moves `APPROVED → PARTIALLY_DISTRIBUTED`
and can complete a donation. The request body is
`{food_item_id, quantity_spoiled_kg, reason}` and nothing else: `reported_at` is
`DATETIME NOT NULL` with no default, written from the database clock inside the
INSERT and returned from the stored row, so **no role can backdate or future-date
it** and a body containing the field is 422 `validation_error` (`API_CONTRACT.md`
§6). The UI must say that the figure reduces what may still be delivered.

---

## 7. Reference data and people

| Operation | DONOR | NGO_MANAGER | DRIVER | INSPECTOR |
|---|---|---|---|---|
| Read organizations / branches / coverage areas / food categories / routes | A | A | A | A |
| Create a branch | D | C — only for themselves: `regional_manager_user_id` is forced to the caller | D | D |
| Edit a branch | D | C — only branches they manage; `branch_name`, `address`, `pincode`, `contact_no` only, never `regional_manager_user_id`, `organization_id` or `established_date` | D | D |
| Create or edit a route | D | A — branch scope; `designated_driver_user_id` is `NOT NULL` and must be a `DRIVER` (trigger); `managing_branch_id` is set at creation and immutable after | D | D |
| Assign a driver to a route / hours | D | A — `route_assignment` insert/delete in scope (no `UPDATE`: change hours by replacing the row) | D | D |
| Add/edit/remove a dependent | D | D | A — own `driver_user_id` only; `dependent_no` is server-allocated; neither key column is editable | D |
| Read other users' profiles | D | C — users in managed branches | C — self only | D |
| Activate / deactivate a user | D | C — §2 | D | D |
| Delete a user | D | D — no `DELETE` on `app_user`; deactivate via `account_status` | D | D |
| Create a user / change a role | D | D — operator CLI; the API cannot write `user_role` or `primary_branch_id` | D | D |

Creating a branch for an arbitrary manager is **not** an API capability: a manager
may only create one for themselves, and assigning an existing branch to another
manager is operator-only. Otherwise a manager could hand themselves a colleague's
branch — or hand a colleague theirs.

---

## 8. Reports

| Report | DONOR | NGO_MANAGER | DRIVER | INSPECTOR |
|---|---|---|---|---|
| Own impact — `vw_donor_impact` filtered by own `donor_id` | A | — | — | — |
| Donor impact for the branch's donors | D | C — **base-table aggregate over the scoped-donation relation (routed ∪ branch-anchored unrouted), branch predicate before aggregation** | D | D |
| Driver performance | D | C — **base-table aggregate over managed branches' routes** | C — own `vw_driver_performance` row + attributed kg | D |
| Branch performance | D | C — managed `branch_id` list only | D | D |
| Freshness / expiry monitor | C — own items | A — branch scope | D — `best_before` is shown inline on their delivery items | A — scope |
| Activity feed (`/api/activity`) | C — own donations | C — branch scope | C — own deliveries | C — scope |
| CSV export of a report | C — own | A | C — own | A |
| Print view | C — own | A | C — own | A |

**Manager donor-report scope is the same union as donation reads.** The report
counts a donation when **either** its pickup route's branch is managed (routed)
**or** it is unrouted and its donor's `primary_branch_id` is a managed branch
(branch-anchored). Donations whose donor has no `primary_branch_id` never enter a
manager report. The two arms are disjoint on `pickup_route_id IS NULL`, so a
donation is counted once, and an unrouted donation contributes its donated and
balance kilograms before routing — matching what the manager sees in the queue.
The canonical SQL is in `DATABASE_APPLICATION_MAPPING.md` §2.1.

**Why the manager rows cannot use the views.** `vw_donor_impact` and
`vw_driver_performance` aggregate globally and group by donor/driver. Filtering
`vw_donor_impact` by `donor_id ∈ (donors of my branches)` would still return that
donor's *whole* history, including kilograms collected by other branches;
filtering `vw_driver_performance` by a branch has no branch column at all. Both are
therefore forbidden for manager reporting. Only the **own-row** case is safe,
because the filter key is the view's grouping key.

Exact queries, including the "aggregate in separate subqueries, never join two
one-to-many children" rule and the "one row per reviewed delivery before averaging"
rule, are in `DATABASE_APPLICATION_MAPPING.md` §2.1.

`vw_donor_sustainability` remains available as the legacy metric; the UI labels its
number **"allocated (legacy metric)"** and uses `vw_donor_impact` for the canonical
delivered/spoiled/balance figures. Showing both without a label would look like a
contradiction.

---

## 9. Enforcement rules (backend, non-negotiable)

1. The session cookie yields only `user_id` (plus session metadata: `sid`, `iat`,
   `seen`, `epoch`, `csrf_id`). `sid` has exactly one use — the CSRF MAC input
   (`AUTH_SECURITY_DESIGN.md` §2.3) — and is never an authorization fact.
   `user_role`, `account_status` and `primary_branch_id` are **re-read from
   `app_user` on every request** and are the only inputs to the role gate and scope
   predicate; no role or branch value is taken from the cookie, the request body, a
   header or a query string. `primary_branch_id` feeds **donor and inspector**
   scope only; a manager's scope is the managed-branch set from
   `branch.regional_manager_user_id` (rule 10).
2. Every scoped query composes `scope_read(user)` / `scope_write(user)` first; a
   repository helper that omits it fails code review by rule.
3. Ownership checks happen inside the service **and** inside the transaction that
   writes (`SELECT … FOR UPDATE` where a write depends on the current row).
4. Denied access returns **404** for records outside scope (not 403), so the API
   does not confirm the existence of other branches' or donors' records. 403 is
   reserved for "in scope but this role may not perform the action".
5. Role gates are duplicated at the database where they already exist (donor,
   inspector, driver, reviewer). The service maps those SQLSTATEs to the codes in
   `API_CONTRACT.md` §1.1, never to the raw trigger text.
6. No endpoint accepts a `user_id`, `branch_id`, `donor_id`, `inspector_user_id`,
   `reviewer_user_id`, `reported_by_user_id` or `dependent_no` that decides scope
   or identity; those are derived server-side.
7. Frontend route guards are a UX convenience only. Every protected page is backed
   by an endpoint that enforces the same rule.
8. List endpoints are always paginated and scoped; there is no "return everything"
   mode for any role.
9. The role sets in this document and in `API_CONTRACT.md` are identical per
   endpoint. A mismatch is a bug in the documents, not a choice.
10. **Manager scope is single-sourced.** `scope_read`/`scope_write` for an
    NGO_MANAGER are built from `branch.regional_manager_user_id = me` and nothing
    else. `app_user.primary_branch_id` is never OR-ed into a manager predicate, no
    "all branches" branch exists in the helper, and an empty managed set yields
    empty lists, empty reports, zero counts and 404 for detail. A test asserts that
    a manager whose only `primary_branch_id` points at a branch they do not manage
    cannot read that branch's rows.
