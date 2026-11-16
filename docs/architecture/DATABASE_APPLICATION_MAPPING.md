# DATABASE ↔ APPLICATION MAPPING

Source of truth: `database/schema_post_migrations.sql` (verified in Phase 2:
18 tables · 3 views · 21 triggers · 12 CHECKs · 29 FKs · 118 rows in `_dev`,
of which 104 are the preserved originals).

Every feature below maps to a real object. Nothing is invented; anything wanted but
absent is listed in §5 as a proposed future migration, not silently assumed. Column
types are quoted from the DDL, not remembered.

---

## 1. Tables → features

| Table | Rows (dev) | Owned by feature | Application writes | Notes the application must obey |
|---|---|---|---|---|
| `organization` | 3 | Reference data | **none** (SELECT only) | 5 columns, no status flag. Read-only for the API; edits are an operator action |
| `branch` | 5 | Branch management (NGO_MANAGER) | INSERT; UPDATE columns `branch_name`, `address`, `pincode`, `contact_no` only | `established_date DATE NOT NULL`; `regional_manager_user_id` **is** the manager's scope key. Triggers on INSERT/UPDATE require that user to hold `NGO_MANAGER`. A manager-created branch is forced to themselves; the manager link, organization and established date are not API-writable |
| `app_user` | 15 | People / profile | UPDATE (`account_status` only) | `email` UNIQUE, `phone` `NOT NULL`; `user_role`/`account_status` ENUMs; `primary_branch_id`, `supervisor_user_id` self-FK. No `created_at`, no DELETE. Accounts are created by the operator CLI, not the API; `user_role` and `primary_branch_id` have no UPDATE grant |
| `user_credential` | 0 | Authentication | INSERT (first invite); UPDATE (password/token/lock/version columns only) | 11 columns; PK `user_id` (one row per user); scrypt hash; `reset_token_hash` CHAR(64) UNIQUE; `password_changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP` (second precision); both CHECKs must hold. `user_id`, `created_at` and `updated_at` are not granted (`updated_at` is `ON UPDATE CURRENT_TIMESTAMP`) |
| `route` | 5 | Route & driver assignment | INSERT; UPDATE columns `designated_driver_user_id`, `coverage_area_id`, `route_type`, `route_status` only | `designated_driver_user_id` is **NOT NULL** and must be a `DRIVER` (trigger). `route_type` PICKUP/DISTRIBUTION/MIXED, `route_status` ACTIVE/INACTIVE; `managing_branch_id` is set at creation and immutable after (no UPDATE grant) |
| `coverage_area` | 5 | Lookup | **none** (SELECT only) | 4 columns, no geometry — no map, no polygon |
| `route_assignment` | 8 | Roster / hours | INSERT, DELETE (no UPDATE) | PK (`user_id`,`route_id`); `hours_per_week DECIMAL(5,2)`; `chk_route_hours` 0 < h ≤ 168. Hours change by replacing the row |
| `donation` | 5 | Donation lifecycle | INSERT; UPDATE columns `pickup_route_id`, `pickup_address`, `pickup_pincode`, `pickup_contact`, `donation_status` only | **No `created_at`** — only `pickup_datetime DATETIME NOT NULL`. `pickup_route_id` **nullable** (unrouted workflow, §3). `donation_status` 8-value ENUM; `PARTIALLY_DISTRIBUTED`/`COMPLETED` are system-derived; `donor_user_id`, `pickup_datetime` and `urgency_level` are not API-writable after creation |
| `donation_item` | 13 | Food items (kg) | INSERT; UPDATE columns `item_name`, `quantity_kg`, `best_before`, `donation_id` only (no DELETE) | `quantity_kg DECIMAL(8,2) > 0`; `best_before NOT NULL`, `prepared_at` nullable; `chk_food_dates`; guard trigger blocks shrink below delivered+spoiled and re-parent with allocations. `food_item_id`, `category_id` and `prepared_at` are creation-only |
| `donation_status_history` | 5 | Timeline | INSERT only | Append-only by trigger **and** by grant. 5 rows are `is_reconstructed = 1` with `changed_at NULL`; `note` VARCHAR(255) |
| `inspection_log` | 5 | Safety inspection | INSERT only | `inspected_at DATETIME NOT NULL` **with no default → written by the service from the database clock**, never from the client. Zero fractional digits and `NOW()` is whole-second, so back-to-back rows may tie; the latest-row order is `inspected_at DESC, inspection_id DESC`, which is total. `temperature_c DECIMAL(5,2)` nullable, CHECK −50…150; inspector role enforced by trigger |
| `delivery` | 5 | Logistics | INSERT; UPDATE columns `driver_user_id`, `scheduled_for`, `delivery_status`, `delivered_at` only (no DELETE) | `driver_user_id` nullable but `route.designated_driver_user_id` is not, so the API defaults it; `delivered_at`/`scheduled_for` nullable; `delivery_status` 5-value ENUM; IN_TRANSIT/DELIVERED require the latest inspection `PASSED` (trigger). `donation_id`, `route_id` and `recipient_branch_id` are immutable |
| `delivery_item` | 15 | Allocation lines | INSERT; UPDATE `quantity_delivered_kg` only; DELETE | `quantity_delivered_kg DECIMAL(8,2) > 0`; UNIQUE(`delivery_id`,`food_item_id`); triggers enforce same-donation and cap ≤ donated − spoiled; `delivery_id` and `food_item_id` are immutable |
| `spoilage_record` | 1 | Loss recording | INSERT only (no PATCH) | `quantity_spoiled_kg DECIMAL(8,2) > 0`; `reported_at DATETIME NOT NULL` **with no default → supplied by the service from the database clock**, never a request field; `reason` `NOT NULL` VARCHAR(255); triggers cap total allocation |
| `delivery_review` | 5 | Delivery outcome | INSERT only (no edit) | UNIQUE `delivery_id` (one review); `rating TINYINT` 1–5 CHECK; `quality_notes TEXT`; `review_date DEFAULT CURRENT_TIMESTAMP`; trigger restricts author to the receiving branch's regional manager |
| `dependent` | 6 | Driver's dependants | INSERT; UPDATE columns `full_name`, `relationship`, `date_of_birth`, `phone` only; DELETE | PK (`driver_user_id`,`dependent_no`) with **no auto-increment** — the number is server-allocated (§3 of the API contract). Both key columns are immutable (no UPDATE grant); the only "recipient" object in the schema |
| `schema_migrations` | 9 | Infrastructure | **none — no grant of any kind** | Runner-owned. `sfc_app` cannot SELECT, INSERT, UPDATE or DELETE it (`AUTH_SECURITY_DESIGN.md` §6.2) |

## 2. Views → features

| View | Security | Columns | Used by |
|---|---|---|---|
| `vw_donor_impact` | **INVOKER** (definer `sfc_migrator`) | donor_id, donor_name, total_donations, total_donated_kg, delivered_kg, spoiled_kg, undistributed_balance_kg | **donor's own** dashboard/report and CSV. **Canonical** numbers |
| `vw_donor_sustainability` | DEFINER=root | …, total_distributed_kg, total_spoiled_kg | Legacy comparison only; `total_distributed_kg` counts every allocation regardless of status. UI labels it "allocated (legacy metric)" |
| `vw_driver_performance` | DEFINER=root | driver_id, driver_name, assigned_routes, completed_deliveries, delivered_quantity_kg | **driver's own** report row, credited by **route designation**, always shown next to the attributed figure |

The two DEFINER=root views are a standing privilege-escalation risk: a caller with
`SELECT` on the view reads its base tables with root's rights, so column-level
intent is bypassed. The application never uses them for authorization and never for
manager reporting; replacement is gap **G8**.

### 2.1 Report queries — aggregate before filtering, never after

**The rule.** A global aggregate view may be filtered **only by its own grouping
key**. `vw_donor_impact` groups by donor, so `WHERE donor_id = :me` returns that
donor's own row — correct for a donor. `WHERE donor_id IN (donors of my branches)`
returns each donor's **whole** history, including kilograms collected by other
branches — wrong, because the aggregate was computed over every branch. Same for
`vw_driver_performance`, which has no branch column at all. Manager-facing figures
therefore come from base tables with the branch predicate applied **before**
aggregation — inside the arms of the scoped-donation relation or the `WHERE` clause
of each subquery.

**Second rule.** Never join two one-to-many children into the same aggregate.
`delivery_item` and `spoilage_record` both fan out under a donation, so joining both
and summing multiplies kilograms. Aggregate each in its own subquery, then join on
the donor/driver key.

**Third rule.** A review belongs to the **delivery**, not to its lines.
`delivery_review` is unique per delivery, but `delivery_item` is one-to-many, so
joining both and averaging the rating repeats each review once per item line and
weights the branch average by item count. Build **one row per reviewed delivery**
first, aggregate the rating by branch from that, and join the finished branch
aggregates only after both calculations are complete.

**Scope relation.** Manager-facing donation aggregates do not filter donations with
a predicate of their own. They use one authoritative **scoped-donation relation**
that is the union of the two manager read arms:

- **Routed:** `donation.pickup_route_id IS NOT NULL` and the route's
  `managing_branch_id` is a branch where `branch.regional_manager_user_id = me`.
- **Unrouted, branch-anchored:** `donation.pickup_route_id IS NULL` and the donor's
  `app_user.primary_branch_id` is a branch where
  `branch.regional_manager_user_id = me`.

The arms are mutually exclusive on `pickup_route_id IS NULL`, so `UNION ALL` cannot
double count; a donation whose donor has no `primary_branch_id` is in neither arm
and stays operator-only (`API_CONTRACT.md` §3.2). Every aggregate — donated,
delivered, spoiled and therefore balance — reads the same relation.

| Report | Role | Query |
|---|---|---|
| Donor impact | DONOR | `SELECT * FROM vw_donor_impact WHERE donor_id = :me` — safe: grouping key = filter key |
| Donor report, list | NGO_MANAGER | the CTE below — the scoped-donation relation covers routed **and** branch-anchored unrouted donations; branch predicate applied before aggregation |
| Driver performance | DRIVER | `SELECT * FROM vw_driver_performance WHERE driver_id = :me` plus the attributed-kg query below (shown side by side) |
| Driver report, list | NGO_MANAGER | the branch-scoped driver aggregate below |
| Branch performance | NGO_MANAGER | the branch aggregate below, grouped by `branch_id`, restricted to the managed list |

```sql
-- NGO_MANAGER · donor report. One scoped-donation relation, used unchanged by all
-- three aggregates. The arms are disjoint on pickup_route_id, so no donation is
-- counted twice; CANCELLED is excluded once, inside the relation.
WITH scoped AS (
  -- A. routed: the pickup route's branch is managed by :me
  SELECT d.donation_id, d.donor_user_id
    FROM donation d
    JOIN route   r ON r.route_id = d.pickup_route_id
    JOIN branch  b ON b.branch_id = r.managing_branch_id
   WHERE d.pickup_route_id IS NOT NULL
     AND b.regional_manager_user_id = :me
     AND d.donation_status <> 'CANCELLED'
  UNION ALL
  -- B. unrouted, but the donor is anchored to a managed branch
  SELECT d.donation_id, d.donor_user_id
    FROM donation d
    JOIN app_user u ON u.user_id = d.donor_user_id
    JOIN branch   b ON b.branch_id = u.primary_branch_id
   WHERE d.pickup_route_id IS NULL
     AND u.primary_branch_id IS NOT NULL
     AND b.regional_manager_user_id = :me
     AND d.donation_status <> 'CANCELLED'
),
donated AS (
  SELECT s.donor_user_id,
         COUNT(DISTINCT s.donation_id) AS total_donations,
         SUM(i.quantity_kg)            AS total_donated_kg
    FROM scoped s JOIN donation_item i ON i.donation_id = s.donation_id
   GROUP BY s.donor_user_id
),
delivered AS (
  SELECT s.donor_user_id, SUM(di.quantity_delivered_kg) AS delivered_kg
    FROM scoped s
    JOIN delivery      dl ON dl.donation_id = s.donation_id
    JOIN delivery_item di ON di.delivery_id = dl.delivery_id
   WHERE dl.delivery_status = 'DELIVERED'
   GROUP BY s.donor_user_id
),
spoiled AS (
  SELECT s.donor_user_id, SUM(sr.quantity_spoiled_kg) AS spoiled_kg
    FROM scoped s
    JOIN donation_item   i  ON i.donation_id = s.donation_id
    JOIN spoilage_record sr ON sr.food_item_id = i.food_item_id
   GROUP BY s.donor_user_id
)
SELECT u.user_id AS donor_id, u.full_name AS donor_name,
       COALESCE(do.total_donations, 0)  AS total_donations,
       COALESCE(do.total_donated_kg, 0) AS total_donated_kg,
       COALESCE(dv.delivered_kg, 0)     AS delivered_kg,
       COALESCE(sp.spoiled_kg, 0)       AS spoiled_kg,
       COALESCE(do.total_donated_kg, 0) - COALESCE(dv.delivered_kg, 0)
                                        - COALESCE(sp.spoiled_kg, 0) AS balance_kg
  FROM app_user u
  JOIN donated do ON do.donor_user_id = u.user_id
  LEFT JOIN delivered dv ON dv.donor_user_id = u.user_id
  LEFT JOIN spoiled   sp ON sp.donor_user_id = u.user_id
 WHERE u.user_role = 'DONOR'
 ORDER BY u.full_name;
-- An unrouted branch-anchored donation therefore contributes its quantity_kg to
-- total_donated_kg and its full amount to balance_kg before any route exists,
-- because arm B needs no route at all.
```

```sql
-- NGO_MANAGER · driver report. Scope is the branch that manages the delivery's route.
SELECT dl.driver_user_id, u.full_name,
       COUNT(DISTINCT dl.delivery_id)          AS completed_deliveries,
       COALESCE(SUM(di.quantity_delivered_kg), 0) AS delivered_kg
  FROM delivery dl
  JOIN route   r ON r.route_id = dl.route_id
  JOIN branch  b ON b.branch_id = r.managing_branch_id
  JOIN app_user u ON u.user_id = dl.driver_user_id
  LEFT JOIN delivery_item di ON di.delivery_id = dl.delivery_id
 WHERE b.regional_manager_user_id = :me
   AND dl.delivery_status = 'DELIVERED'
 GROUP BY dl.driver_user_id, u.full_name;
-- delivery_item is the only child joined here, and COUNT(DISTINCT) protects the
-- delivery count; no second child → no fan-out.

-- DRIVER · own attributed performance (paired with the view row)
SELECT COUNT(DISTINCT dl.delivery_id)               AS completed_deliveries,
       COALESCE(SUM(di.quantity_delivered_kg), 0)   AS delivered_kg
  FROM delivery dl
  LEFT JOIN delivery_item di ON di.delivery_id = dl.delivery_id
 WHERE dl.driver_user_id = :me AND dl.delivery_status = 'DELIVERED';
```

```sql
-- NGO_MANAGER · branch performance. Three independent branch-level aggregates,
-- joined only after each is complete. delivery_item and delivery_review never
-- appear in the same aggregate: a review is one row per delivery, so averaging it
-- beside item lines would weight the rating by item count.
WITH scoped_donation AS (
  -- Branch attribution happens once, before any spoilage aggregation. The arms
  -- are disjoint on pickup_route_id, so each donation is attributed exactly once.
  -- A. routed: the pickup route's managing branch.
  SELECT d.donation_id, r.managing_branch_id AS branch_id
    FROM donation d
    JOIN route  r ON r.route_id = d.pickup_route_id
    JOIN branch b ON b.branch_id = r.managing_branch_id
   WHERE d.pickup_route_id IS NOT NULL
     AND b.regional_manager_user_id = :me
     AND d.donation_status <> 'CANCELLED'
  UNION ALL
  -- B. unrouted but branch-anchored: the donor's primary branch. A donor with
  -- no primary_branch_id is in neither arm and stays operator-only.
  SELECT d.donation_id, u.primary_branch_id AS branch_id
    FROM donation  d
    JOIN app_user u ON u.user_id = d.donor_user_id
    JOIN branch   b ON b.branch_id = u.primary_branch_id
   WHERE d.pickup_route_id IS NULL
     AND u.primary_branch_id IS NOT NULL
     AND b.regional_manager_user_id = :me
     AND d.donation_status <> 'CANCELLED'
),
delivery_lines AS (
  SELECT dl.delivery_id, dl.route_id,
         SUM(di.quantity_delivered_kg) AS delivery_kg
    FROM delivery dl
    JOIN delivery_item di ON di.delivery_id = dl.delivery_id
   WHERE dl.delivery_status = 'DELIVERED'
   GROUP BY dl.delivery_id, dl.route_id
),
delivery_agg AS (
  SELECT r.managing_branch_id AS branch_id,
         COUNT(*)             AS delivered_deliveries,
         SUM(dl.delivery_kg)  AS delivered_kg
    FROM delivery_lines dl
    JOIN route r ON r.route_id = dl.route_id
   GROUP BY r.managing_branch_id
),
review_agg AS (
  -- one row per reviewed delivery: delivery_review.delivery_id is UNIQUE
  SELECT r.managing_branch_id AS branch_id,
         COUNT(*)             AS reviews,
         AVG(dr.rating)       AS avg_rating
    FROM delivery dl
    JOIN delivery_review dr ON dr.delivery_id = dl.delivery_id
    JOIN route           r  ON r.route_id = dl.route_id
   WHERE dl.delivery_status = 'DELIVERED'
   GROUP BY r.managing_branch_id
),
spoiled_agg AS (
  -- Each spoilage row maps to exactly one donation_item (food_item_id is its PK
  -- and FK), so this join cannot fan out. Attribute the donation to a branch
  -- first, then aggregate; an inner join through route here was the bug that
  -- dropped branch-anchored unrouted spoilage. delivery_item and delivery_review
  -- never appear in this aggregate.
  SELECT sd.branch_id,
         SUM(sr.quantity_spoiled_kg) AS spoiled_kg
    FROM scoped_donation sd
    JOIN donation_item   i  ON i.donation_id  = sd.donation_id
    JOIN spoilage_record sr ON sr.food_item_id = i.food_item_id
   GROUP BY sd.branch_id
)
SELECT b.branch_id, b.branch_name,
       COALESCE(da.delivered_deliveries, 0) AS delivered_deliveries,
       COALESCE(da.delivered_kg, 0)         AS delivered_kg,
       COALESCE(ra.reviews, 0)              AS reviews,
       ROUND(ra.avg_rating, 2)              AS avg_rating,
       COALESCE(sa.spoiled_kg, 0)           AS spoiled_kg
  FROM branch b
  LEFT JOIN delivery_agg da ON da.branch_id = b.branch_id
  LEFT JOIN review_agg   ra ON ra.branch_id = b.branch_id
  LEFT JOIN spoiled_agg  sa ON sa.branch_id = b.branch_id
 WHERE b.regional_manager_user_id = :me
 ORDER BY b.branch_name;
-- delivered_kg is summed per delivery line and then per branch; reviews and
-- avg_rating come from the per-delivery aggregate untouched. Branch A with two
-- deliveries rated 2 and 5, with 1 and 4 item lines, reports avg_rating = 3.50
-- (not 4.40). spoiled_kg is attributed through routed and branch-anchored
-- unrouted donations, so a spoilage row entered before routing is still counted.
```

All of the rules above — grouping-key-only filtering, no sibling fan-out, one row
per reviewed delivery, and the scoped-donation relation — are enforced by seeded
tests that compare each API figure with a hand-written SQL total, on a dataset
built to break a naive query:

1. **Two-branch donor.** A donor with donations routed through two different
   branches (reachable after an operator reassigns the donor's `primary_branch_id`,
   since a donor's own route choice is branch-confined at creation); a manager's
   donor total must exclude the other branch's kilograms, which a filtered
   `vw_donor_impact` would silently include.
2. **Scoped-donation relation (routed ∪ branch-anchored unrouted).** Manager A
   manages Branch A; Donor A belongs to Branch A and has an unrouted donation of a
   known quantity (plus, optionally, a routed one via a Branch A route). Assert:
   (a) Manager A sees the unrouted donation in the queue `GET /api/donations`;
   (b) the donor report lists Donor A and includes the unrouted donation's
   `total_donated_kg` and its full `balance_kg` before routing; (c) the routed and
   unrouted quantities sum exactly once (no double count); (d) Manager B, who
   manages Branch B only, sees neither the queue row nor the donor report row;
   (e) a donor with `primary_branch_id IS NULL` is absent from both managers'
   reports and appears only through the operator queue (`API_CONTRACT.md` §3.2).
3. **Branch average rating is unweighted by item count.** Branch A has two
   `DELIVERED` deliveries with reviews `rating = 2` and `rating = 5`, and with 1
   and 4 `delivery_item` lines respectively. Assert `reviews = 2`,
   `delivered_deliveries = 2`, `delivered_kg` equals the sum of all five line
   quantities, and `avg_rating = 3.50` — the arithmetic mean of the two review
   rows — **not** `(2×1 + 5×4)/5 = 4.40`, the item-weighted figure a single
   `delivery_item` × `delivery_review` join produces.
4. **Unrouted branch-anchored spoilage is counted exactly once.** Manager A
   manages Branch A; Manager B manages Branch B. Donor A is anchored to Branch A
   and has an unrouted donation (`pickup_route_id IS NULL`) with a known item. A
   `spoilage_record` of 2.00 kg is seeded before any route exists (fixture-level
   insert; this test targets the report query, so it does not depend on the routing
   lifecycle). Apply the route assignment in (c) as a fixture update as well, so
   the test isolates report attribution from the routing lifecycle; the API
   routing rules themselves are covered by the tests in `API_CONTRACT.md` §3.2.
   Assert: (a) Branch A's `spoiled_kg` is 2.00 and no other branch
   includes it; (b) Manager B's report excludes it; (c) after assigning the
   donation to a Branch A route, Branch A still reports 2.00 — the row moves from
   arm B to arm A and is not double counted; (d) a donor with
   `primary_branch_id IS NULL` contributes to neither manager's `spoiled_kg`.
   Keep this figure separate from `delivery_item` and `delivery_review`: the
   spoilage aggregate must never share a query arm with either.

## 3. Relationships the application depends on

```
organization 1─n branch 1─n route 1─n delivery
                             │            ├─n delivery_item ─n─ donation_item
                             │            └─1 delivery_review
branch 1─n app_user (primary_branch_id)  ·  branch.regional_manager_user_id → app_user
app_user 1─n donation (donor_user_id)  ·  app_user 1─n inspection_log (inspector)
app_user 1─1 user_credential  ·  app_user 1─n dependent  ·  app_user n─n route (route_assignment)
donation 1─n donation_item 1─n spoilage_record  ·  donation 1─n donation_status_history
donation 1─n inspection_log  ·  donation 1─n delivery
```

Consequences the UI/API must handle:

- A route can only be created for an existing `DRIVER` — `designated_driver_user_id`
  is `NOT NULL`, so the "new route" form needs a driver already provisioned.
- A delivery needs `donation_id`, `route_id`, `recipient_branch_id`; all three are
  mandatory FKs. Its driver is optional in the table but always resolvable from the
  route, so the API defaults it rather than storing `NULL`.
- **Manager scope is one column, not two.** Every manager-facing query filters
  `branch.regional_manager_user_id = :me` — the CTEs and aggregates in §2.1 already
  do, and they are the canonical form. `app_user.primary_branch_id` is **not** a
  manager scope anchor: it locates a donor's unrouted donations and an
  inspector's jurisdiction. A manager whose `regional_manager_user_id` matches no
  branch therefore reads no branch-scoped row at all — lists empty, aggregates
  empty/zero, details 404 — rather than falling back to `primary_branch_id`, and
  the column is outside `sfc_app`'s UPDATE privileges, so the app could not widen
  its own scope even if a code path tried. The donor report's `scoped` relation in
  §2.1 is the same two-arm union, so an unrouted branch-anchored donation appears
  in the manager's queue **and** in the donor report's donated/balance figures
  before routing.
- **A donor may only name a route of their own branch.** `donation.pickup_route_id`
  is set at creation by the donor (`INSERT`) or reassigned by a manager
  (`UPDATE`). The schema's FK proves only that the route exists, so the service
  additionally requires `route.managing_branch_id = donor.primary_branch_id`,
  `route_status = 'ACTIVE'` and type `PICKUP`/`MIXED`, and requires the route to be
  omitted when the donor's `primary_branch_id` is `NULL`
  (`API_CONTRACT.md` §3). Without that check a donor could place a donation into
  another manager's branch scope by naming that branch's route.
- A donation with no `pickup_route_id` (nullable) has no branch. It is visible to
  inspectors, and to managers **only** through the donor's `primary_branch_id`
  (`API_CONTRACT.md` §3.2). When the donor has no `primary_branch_id`
  there is no branch anchor and therefore no manager scope at all: every manager
  gets 404, and the row appears for managers only in the operator-authorised
  read-only CLI queue (`flask queue unrouted --orphans`) until the operator sets
  the donor's `primary_branch_id`. Routing then uses
  `PATCH /api/donations/{id}/route`, so the donation is never invisible to the
  system and never visible to the wrong branch. Because creation already confines
  a donor-chosen route to their own branch, an unrouted donation is never a way
  around that check.
- **Inspection decisions are per-row; delivery eligibility is per-latest-row.** The
  triggers read the newest inspection with `ORDER BY inspected_at DESC,
  inspection_id DESC`; the queue must use the same predicate, or a donation with an
  old PASSED row and a newer FAILED row would sit in one view and not the other.
  The second key is load-bearing: `inspected_at` is `DATETIME` at second precision
  and `NOW()` has no fractional part, so two inspections may share a timestamp.
  The database's own ordering is still deterministic because `inspection_id` is
  auto-increment, and no query may sort on `inspected_at` alone.
- **`inspected_at` and `reported_at` have no default**, so the service must supply
  them — from the database clock, in the inserting statement — and read the stored
  value back. Neither is a request field; a client-supplied value would let a
  future timestamp outrank real inspections, and spoilage could be backdated to
  hide a loss.
- **Delivery status is current state, not history.** `delivery` has one row per
  delivery and no event table; `donation_status_history` covers donations only.
- **Distribution is quantity-based.** `delivery.delivery_status = 'DELIVERED'` plus
  `delivery_item.quantity_delivered_kg` is the only source of "delivered";
  allocation alone changes nothing (gap **G12** is about history, not quantity).

## 4. Constraints and triggers — who owns which rule

| Rule | Enforced by | Application behaviour |
|---|---|---|
| Donation belongs to a `DONOR` | `trg_donation_*` | 422 `donor_role_invalid` (never reachable from the UI) |
| Donor-selected pickup route ∈ donor's `primary_branch_id`, `ACTIVE`, type `PICKUP`/`MIXED` | **service only** — the schema enforces just the FK to `route` | 422 `invalid_reference` (`route_not_selectable`) for a missing/inactive/wrong-type/other-branch route; 422 `validation_error` (`donor_branch_required`) when the donor has no `primary_branch_id`; no row written. Covers a hole no trigger closes. |
| Inspection author is a `SAFETY_INSPECTOR` | `trg_inspector_*` | 403 `forbidden_role` at the role gate first |
| Route driver and delivery driver hold `DRIVER` | `trg_route_*`, `trg_delivery_*` | 422 `driver_not_eligible` (validation of a referenced entity), checked before the write |
| Delivery IN_TRANSIT/DELIVERED needs latest inspection PASSED | `trg_delivery_*` (inspection gate) | 409 `inspection_required`; the service checks first for a good message, the DB remains the guarantee |
| Delivery IN_TRANSIT needs an attributed driver | `trg_delivery_driver_*` | 409 `driver_required` |
| Attribution immutable once DELIVERED | `trg_delivery_driver_update` | no "edit driver" affordance after departure; 409 `attribution_immutable` |
| Re-parent / shrink guard on items | `trg_donation_item_update_guard` | lock item row, 409 `item_has_allocations` / `below_allocated` |
| Allocation ≤ donated − spoiled | `trg_delivery_item_*`, `trg_spoilage_*` | 409 `allocation_exceeds_available` carrying the remaining kg. The sum includes `PLANNED`, `IN_TRANSIT`, `FAILED` and `DELIVERED` lines; see the status-blind limitation below. |
| Allocation cap is status-blind | **no database rule** — the four cap triggers sum every `delivery_item` row for the item and never join `delivery` | a status-only cancellation releases nothing. Step 7 releases a `PLANNED` cancellation by deleting its lines in the same transaction; `IN_TRANSIT`/`FAILED` lines are never deleted. Failed-delivery recovery needs **G15**. |
| Delivery status transition legality | **service only** — the ENUM stores all five values and no trigger constrains the sequence | `FAILED → CANCELLED` is refused by the service in Step 7 (409 `invalid_transition`) even though a bare `UPDATE` would succeed. |
| History append-only | `trg_dsh_block_update/delete` | the API exposes no edit/delete for history at all; 409 `immutable_record` if ever reached |
| Review author = receiving branch manager | `trg_review_manager_*` | 403 `reviewer_not_authorized` before attempting; 409 `duplicate_review` on the second |
| Temperature plausibility | `chk_temperature_range` | 422 `temperature_implausible` (−50…150 inclusive, NULL allowed) |
| Quantities positive | `chk_donation_quantity`, `chk_delivery_quantity`, `chk_spoilage_quantity` | Pydantic `gt=0` with `Decimal`, 422 before SQL |
| Food dates consistent | `chk_food_dates` | 422 `best_before_must_follow_prepared_at` |
| Token pairing / lock consistency | `chk_cred_token_pairing`, `chk_cred_lock_consistency` | the service never writes half a pair; 500 if it ever does |
| Review rating 1–5 | `chk_review_rating` | Pydantic `ge=1, le=5` |
| Route hours 0 < h ≤ 168 | `chk_route_hours` | Pydantic bound |

Raw trigger text never reaches the client: the service matches the message against
the fixed table in `API_CONTRACT.md` §1.1 and returns a stable code, sanitising
anything unrecognised to `409 business_rule_violation`.

**Column-level writes mirror the API, not just the table.** The triggers above
govern *rows*; the writable *columns* are narrower and are enforced by
column-level `UPDATE` grants (`AUTH_SECURITY_DESIGN.md` §6.2). The set is exactly
`branch(branch_name, address, pincode, contact_no)`,
`app_user(account_status)`,
`user_credential(password_hash, must_change_password, failed_attempts, locked_until,
last_login_at, password_changed_at, reset_token_hash, reset_expires_at)`,
`route(designated_driver_user_id, coverage_area_id, route_type, route_status)`,
`donation(pickup_route_id, pickup_address, pickup_pincode, pickup_contact,
donation_status)`,
`donation_item(item_name, quantity_kg, best_before, donation_id)`,
`dependent(full_name, relationship, date_of_birth, phone)`,
`delivery(driver_user_id, scheduled_for, delivery_status, delivered_at)` and
`delivery_item(quantity_delivered_kg)`. Identity/ownership columns
(`donor_user_id`, `user_role`, `primary_branch_id`, `regional_manager_user_id`,
`managing_branch_id`, a delivery's `donation_id`/`route_id`/`recipient_branch_id`,
`dependent`'s composite key, `donation_item.food_item_id`/`category_id`) are
outside every grant, so a mistaken UPDATE fails with 1142 instead of silently
re-attributing a row.

**Status transition legality is *not* in the database.** The service owns it for
donations (`ROLE_PERMISSION_MATRIX.md` §3.1) and for deliveries: the delivery ENUM
accepts all five values and no trigger constrains the sequence, so a bare
`UPDATE delivery SET delivery_status = 'CANCELLED'` would succeed from `FAILED` or
even `DELIVERED`. That is precisely why the service must reject
`FAILED → CANCELLED` until G15 exists. Donation changes are recorded in
`donation_status_history`; delivery changes have no history table (G12).

## 5. Identified schema gaps → proposed future migrations

None of these is implemented in Step 7. Each requires its own reviewed migration
file under `database/prep_phase1/` conventions and a Phase-2-style runner run.

| # | Gap | Why it hurts | Proposed migration (future) |
|---|---|---|---|
| G1 | `donation` has no `created_at` | cannot order a donor feed by "recently created", only by `pickup_datetime`; creation analytics impossible | `008_donation_created_at.sql` — nullable, backfilled from `pickup_datetime` with a documented note |
| G2 | Lockout does not escalate (15 → 30 → 60 needs a counter the schema lacks) | v1 must use a fixed 15-minute lock | `009_credential_lock_state.sql` — `lock_stage TINYINT UNSIGNED NOT NULL DEFAULT 0` |
| G3 | No session or auth-event table | logout everywhere, login audit and per-device sessions are limited to the cookie's own expiry; the idle timeout is per cookie copy | `010_auth_event.sql` (append-only, `user_id`, `event`, `ip_hash`, `at`) + session table |
| G4 | No notification table | "notifications" are derived from history/deliveries, no read/unread state | `011_notification.sql` |
| G5 | No driver-correction record | attribution is frozen after DELIVERED with no auditable repair path | `012_delivery_driver_correction.sql` (as already specified in the 004b notes) |
| G6 | `inspection_log` has no UPDATE grant and no correction path | a mistyped reading is permanent | `013_inspection_correction.sql` (who/when/why + supersedes) |
| G7 | No recipient/household allocation table | "recipient management" is limited to a driver's `dependent` rows | `014_beneficiary_distribution.sql` |
| G8 | `vw_donor_sustainability`, `vw_driver_performance` are `DEFINER=root` | accidental privilege escalation and a bypass of column-level intent | `015_views_invoker.sql` (replace with INVOKER) |
| G9 | `donation_item` cannot be deleted (no DELETE grant, FK RESTRICT) | a mistyped item lives forever | decide: soft-delete flag or an explicit void workflow |
| G10 | No index for `delivery(donation_id, delivery_status)` or `inspection_log(donation_id, inspected_at DESC)` | the inspection gate and delivery lists scan | `016_perf_indexes.sql` (add only after `EXPLAIN` on the load-test dataset) |
| G11 | No index for `donation(donor_user_id, donation_status, pickup_datetime)` | donor feed sort at 50k rows | same migration as G10, measured first |
| G12 | **No delivery-status history table** | a delivery's past statuses, the actor of a change and any reason are unrecoverable; v1 therefore accepts no note and shows no delivery timeline | `017_delivery_status_event.sql` (`delivery_id`, `from_status`, `to_status`, `actor_user_id`, `changed_at`, `note`) + service writes in the same transaction |
| G13 | **No donation close-out** | a donation whose surplus will never be delivered cannot be formally closed; `COMPLETED` requires the balance to be zero, and `spoilage_record.reason` describes food loss, not a logistics decision. Such donations stay `PARTIALLY_DISTRIBUTED` forever | `018_donation_closeout.sql` (`closed_at`, `close_reason ENUM('EXPIRED','CANCELLED_REMAINDER','NO_RECIPIENT','OTHER')`, `closed_by_user_id`, `close_note`) + one transition, with the balance preserved as an explicit figure |
| G14 | **Credential version is second-granularity** | `password_changed_at DATETIME` (0 fractional digits) cannot distinguish two writes in one second; v1 compensates with a strictly increasing write (see `AUTH_SECURITY_DESIGN.md` §2.2) which can lead the wall clock by <1 s per rapid change | `019_credential_epoch.sql` — `session_epoch BIGINT UNSIGNED NOT NULL DEFAULT 0`, incremented atomically on every credential write, plus `password_changed_at DATETIME(6)` |
| G15 | **Allocation cap is status-blind** | the four cap triggers sum every `delivery_item` row for the item without joining `delivery`, so `FAILED`/`CANCELLED` lines keep consuming capacity. Deleting a `FAILED` delivery's lines is the only current release and destroys the record of the attempt, so failed-delivery recovery and reallocation cannot be implemented safely. | `020_status_aware_allocation_cap.sql` (database) — recreate `trg_delivery_item_insert/update` and `trg_spoilage_quantity_insert/update` to sum only lines whose `delivery.delivery_status <> 'CANCELLED'` (keep `FAILED` held until the manager cancels). The same release adds the service-owned `FAILED → CANCELLED` transition for `NGO_MANAGER`, performing cancellation and loss spoilage in one transaction. No column changes. After it lands, `PLANNED` cancellation no longer needs to delete lines. |

Because of G12 the API deliberately has **no** delivery transition note and no
`GET /api/deliveries/{id}/history`. Because of G13 the API cannot offer a "close
out the remainder" button, and the UI shows the balance instead of pretending the
donation finished. Donation history is unaffected: it exists, with a `note` column
and append-only guards.

`sfc_app` can neither read nor write `schema_migrations` — resolved in
`AUTH_SECURITY_DESIGN.md` §6.2 without a schema change (no database-wide grant at
all; `SELECT` on it fails with 1142 like any other missing privilege).
