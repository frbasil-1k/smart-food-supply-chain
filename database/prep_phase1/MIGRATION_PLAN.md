# PHASE 1 — MIGRATION PLAN (REVISED)

**Status: PREPARATION ONLY.** Nothing in this document has been executed and no
database was contacted. Companion files: `README.md` (usage, backup/restore),
`RUNNER_DESIGN.md` (Phase 2 runner + recovery), `TEST_MATRIX.md`,
`REVISION_REPORT.md`, `rollback/`, `validation/`, `proposed/`. All drafts are
marked **UNEXECUTED**.

---

## 1. Current state (verified from files and the live audit report)

| Item | Verified value | Source |
|---|---|---|
| Server | MySQL 8.0.46, InnoDB, utf8mb4 / utf8mb4_0900_ai_ci | `audit-report.txt` B.1 |
| Tables | 15 · 86 columns · 40 indexes (incl. 15 primary keys) | B.3 |
| Views | 2 (`vw_donor_sustainability`, `vw_driver_performance`), both `DEFINER=root@localhost` | B.4 + export |
| Triggers | 16 on 8 tables | B.4 |
| CHECK constraints | 6, all `ENFORCED=YES` | B.3 |
| Foreign keys | 25, all `RESTRICT` / `NO ACTION` | B.3 |
| Rows | **104** (COUNT(*), matches Workbench) | B.2 |
| Schema parity | live == `database/schema.sql`, 0 failures | B.3 |
| Invariants | 7/7 pass, exit code 0 | B.6 / SUMMARY |

**Rows that the migrations interact with**

```
organization 3   branch 5   app_user 15   route 5   coverage_area 5
route_assignment 8   donation 5   food_category 8   donation_item 13
inspection_log 5   dependent 6   delivery 5   delivery_item 15
spoilage_record 1   delivery_review 5
```

- 5 donations: **4 COMPLETED, 1 APPROVED** → 5 reconstructed snapshots; nothing
  is CANCELLED, so the view's exclusion is a guarantee, not a visible change.
- 5 deliveries, **all DELIVERED**, all with `driver_user_id` absent → 5 NULLs.
- 5 inspections, all PASSED, `temperature_c` inside the band → 006 can validate.
- 15 users: 5 DRIVER, 4 DONOR, 3 NGO_MANAGER, 3 SAFETY_INSPECTOR, all ACTIVE;
  8 route assignments = 5 drivers + 3 inspectors.

### Findings that shaped the design

1. **No migration infrastructure and no git repository.** No `database/migrations/`,
   no runner, no ledger, no version control. `git init` before applying anything is
   step 2 of the checklist (§9).
2. **`donation.pickup_datetime` is `NOT NULL`** — it is always present and always
   ambiguous, so it is never treated as creation time.
3. **`delivery_item` has `UNIQUE(delivery_id, food_item_id)`** — per delivery, not
   per donation+branch. Repeated branch deliveries are already legal; F4 adds no
   unique key.
4. **`vw_donor_sustainability.total_distributed_kg` sums every `delivery_item`
   row regardless of `delivery_status`.** PLANNED/IN_TRANSIT/FAILED/CANCELLED
   allocations all read as "distributed" — the defect `vw_donor_impact` corrects.
5. **`vw_driver_performance` attributes deliveries via
   `route.designated_driver_user_id`.** It credits the current designated driver
   for past work; it stays as the clearly labelled route-based metric.
6. **Both existing views are `DEFINER=root@localhost`.** A pre-existing privilege
   escalation (whoever may SELECT the view reads as root). Not changed here; the
   new view uses INVOKER instead (open question 10).
7. `database/audit_db.py` hard-codes the baseline path and truncates delivered
   kilograms with `CAST(... AS SIGNED)`; both fixes are in `proposed/`.
8. `audit-report.txt` and `database/__pycache__/` are untracked artefacts: rename
   the report by date, ignore the cache.

---

## 2. Migration architecture and order

| # | Migration | Objects | Depends on | Reversible |
|---|---|---|---|---|
| 000 | preflight | read-only checks | — | n/a |
| 001 | `user_credential` | table + FK + unique + 2 CHECKs | none | drop table (loses hashes) |
| 002a | `donation_status_history` | table + 2 FKs + 3 CHECKs + generated column + 2 append-only triggers | none | drop table (loses history) |
| 002b | legacy snapshots | `INSERT ... SELECT` (DML only) | 002a | re-run safe |
| 003 | donation pickup | 3 nullable columns | none | drop columns (loses data) |
| 004a | delivery attribution | 2 nullable columns, 2 indexes, 1 FK | none | drop (loses data) |
| 004b | delivery driver guards | 2 triggers | 004a | drop triggers — full |
| 005 | item update guard | 1 trigger (2 rules) | none | drop trigger — full |
| 006 | temperature CHECK | 1 constraint | none | drop check — full |
| 007 | `vw_donor_impact` | 1 view (`SQL SECURITY INVOKER`) | none | drop view — full |

**Why the two splits**

- 002a/002b: MySQL DDL commits independently. One file doing `CREATE TABLE` then
  `INSERT` cannot be re-run if the insert fails — the table exists, `CREATE`
  fails with 1050, and the batch is stuck. Split, the DDL is atomic on its own and
  the backfill is a repeatable DML statement.
- 004a/004b: the trigger body is the most likely thing to fail on first
  execution. Split, a failure is a `CREATE TRIGGER` that did not happen, not a
  partly-applied `ALTER TABLE`.

Everything from 001 to 006 is independent at SQL level; the order is by risk —
additive structure first, behavioural objects (triggers, CHECK) next, the
reporting view last because its numbers are reviewed before anyone relies on it.

---

## 3. Specifications

### 001 — USER_CREDENTIAL (11 columns)
PK/FK `user_id` → `app_user` (`ON DELETE CASCADE`), `password_hash`,
`must_change_password`, `failed_attempts`, `locked_until`, `last_login_at`,
`password_changed_at`, `reset_token_hash` (SHA-256 hex, UNIQUE, many NULLs),
`reset_expires_at`, `created_at`, `updated_at`.

- **v1 algorithm is Werkzeug scrypt** (`scrypt:32768:8:1$…`). That is the only
  algorithm the backend issues and the only one the audit accepts
  (`cred_non_scrypt_hash` must stay 0). Argon2 is **not** supported by either in
  v1 and is not claimed anywhere in this package.
- No `CHECK` on the hash format: policy, not structure; the audit enforces it.
- Two CHECKs: `chk_cred_lock_consistency` (a lock must have been earned) and
  `chk_cred_token_pairing` (`reset_token_hash` NULL exactly when
  `reset_expires_at` is NULL, so a half-written reset is unstorable).
- Reset tokens stay **inside** this table (approved decision): one row shape
  instead of a third table, revocable, no server-side signing secret.
- **No credentials are created for the 15 existing users.** A manager issues a
  single-use activation token; the user sets their own password. Until then,
  login fails with the same generic message as a wrong password.
- Lockout: 5 failures → 15 minutes, doubling 15 → 30 → 60; success clears counters
  and lock together; per-IP throttling runs alongside so lockout cannot be used to
  deny service to everyone.

### 002a — DONATION_STATUS_HISTORY (structure + append-only)
Append-only ENUM history; nullable `changed_at`; `is_reconstructed`; `note`.

- `reconstructed_donation_id INT GENERATED ALWAYS AS (IF(is_reconstructed=1,
  donation_id, NULL)) STORED` + `UNIQUE` on it = **at most one reconstructed
  snapshot per donation**, structurally. Genuine rows are all NULL, so any number
  of real transitions remains legal.
- Three CHECKs: time semantics (`reconstructed ⇔ no timestamp`), no
  self-transition, no actor on a reconstructed row.
- **Append-only is enforced, not asserted**: `trg_dsh_block_update` and
  `trg_dsh_block_delete` raise 45000 on any UPDATE/DELETE. The grant layer is the
  second defence and is expressed the only way MySQL allows: the app account gets
  database-wide `SELECT, INSERT` and per-table `UPDATE, DELETE` on the tables it
  actually changes, with this table in neither list (RUNNER_DESIGN §5b). A
  database-wide grant cannot be narrowed afterwards by a table-level `REVOKE`
  (§5c). `TRUNCATE` bypasses row triggers, so the app account must not hold
  `DROP`; that limit is documented, and the audit detects an emptied history table.
- UI wording for a reconstructed row is exactly: *"State observed when history
  tracking began; earlier transitions were not recorded."* No `applied_at`
  timestamp is shown, because none is stored.

### 002b — legacy snapshots
`INSERT ... SELECT ... LEFT JOIN ... WHERE h.history_id IS NULL`: one row per
donation, `from_status NULL`, `to_status` = current, `changed_at NULL`, actor
NULL, fixed note. 5 rows expected. Repeatable by the `LEFT JOIN`, backed by the
unique key, atomic as one statement. Recovery cases A–E are written out in the file.

### 003 — DONATION pickup
`pickup_address VARCHAR(255)`, `pickup_pincode VARCHAR(10)`,
`pickup_contact VARCHAR(15)`, all NULL, no defaults, no backfill (5/5/5).
PIN/contact formats are validated in the **backend** (approved): `^[1-9][0-9]{5}$`
after stripping spaces; `+91` + 10 digits starting 6–9. No DB CHECK (addresses are
not uniform, and a wrong CHECK needs a live ALTER); no index (no approved query
uses these columns). `pickup_datetime` is never used as creation time.

### 004a — delivery attribution
`driver_user_id INT NULL` FK → `app_user`; `scheduled_for DATETIME NULL`;
`idx_delivery_driver_status (driver_user_id, delivery_status)`;
`idx_delivery_scheduled (scheduled_for)`. No unique on
`(donation_id, recipient_branch_id)`; no CHECK on the FK (NULL is meaningful).
All 5 legacy rows stay NULL in both columns.

### 004b — delivery driver guards (corrected in R3)
| Rule | Insert | Update |
|---|---|---|
| Driver must hold `DRIVER` role | if set | **only when newly set or changed** |
| Attribution immutable | — | once `OLD.delivery_status = 'DELIVERED'` |
| `IN_TRANSIT` requires a driver | yes | yes |

- Unrelated updates on a legacy DELIVERED row are allowed: the NULL-safe
  comparison `NEW.driver_user_id <=> OLD.driver_user_id` is true, so neither
  immutability nor the role check fires. A driver who leaves the role keeps valid
  history, and history is never re-validated against a present-day role.
- Account status is not checked here: it changes over time, and a DB gate would
  make a suspended driver's rows un-repairable. The service rejects non-ACTIVE
  assignments with 422.
- Between `IN_TRANSIT` and `DELIVERED` the database still permits a change,
  because no correction workflow exists and an operational swap must not become
  impossible; the service requires the same driver on the transition (test F4-11b).
- **No correction workflow** is built: there is no attribution-history table to
  record actor, time and reason, and F6 is deferred. The file specifies the future
  auditable design (`delivery_driver_correction` + a scoped trigger) instead of
  permitting silent edits.

### 005 — DONATION_ITEM update guard (extended in R6)
One `BEFORE UPDATE`, two rules:
1. **Re-parenting**: if `donation_id` changes and any `delivery_item` or
   `spoilage_record` row references the item → 45000. Re-parenting an
   unallocated item remains legal (nothing can be corrupted, and data-entry
   correction must stay possible).
2. **Quantity reduction**: two scalar subqueries (not joins — no fan-out), compare
   against delivered + spoiled, `SIGNAL` if below. `DECIMAL(20,2)` locals because
   `SUM()` widens `DECIMAL(8,2)` and a narrow local raises 1264.

Concurrency: every consuming path takes `SELECT … FOR UPDATE` on the
`donation_item` row **first**, before reading children — a locking read is a
current read, so a long transaction cannot act on a stale REPEATABLE READ
snapshot; the three paths serialise on one row in one order. The trigger is the
backstop for anything that bypasses the protocol. The API must also reject
re-parenting with `409 item_has_allocations`.

### 006 — temperature plausibility
`CHECK (temperature_c IS NULL OR (temperature_c BETWEEN -50 AND 150))`, inclusive,
NULL legal. Instrument plausibility, not food safety: `safety_status` remains the
decision, and passing the band must never render as a "safe" badge.
`ALTER … ADD CHECK` validates existing rows and fails atomically (3819).

### 007 — vw_donor_impact (review-gated)
New view; `vw_donor_sustainability` and `vw_driver_performance` preserved
unchanged. **`SQL SECURITY INVOKER`** (R12): no definer account, no hidden
escalation, no dependency on root. CANCELLED excluded from all three aggregates;
delivered counts only `DELIVERED`; spoiled is its own column;
`undistributed_balance_kg` is an **accounting balance**, never stock. Pre-aggregated
subqueries prevent fan-out. No extra grant is needed: the app's database-wide
`SELECT` covers the view and its base tables (RUNNER_DESIGN §5b).

---

## 4. Key decisions and why

| Decision | Alternative rejected | Reason |
|---|---|---|
| Split 002 and 004 | one file each | MySQL DDL commits independently; one failure strands the batch |
| Generated column + UNIQUE for "one snapshot" | service rule / NOT EXISTS only | makes the guarantee structural and the backfill naturally idempotent |
| Append-only via triggers | grants only | a grant mistake is silent; a trigger fails loudly. Both are used |
| Role validated only on change | every update | otherwise a legitimate role change freezes a driver's own history |
| Immutable from `DELIVERED`, not `IN_TRANSIT` | freeze at assignment | no correction workflow exists yet; a mid-trip swap must remain possible, service-restricted |
| Re-parent blocked in the trigger | service-only | the FK cannot see it and the audit only detects it afterwards |
| `FOR UPDATE` before child reads | plain SELECT | REPEATABLE READ snapshot can be stale; a locking read is current |
| `SQL SECURITY INVOKER` view | `DEFINER=root` like the old ones | no accidental privilege escalation; app already holds the base SELECTs |
| No `CHECK` on hash/pincode format | schema regex | policy, not law; both are one-way doors on a live table |
| No unique on (donation, branch) | unique key | duplicate branch deliveries are approved |

---

## 5. Historical data strategy

| Object | Legacy state | Guard |
|---|---|---|
| `user_credential` | no rows; nobody can log in until invited | audit `cred_users_missing` |
| `donation_status_history` | 1 snapshot/donation, `changed_at NULL`, actor NULL | `chk_dsh_time_semantics`, `uq_dsh_one_reconstructed` |
| `donation.pickup_*` | NULL ×5 → "Not recorded" | fingerprint assertion; API requires values for new rows |
| `delivery.driver_user_id` | NULL ×5, never inferred from routes | `driver_legacy_null`; confirmed/unconfirmed split |
| `delivery.scheduled_for` | NULL ×5, never derived | fingerprint assertion |
| 15 original tables | 104 rows byte-identical | `CONTENT_FINGERPRINT.sql` before/after |

No migration writes to any original table's values. `donation` and `delivery` gain
columns only; `inspection_log` gains a constraint only.

---

## 6. Rollback limitations

No migration here is transactional. `rollback/ROLLBACK_ALL.sql` runs in reverse
(007 → 001) as compensating DDL. 005/006/007 are fully reversible; 004b and 002a's
triggers are free to remove; 001/002a/003/004a destroy data created after go-live.
A failed partial batch is **not** fixed by running the rollback from the top — use
the per-version recovery path in RUNNER_DESIGN §4. Restoring the pre-batch dump is
the only true global undo and discards everything written since the backup.

---

## 7. Audit integration (R7, R8)

`database/audit_db.py` is **not modified**. Its proposed change is isolated in
`proposed/` as two ordered patches plus a ready candidate file.

**Baseline workflow.** B.3 compares live to `database/schema.sql`. After the batch
the live schema legitimately has 1 table, 5 columns, 4 triggers, 1 CHECK, 3 indexes
and 1 view more. So:

- before the batch: `audit_db.py` → exit 0 (as today);
- during: per-migration `VALIDATION_ALL.sql` blocks only;
- after: `mysqldump --no-data … > database/schema_post_migrations.sql`, then
  `audit_db.py --baseline database/schema_post_migrations.sql` → exit 0.

The frozen export is never rewritten, no check is deleted, and the 39-assertion
self-test still passes (verified against the candidate: `SELF-TEST RESULT: PASS`).

**Checks that activate automatically** (guarded by object existence, print
`skipped` until then): `cred_users_missing`, `cred_non_scrypt_hash`,
`cred_locked_out`, `hist_*` (4), `donation_missing_pickup_address`,
`driver_role_invalid_active`, `driver_legacy_null`,
`driver_confirmed_delivered_kg`, `driver_unconfirmed_delivered_kg`,
`temperature_out_of_range`; `delivery_driver_history` stops being NOT AVAILABLE.

**R7 correction.** Both delivered-kg observations used
`CAST(… AS SIGNED)`, which truncates 1.25 kg to 1. The patch replaces the cast with
`AS DECIMAL(20,2)`; the observation then prints `n=1.25`. Tested by seeding a
fractional `delivery_item` on the dev database (test F4-13b).

**New checks worth adding when the audit is next revised** (read-only, none weakens
an existing check): `history_status_lag` (INVARIANT), `cred_must_change_open`,
`cred_stale_reset_token`, `pickup_pincode_suspect`, `pickup_contact_suspect`,
`delivery_transit_without_driver` (INVARIANT), `delivery_scheduled_before_pickup`,
`donor_impact_reconciles` (INVARIANT), `donor_impact_negative_balance` (INVARIANT),
`dsh_append_only_guards_present` (structural).

Unchanged by instruction: 7 invariants, 10 observations, 7-stage comparison,
semantic trigger/view comparison, gate self-test, donor-impact preview.

---

## 8. Backend / API impact map

| Migration | Endpoints | Behaviour |
|---|---|---|
| 001 | `POST /auth/login`, `/auth/logout`, `/auth/activate`, `/auth/password`, `GET /auth/me`, `POST /users/{id}/credential-invite` | login needs a credential row; generic failure; session + CSRF; lockout; **no response may contain `password_hash` or `reset_token_hash`** |
| 002a/002b | `POST /donations`, `PATCH /donations/{id}/status`, `GET /donations/{id}` | every status write goes through one transactional function (`FOR UPDATE`, UPDATE + INSERT); history is INSERT-only; timeline renders reconstructed nodes with the exact approved sentence; `APPROVED` requires a PASSED inspection |
| 003 | `POST /donations`, `PATCH /donations/{id}`, driver task cards | pickup fields required on create (422); legacy renders "Not recorded" |
| 004a/004b | `POST /deliveries`, `PATCH /deliveries/{id}/driver`, `PATCH /deliveries/{id}/status`, `GET /reports/drivers` | assignment restricted to ACTIVE DRIVERs on the route; `IN_TRANSIT` requires a driver; attribution immutable after DELIVERED (no override endpoint); per-driver totals exclude unattributed rows |
| 005 | `POST /deliveries`, `POST /spoilage`, `PATCH /donation-items/{id}` | 1644 → 409 with the committed total; re-parent → `409 item_has_allocations`; lock the item row first |
| 006 | `POST /inspections` | out-of-band temperature → 422 phrased as plausibility, not safety; boundaries accepted |
| 007 | `GET /reports/donors`, `GET /reports/donors/{id}`, CSV | new numbers from `vw_donor_impact`; old view stays until the switch is reviewed |

Authorization is unchanged by the migrations but newly enforced by them: donor
scope, manager branch scope, driver route scope, inspector branch scope. Role-change
policy P1 remains a service concern; 004b only guarantees the role at write time.

---

## 9. Execution checklist (Deliverable H, revised)

1. **Freeze**: maintenance window; confirm nobody is in Workbench.
2. **Version control**: `git init`, commit the current state, these drafts, and the
   audit report. Migrations without a VCS net are not reviewable.
3. **Audit before**: `python database/audit_db.py --out reports\audit_pre.txt` →
   exit 0, 7/7 invariants, 104 rows.
4. **Fingerprint before**: `validation/CONTENT_FINGERPRINT.sql` → save all 15
   fingerprints and the combined digest.
5. **Backup**: `mysqldump` per README §5, timestamped, outside the repo.
6. **Restore-verify**: restore into `sfc_restore_verify`, audit it (exit 0), and
   fingerprint it (digest identical). Write the marker file.
7. **Preflight**: `000_preflight.sql`; P3/P4/P5 = 0 rows, P8 = 0, P11 = 0, P12 = 0,
   P7 = 104.
8. **Adopt the audit patch** (optional but recommended before the batch):
   apply `proposed/01_baseline_option.patch`, re-run `--self-test` → PASS.
9. **Apply 001** → `V001` → ledger `applied`.
10. **Apply 002a** → `V002a` (structure + 2 triggers + 0 rows) → ledger.
11. **Apply 002b** → `V002b` (5 snapshots, 0 fabricated, 0 duplicates) → ledger.
12. **Apply 003** → `V003` (5/5/5 NULL) → ledger.
13. **Apply 004a** → `V004a` (5/5 NULL, FK, indexes, no forbidden unique) → ledger.
14. **Apply 004b** → `V004b` (2 triggers; dev-only negatives: role-on-change,
    immutability, transit gate) → ledger.
15. **Apply 005** → `V005` (invariant queries 0; dev-only: shrink 1644,
    re-parent 1644, unallocated re-parent OK) → ledger.
16. **Apply 006** → `V006` (ENFORCED, 0 out-of-band, NULL still legal) → ledger.
17. **Review gate**: read `vw_donor_impact` numbers on the restored copy.
18. **Apply 007** → `V007` (INVOKER, both old views present, no negative balance).
19. **Fingerprint after**: identical digest → proves the 104 records did not move.
20. **Audit after**: `--baseline database/schema_post_migrations.sql` → exit 0.
21. **Record**: ledger rows, pre/post audit reports, fingerprint captures,
    validation output, all saved together.
22. **Drop `sfc_restore_verify`** only after acceptance.
23. **No application code in Phase 1.** Phase 2 begins only with authorization.

---

## 10. Open questions

1. **Reset tokens inside `user_credential`** — confirmed as the product decision;
   the pairing CHECK is the only change. Re-confirm the 24-hour expiry.
2. **Lockout numbers** — 5 / 15 min doubling to 60, per-IP throttling alongside.
   Confirm the per-IP threshold (e.g. 20 failures / 10 min / IP).
3. **PIN/contact** — backend-only validation, as approved. No DB CHECK is added;
   say if you want the optional regex CHECK tested on dev.
4. **`scheduled_for`** — included, nullable, no backfill (approved).
5. **Audit baseline** — approve applying `proposed/01_baseline_option.patch` and
   adding `database/schema_post_migrations.sql` after the batch.
6. **Attribution immutability** — frozen from `DELIVERED` only; a future
   `delivery_driver_correction` table is the proposed auditable route.
7. **Item re-parenting** — blocked by trigger when allocations exist; allowed
   otherwise. Confirm that an unallocated item may still be corrected.
8. **Duplicate branch deliveries** — allowed; the UI warns (Open question resolved
   as "warn, do not block" — implemented in Phase 3 UI, not in SQL).
9. **`vw_driver_performance`** — kept as the route-designated metric; the new
   actual-driver report is separate and reports unattributed legacy deliveries
   separately (approved).
10. **Existing views are `DEFINER=root`** — replace with INVOKER in a separate
    reviewed migration, or leave as-is for v1? Leaving them as-is is the smaller
    change but keeps an accidental privilege escalation.
