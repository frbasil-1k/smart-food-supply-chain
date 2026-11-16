# PHASE 1 — TEST MATRIX (REVISED)

**Preparation only.** None of these has been executed against any database.
Negative probes run on `smart_food_supply_chain_dev` only, never on the live
database. Layer key: **SQL** = dev database, **API** = backend integration test,
**AUD** = `database/audit_db.py`, **OPS** = runner/restore procedure.

---

## 1. USER_CREDENTIAL (F1)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| F1-01 | SQL | count after migration | 0 |
| F1-02 | SQL | second credential for same `user_id` | 1062 |
| F1-03 | SQL | credential for `user_id = 999999` | 1452 |
| F1-04 | SQL | hash `'plaintext123'` | accepted by SQL, **flagged by AUD `cred_non_scrypt_hash`** |
| F1-05 | SQL | `locked_until` set with `failed_attempts = 0` | 3819 |
| F1-06 | SQL | token hash with no expiry | 3819 (`chk_cred_token_pairing`) |
| F1-07 | SQL | expiry with no token hash | 3819 |
| F1-08 | SQL | both token fields set, then both cleared | accepted |
| F1-09 | SQL | `DELETE FROM app_user` (dev) | credential row cascades |
| F1-10 | API | login with no credential row | 401 generic, no user enumeration |
| F1-11 | API | 5 wrong passwords then the right one | 401 ×5 then locked; counters set |
| F1-12 | API | correct password during lock | rejected; lock not extended |
| F1-13 | API | login after lock expiry | 200; counters cleared together |
| F1-14 | API | `GET /auth/me`, `GET /users/{id}` | no hash, no token, ever |
| F1-15 | API | invite → activate → reuse token | 200 then 410/401 |
| F1-16 | API | activation with expired token | 410/401, nothing written |
| F1-17 | AUD | `cred_users_missing` / `cred_non_scrypt_hash` / `cred_locked_out` | 15 / 0 / 0 |

## 2. DONATION_STATUS_HISTORY (F2a structure, F2b backfill)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| F2a-01 | SQL | 002a applied to an empty table | 0 rows |
| F2a-02 | SQL | `UPDATE donation_status_history SET note='x'` | **1644** (append-only) |
| F2a-03 | SQL | `DELETE FROM donation_status_history` | **1644** (append-only) |
| F2a-04 | SQL | genuine row with `changed_at = NULL` | 3819 |
| F2a-05 | SQL | reconstructed row with `changed_at` set | 3819 |
| F2a-06 | SQL | reconstructed row with an actor | 3819 |
| F2a-07 | SQL | `from_status = to_status` | 3819 |
| F2a-08 | SQL | two reconstructed rows for one donation | **1062** (`uq_dsh_one_reconstructed`) |
| F2a-09 | SQL | many genuine rows for one donation | all accepted (NULLs exempt from the unique key) |
| F2a-10 | SQL | `to_status` outside the enum | rejected (1265 in strict mode) |
| F2b-01 | SQL | count after 002b | exactly 5 |
| F2b-02 | SQL | donations with no history | 0 |
| F2b-03 | SQL | duplicates per donation | 0 |
| F2b-04 | SQL | **re-run 002b** | 0 rows affected, still 5 |
| F2b-05 | SQL | reconstructed note text | starts with the approved sentence |
| F2b-06 | SQL | `TRUNCATE donation_status_history` as `sfc_app` | denied (no DROP) |
| F2-07 | API | PENDING → SCHEDULED | one row, actor, real timestamp, `is_reconstructed = 0` |
| F2-08 | API | PENDING → COMPLETED | 409, no row written |
| F2-09 | API | `APPROVED` while latest inspection FAILED | 409, no row |
| F2-10 | API | forced history INSERT failure | donation status unchanged (one transaction) |
| F2-11 | API | timeline rendering of a legacy snapshot | hollow node, no time, exact approved sentence |
| F2-12 | AUD | `hist_missing_donation`, `hist_invented_timestamp`, `hist_missing_timestamp`, `hist_duplicate_snapshot` | 0/0/0/0 |
| F2-13 | AUD | proposed `dsh_append_only_guards_present` | 2 triggers present |

## 3. DONATION pickup (F3)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| F3-01 | SQL | after migration | 5/5/5 NULL |
| F3-02 | API | create without `pickup_address` | 422 |
| F3-03 | API | whitespace-only address | 422 |
| F3-04 | API | `"560 001"`, `"98765 43210"` | stored `560001`, `+919876543210` |
| F3-05 | API | `"056001"` / `"56001"` / `"5600011"` / `"56A001"` | 422 each |
| F3-06 | API | contact `"12345"` / `"08012345678"` | 422 |
| F3-07 | API | donor adds details to a legacy donation | 200, NULL replaced, no fabricated history |
| F3-08 | API | driver card for legacy donation | "Pickup address not recorded" |
| F3-09 | AUD | `donation_missing_pickup_address` | 5 |

## 4. DELIVERY attribution (F4a structure, F4b guards)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| F4a-01 | SQL | legacy rows | 5 NULL driver, 5 NULL schedule |
| F4a-02 | SQL | unknown driver id | 1452 |
| F4a-03 | SQL | two deliveries, same donation + branch | both insert |
| F4a-04 | SQL | unique index exactly on (donation_id, recipient_branch_id) | **none exists** |
| F4b-01 | SQL | assign a manager/donor as driver | 1644 |
| F4b-02 | SQL | assign a DRIVER | accepted |
| F4b-03 | SQL | **assign a driver, then a later unrelated UPDATE** | accepted (no revalidation) |
| F4b-04 | SQL | **R3 scenario**: driver assigned, their role changed to DONOR, then an unrelated update | **accepted** — historical attribution is not re-litigated |
| F4b-05 | SQL | change attribution on a DELIVERED row | 1644 (immutable) |
| F4b-06 | SQL | update another column of a legacy DELIVERED row | accepted, driver stays NULL |
| F4b-07 | SQL | `IN_TRANSIT` with NULL driver | 1644 |
| F4b-08 | SQL | `IN_TRANSIT` with a valid driver | accepted |
| F4b-09 | API | assign a SUSPENDED/INACTIVE driver | 422 |
| F4b-10 | API | assign a DRIVER not on the route | 422 |
| F4b-11 | API | move to `IN_TRANSIT` with no driver | 422 (or the same UPDATE sets it) |
| F4b-11b | API | `IN_TRANSIT` → `DELIVERED` with a different driver | 409 (service rule; DB allows) |
| F4b-12 | API | attempt to change driver after DELIVERED | 409, no correction endpoint exists |
| F4b-13 | AUD | `driver_role_invalid_active` (PLANNED/IN_TRANSIT only) | 0 |
| F4b-14 | AUD | `driver_legacy_null` / confirmed / unconfirmed kg | 5 / 0 / full total |

## 5. DONATION_ITEM guard (F5 — quantity + re-parenting)

Seed (dev only): item A 100 kg donated, 60 delivered, 10 spoiled; item B 50 kg no
children; item C 20 kg fully delivered 20 kg.

| ID | Layer | Operation | Expected |
|---|---|---|---|
| F5-01 | SQL | A → 120 | accepted |
| F5-02 | SQL | A → 70 | accepted |
| F5-03 | SQL | A → 70.00 exactly | accepted (inclusive boundary) |
| F5-04 | SQL | A → 69.99 | 1644 |
| F5-05 | SQL | A unrelated column update | accepted (guard on reduction only) |
| F5-06 | SQL | B → 10 (no children) | accepted |
| F5-07 | SQL | B → 0 | 3819 (`chk_donation_quantity`) |
| F5-08 | SQL | C → 19 | 1644 |
| F5-09 | SQL | item with 3 deliveries + 2 spoilage rows | total equals the true sum (no fan-out) |
| F5-10 | SQL | insert an allocation past donated | rejected by existing `trg_delivery_item_*` |
| F5-11 | SQL | **re-parent A** (has allocations) | **1644** |
| F5-12 | SQL | **re-parent B** (no allocations) | accepted |
| F5-13 | SQL | re-parent C (spoilage only, no delivery) | 1644 |
| F5-14 | API | `PATCH /donation-items/{id}` below committed | 409 with the committed total |
| F5-15 | API | re-parent with allocations | **409 `item_has_allocations`**, clear message |
| F5-16 | API | concurrent allocate + reduce (2 sessions, ≥20 iterations) | serialised by `FOR UPDATE`; one gets 409/1644; invariant holds |
| F5-17 | API | staleness probe: open a transaction, read, sleep, allocate from another session, then reduce | the `FOR UPDATE` re-read sees the new allocation and rejects the stale reduction |
| F5-18 | AUD | `alloc_le_donated`, `delivery_item_same_donation` | pass |

## 6. Temperature plausibility (F8)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| F8-01 | SQL | `NULL` | accepted |
| F8-02 | SQL | `-50.00` / `150.00` | accepted |
| F8-03 | SQL | `-50.01` / `150.01` | 3819 |
| F8-04 | SQL | `3.40` | accepted — plausibility is not safety |
| F8-05 | API | `340` with `PASSED` | 422 phrased as plausibility |
| F8-06 | API | `NULL` temperature with `PASSED` | accepted; UI invents nothing |
| F8-07 | API | `FAILED` at a plausible temperature | accepted — independent judgements |
| F8-08 | AUD | `temperature_out_of_range` | 0 |

## 7. View and audit-script corrections (R7, R8, R12)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| R7-01 | SQL | seed a DELIVERED `delivery_item` of **1.25 kg** with a recorded driver | AUD prints `n=1.25`, not `1` |
| R7-02 | SQL | same 1.25 kg with no recorded driver | `driver_unconfirmed_delivered_kg` also `n=1.25` |
| R8-01 | AUD | `candidate.py --self-test` | 39 assertions PASS |
| R8-02 | AUD | `candidate.py --baseline <alt export>` | comparison uses the alt export (verified: an export without views fails the view assertions) |
| R8-03 | AUD | `candidate.py --baseline missing.sql` | exit 1 with a clear message |
| R8-04 | AUD | `audit_db.py` (original) with `--baseline` | flag ignored — proves the change is new |
| R8-05 | AUD | frozen `database/schema.sql` | unchanged after everything |
| R12-01 | SQL | `information_schema.views.security_type` for `vw_donor_impact` | `INVOKER`, definer not root |
| R12-02 | OPS | restore dump into `sfc_restore_verify` | audit exit 0, 104 rows |
| R12-03 | OPS | fingerprint the restored copy | combined digest identical to live |
| R12-04 | SQL | `SELECT` on the view as `sfc_app` | works (INVOKER + database-wide SELECT) |
| R12-05 | SQL | `SELECT` on the view as a user without base-table grants | denied (no hidden escalation) |
| G-01 | SQL | `SHOW GRANTS FOR 'sfc_app'@'localhost'` | exactly **17** lines: 1 `USAGE ON *.*`, 1 database-wide `GRANT SELECT, INSERT ON \`smart_food_supply_chain\`.*`, **12** single-table `GRANT UPDATE ON \`smart_food_supply_chain\`.\`<t>\`` lines, **3** single-table `GRANT DELETE ON ...` lines. Assert: zero lines containing a wildcard `UPDATE`/`DELETE`, zero lines with more than one table after `ON`, and zero lines naming `donation_status_history` |
| G-10 | SQL | `SELECT COUNT(*) FROM information_schema.table_privileges WHERE grantee = '''sfc_app''@''localhost''' AND privilege_type = 'UPDATE'` | **12** |
| G-11 | SQL | same query with `privilege_type = 'DELETE'` | **3** |
| G-12 | SQL | same query filtered to `table_name = 'donation_status_history'` (any privilege type) | **0** |
| G-13 | SQL | `SELECT COUNT(*) FROM information_schema.table_privileges WHERE grantee = '''sfc_app''@''localhost''' AND table_schema = 'smart_food_supply_chain'` | 15 (12 + 3) — proves no table-level grant beyond the intended set |
| G-02 | SQL | `UPDATE donation_status_history SET note='x'` as `sfc_app` | **1142 (command denied)** — not 1644. 1644 means the grant is too broad |
| G-03 | SQL | `DELETE FROM donation_status_history` as `sfc_app` | 1142 |
| G-04 | SQL | `UPDATE delivery SET delivery_status=...` as `sfc_app` | allowed (table is in the UPDATE list) |
| G-05 | SQL | `INSERT INTO donation_status_history ...` as `sfc_app` | allowed (db-wide INSERT) — appends are the only write |
| G-06 | SQL | `TRUNCATE donation_status_history` as `sfc_app` | denied (no `DROP`) |
| G-07 | SQL | `UPDATE inspection_log` as `sfc_app` | 1142 (append-only by grant, deliberately) |
| G-08 | SQL | attempt `REVOKE UPDATE ON ...donation_status_history` as the admin | 1147 `ER_NONEXISTING_TABLE_GRANT` — proves there is no table grant to revoke |
| G-09 | SQL | `SHOW GRANTS FOR 'sfc_migrator'@'localhost'` | includes `TRIGGER` and `CREATE VIEW`; no `GRANT OPTION`, no `SUPER`, no `FILE` |

## 8. Data preservation and runner (R10, R11)

| ID | Layer | Operation | Expected |
|---|---|---|---|
| R10-01 | SQL | fingerprint before vs after the batch | byte-identical, all 15 tables + combined digest |
| R10-02 | SQL | `not_truncated` column | 1 on every row |
| R10-03 | SQL | total rows in the fingerprint | 104 |
| R10-04 | SQL | reconstructed snapshots / donations covered | 5 / 5 |
| R10-05 | SQL | pickup NULLs, driver NULLs, schedule NULLs | 5 / 5 / 5 |
| R10-06 | SQL | deliberately change one value in the dev copy, re-fingerprint | digest changes (proves the test can fail) |
| R11-01 | OPS | runner re-run with an edited applied file | refuses (checksum mismatch) |
| R11-02 | OPS | kill the runner after a `started` row | next run refuses and prints the §4 recovery path |
| R11-03 | OPS | ledger state after a validated migration | `applied` with `applied_at` and `duration_ms` |
| R11-04 | OPS | rollback a migration | state `rolled_back`, never left as `applied` |
| R11-05 | OPS | `002b` recovery case D (wrong snapshot) | trigger dropped, `is_reconstructed = 1` rows only deleted, trigger recreated, backfill re-run |
| R11-06 | OPS | runner with a PostgreSQL-style "continue on error" flag | flag does not exist; first error aborts |
| X-01 | SQL | preflight P7 vs V000 | identical counts |
| X-02 | SQL | charset/collation of new columns | utf8mb4_0900_ai_ci |
| X-03 | AUD | post-batch, post-migration baseline | exit 0; new objects explained once each |
| X-04 | AUD | `--self-test` on the original script | 39 PASS, unchanged |
| X-05 | SQL | re-run any applied migration file | precondition non-zero → refused, nothing applied |
| X-06 | SQL | full rollback, then audit with the **pre**-migration baseline | exit 0; 15 tables / 2 views / 16 triggers |
| X-07 | API | end-to-end donor → manager → driver → inspector | status, allocation, delivery, inspection and reports agree |

---

## 9. What these tests do not prove

- SQL tests do not prove the *service* enforces actor, scope and transition rules;
  the API rows must be implemented in Phase 3 before they can run.
- A concurrency test that passes once proves nothing; F5-16 must be repeated.
- The fingerprint proves data equality, not business correctness.
- Restore-verification proves the dump restores on this machine, not that the
  production host has the space or the window.
