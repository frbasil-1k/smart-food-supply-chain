# PHASE 2 — FINAL REPORT

**Project:** Smart Food Supply Chain (DBMS)
**Server:** MySQL 8.0.46, instance `MySQL80_New`, 127.0.0.1:3306 (PID 6792)
**Phase:** live `smart_food_supply_chain` → cloned `smart_food_supply_chain_dev`, nine approved migrations applied, validated, tested, audited
**Date:** 2026-11-16
**Original database:** **untouched** — 15 tables / 2 views / 16 triggers / 6 CHECKs / 25 FKs / **104 rows**, content digest `42285b6097d4b84fc3323f306cf44031e8c621433697464b9265894ced9565cb` before and after.

---

## 1. Summary table — the nine migrations

| # | Migration file | SHA-256 (first 12) | State | Validation performed by the runner | Time |
|---|---|---|---|---|---|
| 1 | `001_user_credential.sql` | `2c42344488b7` | **applied** | 11 columns; 2 CHECK constraints; 1 unique index; 0 credentials invented; 15 users still credential-less; original rows 104 | 92 ms |
| 2 | `002a_donation_status_history.sql` | `dff2420ed339` | **applied** (after the documented recovery, §4) | 9 columns; 3 CHECKs; unique one-snapshot index; 2 append-only triggers; 0 rows; original rows 104 | 184 ms |
| 3 | `002b_backfill_donation_history.sql` | `4928c2f5089e` | **applied** | 5 reconstructed snapshots; 5 donations covered; 0 uncovered; 0 fabricated timestamps; 0 actors on snapshots; exact approved note; original rows 104 | 79 ms |
| 4 | `003_donation_pickup.sql` | `b25248227ca3` | **applied** | 3 nullable columns; 5/5/5 legacy NULLs; original rows 104 | 140 ms |
| 5 | `004a_delivery_attribution.sql` | `a01608f0728e` | **applied** | 2 nullable columns; `fk_delivery_driver`; 2 new indexes; 5/5 legacy NULLs; no forbidden unique pair; original rows 104 | 167 ms |
| 6 | `004b_delivery_driver_triggers.sql` | `8e612c87435a` | **applied** | 2 triggers; no wrongly attributed driver; no transit without driver; 5 legacy drivers still NULL; original rows 104 | 60 ms |
| 7 | `005_donation_item_update_guard.sql` | `8eebbf8acea9` | **applied** | trigger present; 0 over-allocation; 0 cross-donation allocation; original rows 104 | 47 ms |
| 8 | `006_inspection_temperature_check.sql` | `c8aeb57a4121` | **applied** | constraint enforced; 0 out-of-band readings; 5 inspection rows intact; original rows 104 | 135 ms |
| 9 | `007_vw_donor_impact.sql` | `fa01355f8e50` | **applied** | view exists as INVOKER; 2 original views preserved; 4 donor rows; no negative balance; delivered never exceeds donated; original rows 104 | 148 ms |

Every migration was one runner invocation, stopped on first error, checksum-verified against
`MANIFEST.sha256`, recorded `applied` only after its validation passed. Full per-run output:
`reports/phase2/migration_<version>.log`. Ledger: `smart_food_supply_chain_dev.schema_migrations`
(9 rows, all `applied`, all checksums `match`).

---

## 2. Final structure

| Database | Tables | Views | Triggers | CHECKs | FKs | Rows |
|---|---|---|---|---|---|---|
| `smart_food_supply_chain` (original) | 15 | 2 | 16 | 6 | 25 | **104** |
| `sfc_restore_verify` (restore proof) | 15 | 2 | 16 | 6 | 25 | 104 |
| `smart_food_supply_chain_dev` (migrated) | 18 | 3 | 21 | 12 | 29 | **118** |
| `smart_food_supply_chain_phase2_test_dev` (test clone) | 18 | 3 | 21 | 12 | 29 | 118 |

**Why the dev database has 118 rows, not 104** — required explanation, not corruption:

| Part | Rows |
|---|---|
| the original 15 tables | 104 |
| `donation_status_history` — 5 reconstructed legacy snapshots (002b) | 5 |
| `schema_migrations` — 1 ledger row per applied migration | 9 |
| **total** | **118** |

104 + 5 + 9 = 118 exactly. The audit reports this as a warning (`row total 118 differs from
the verified 104`) by design: it compares against the pre-migration constant, and the
difference is fully accounted for above. Exit code is unaffected.

---

## 3. Data preservation — byte-identical original rows

| Control | Result |
|---|---|
| Pre-migration fingerprint of the original | `42285b60…9565cb`, 15 tables, 104 rows, `not_truncated = 1` on every row |
| Fingerprint of the restored copy | **identical** digest, 15/15 table hashes match |
| Pre-migration fingerprint of the clone | **identical** digest |
| Post-migration fingerprint of `_dev` | **identical** digest, 104 rows, **0 per-table differences** |
| Negative control (R10-06) | changing one value in the test clone changed the digest (`dedd1517…` → `22bdf9f4…`), reverting restored it — the test can fail |
| Original re-audited after everything | exit 0, 7/7 invariants, 0 failures, 104 rows |
| Frozen originals | `schema.sql` `50b7af57…`, `audit_db.py` `6f7dfc7e…`, `eer diagram.mwb` `dc9105b8…` — all unchanged |

Backup taken before any migration: `C:\backup\sfc_before_phase2_20261116_160043.sql`
(53,341 bytes, SHA-256 `e04b8c4c818ac30a024278d5e568ee027288ca7289e4c5806a0eb2b85d5f1d4c`,
15 tables + 2 views + 16 triggers + 15 INSERT blocks, no `CREATE DATABASE`/`USE`).
Not overwritten. Post-migration schema+data snapshot:
`C:/backup/sfc_dev_after_migrations_20261116_161137.sql`.

---

## 4. The one failure and its documented recovery (002a)

**Blocker:** `ERROR 1419 … You do not have the SUPER privilege and binary logging is enabled`
on the first `CREATE TRIGGER`. Environment: `log_bin=ON`, `binlog_format=ROW`,
`log_bin_trust_function_creators=OFF`. A **server configuration prerequisite**, not a defect in
the migration SQL — the same file applied completely once the prerequisite was met.

| Step | Action | Evidence |
|---|---|---|
| Capture before | root read-only capture; `persisted_variables` **empty** (nothing to overwrite) | `log_bin_trust_before.txt` |
| Re-verify partial state | dev; 0 rows; 9 columns; 3 CHECKs; unique index; **0 of 2** triggers; 0 inbound FKs; 16 original triggers; no stray objects | `evidence/partial_002a_state.txt` |
| Preserve ledger row | failed row saved verbatim before any cleanup | `evidence/ledger_002a_verbatim.txt` |
| Enable (temporary) | `SET PERSIST log_bin_trust_function_creators = ON;` → runtime 1; grants untouched | `log_bin_trust_enabled.txt` |
| Recover (documented case "table + 0/1 trigger") | as `sfc_migrator`: `DROP TABLE donation_status_history` (empty, never populated, no inbound FKs) → `DELETE FROM schema_migrations WHERE version='002a'` → re-apply the whole file through the runner | `recovery_002a.txt`, `migration_002a_recovery.log` |
| Verify | 9 columns, 3 CHECKs, unique index, **2 triggers**, 0 rows, ledger `applied` | `migration_002a_recovery.log` |
| Restore | `SET GLOBAL … = OFF;` + `RESET PERSIST IF EXISTS …;` → runtime **0**, **no persisted entry**, binlog settings unchanged | `log_bin_trust_restored.txt` |

The variable is documented by MySQL as deprecated; it was used only as a temporary
compatibility workaround for this 8.0 environment, kept enabled only across the migrations that
create triggers (002a→005), and removed before `006`/`007`. `sfc_migrator` never gained `SUPER`
or `SYSTEM_VARIABLES_ADMIN`, its grant list is unchanged, and no trigger was created as root —
all five new triggers carry `DEFINER=sfc_migrator@localhost`
(`evidence/five_triggers_verified.txt`).

Full narrative: `reports/phase2/STAGE5_FAILURE_002a.md` (sections 1–7 as first reported,
section 8 the resolution — nothing rewritten).

---

## 5. Test matrix results

Executed on the disposable clone `smart_food_supply_chain_phase2_test_dev`, never on the
original. Harness: `database/phase2/sql_test_matrix.py`; raw output:
`reports/phase2/evidence/sql_test_results.txt`.

### 5.1 PASSED — 64/64 SQL-layer cases

| Area | Cases | Evidence |
|---|---|---|
| F1 credentials (structure, uniqueness 1062, FK 1452, plaintext accepted by SQL, lock pairing 3819, token pairing 3819, cascade, `ON DELETE CASCADE` declared) | F1-01…F1-09c | all matched |
| F2a history structure (append-only 1644 ×2, time semantics 3819, no-actor 3819, distinct status 3819, one-snapshot 1062, many genuine rows, enum 1265) | F2a-02…F2a-10 | all matched |
| F2b backfill (5 snapshots, 0 uncovered, 0 duplicates, approved note, no fabricated timestamps) | F2b-01…F2b-05 | all matched |
| F3 pickup structure (5/5/5 NULL) | F3-01 | matched |
| F4a attribution (5/5 NULL, unknown driver rejected, duplicate delivery+branch allowed, **no** unique pair) | F4a-01…F4a-04 | all matched |
| F4b driver guards (manager rejected 1644, DRIVER accepted, no revalidation, R3 role-change tolerated, DELIVERED attribution immutable 1644, legacy update allowed, IN_TRANSIT needs a driver 1644) | F4b-01…F4b-08 | all matched |
| F5 item guard (reduction below committed 1644, exact boundary accepted, increase accepted, unrelated update accepted, re-parent with allocations 1644, childless reduce/zero 3819, childless re-parent accepted) | F5-01…F5-12 | all matched |
| F8 temperature (−50.00/150.00 accepted, −50.01/150.01 3819, NULL accepted, 3.40 accepted) | F8-01…F8-04 | all matched |
| X-02 new-column collation | — | `utf8mb4_0900_ai_ci` |

### 5.2 PASSED — operations and audit layer

| ID | What was proven | Result |
|---|---|---|
| R7-01 / R7-02 | fractional kg: seeded DELIVERED allocations of 1.25 kg → `driver_confirmed_delivered_kg n=1.25`, `driver_unconfirmed_delivered_kg n=62.25` (61.00 + 1.25) — **no truncation to 1** | PASS |
| R8-01 | `audit_db_phase2.py --self-test` | PASS, 0 failed assertions |
| R8-02 | `--baseline` really switches the reference: dev audited against `schema.sql` → exit 1 with `extra=['donation_status_history','schema_migrations','user_credential']`, `extra=['vw_donor_impact']` | PASS (control behaves) |
| R8-03 | missing baseline file → clear `ERROR: --baseline … not found` | PASS |
| R8-05 | frozen originals unchanged (md5 checked) | PASS |
| R12-01 | `vw_donor_impact` is `SECURITY_TYPE=INVOKER`, definer `sfc_migrator@localhost`, not root | PASS |
| R12-02 / R12-03 | restore into `sfc_restore_verify` → audit exit 0, 104 rows, identical digest | PASS |
| X-03 | dev audit against `schema_post_migrations.sql` → exit 0, 14/14 invariants, 0 structural failures | PASS |
| X-04 | original `audit_db.py --self-test` unchanged → PASS | PASS |
| X-05 | re-running an applied migration → "already applied with a matching checksum — nothing to do", nothing executed | PASS |
| R10-01…R10-05 | fingerprint identity, `not_truncated=1`, 104 rows, 5/5 snapshots, 5/5/5 NULLs | PASS |
| R10-06 | negative control, digest reacts to a changed value and returns on revert | PASS |
| R11-01 | runner refuses an applied file whose bytes changed: `ABORTED: file was edited AFTER being applied (checksum mismatch)` | PASS |
| R11-03 | ledger records `applied` with `applied_at` and `duration_ms` for all nine | PASS |
| R11-06 | no "continue on error" flag exists; first error aborts | PASS |
| G-09 | `sfc_migrator` grants include `TRIGGER` and `CREATE VIEW`; no `GRANT OPTION`, no `SUPER`, no `FILE` | PASS |
| 007 review gate | numbers read on the pre-migration copy first: 4 donor rows, `delivered ≤ donated`, no negative balance (Hotel Donor 20.00 − 15.00 − 1.50 = 3.50); all 5 deliveries `DELIVERED`, so the status filter changes nothing today — a forward guarantee | PASS |

Incidental evidence: the pre-existing delivery gate rejected a delivery with
`Delivery blocked: latest food inspection has not passed`, and the audit's
`hist_missing_donation` invariant flagged a deliberately inserted donation with no history row.

### 5.3 DEFERRED — not run, therefore **not** reported as passed

| Group | Rows | Why |
|---|---|---|
| API layer | F1-10…F1-16, F2-07…F2-11, F3-02…F3-08, F4b-09…F4b-12, F5-14…F5-17, F8-05…F8-07, X-07 | requires the service built in Phase 3 |
| `sfc_app` grants | G-01…G-08, G-10…G-13, F2b-06, R12-04, R12-05, F2a-02/03 as the app account | `sfc_app` deliberately not created in Phase 2 |
| Rollback rehearsal | X-06, R11-04, R11-05 | `ROLLBACK_ALL.sql` is never run automatically; it is a deliberate, supervised action |
| Runner kill-timing | R11-02 | requires killing a run mid-statement; not attempted on a working system |

### 5.4 Harness defects found and fixed during testing (not migration defects)

* `F1-09` originally deleted a donor that other tables still reference (1451). Corrected to
  search for an unreferenced user and to assert the declared `ON DELETE CASCADE` rule.
* `F4a-02` expected 1452, but the BEFORE INSERT trigger rejects an unknown driver with **1644**
  first — the trigger runs before the FK. Expectation corrected and the FK's existence asserted
  separately.
* `F4b-05` set the driver to `NULL` on a row that already had `NULL` — not a change, so the
  trigger allowed it. Corrected to assign a real driver.
* `002a`'s ledger query used a non-existent `filename` column; the real column is `name`.

---

## 6. Deliverables created

| Path | Purpose |
|---|---|
| `database/phase2/run_migration.py` | target-locked runner (refuses non-`_dev`, refuses the original, checksums, ledger, per-migration pre/post checks) |
| `database/phase2/sql_test_matrix.py` | SQL-layer test harness, refuses anything but the test clone |
| `database/schema_post_migrations.sql` | post-migration schema export (18 tables, 21 triggers, 3 views) — the new baseline |
| `database/audit_db_phase2.py` | Phase 2 audit from the approved candidate, with the `--baseline` switch |
| `reports/phase2/PHASE2_FINAL_REPORT.md` | this report |
| `reports/phase2/STAGE0_VERIFICATION.md`, `PACKAGE_DEVIATION.md`, `STAGE5_FAILURE_002a.md` | package and failure evidence |
| `reports/phase2/audit_*.txt`, `pre/post_fingerprint_*.txt`, `preflight_*.txt`, `migration_*.log`, `recovery_002a.txt`, `log_bin_trust_*.txt` | evidence trail |

### Deviations from the approved package (all disclosed, all documented)

1. `database/prep_phase1/RUNNER_DESIGN.md` — four mandated Phase 2 corrections; this is the only
   file that differs from `phase1_migration_prep_revision.zip`
   (`reports/phase2/PACKAGE_DEVIATION.md`). All nine migration files and all validation SQL are
   byte-identical to the approved package.
2. `database/audit_db_phase2.py` — one parser correction: `parse_column` now recognises
   `GENERATED … STORED`, which the pre-F4 schema never needed. Without it the post-migration
   baseline comparison reported a false structural difference on
   `donation_status_history.reconstructed_donation_id`. The frozen `database/audit_db.py` was
   **not** changed and its 39-assertion self-test still passes.
3. `database/schema_post_migrations.sql` — new file, generated by `mysqldump --no-data`.

---

## 7. Boundaries honoured

* `smart_food_supply_chain` — never written: no DDL, no DML, no migration, no probe. 104 rows and
  the same digest at every checkpoint.
* `sfc_restore_verify` — created, restored once, read-only thereafter.
* Verified backup — never overwritten; a second, separate post-migration snapshot was written.
* `sfc_migrator` — exactly the 12 approved database-level privileges on `_dev.*`; no `SUPER`, no
  `SYSTEM_VARIABLES_ADMIN`, no `GRANT OPTION`, nothing on the original (proven: `ERROR 1142`).
* No migration was ever executed as root; no trigger was created as root; no `--force`; no retry;
  no automatic rollback; `ROLLBACK_ALL.sql` was not run.
* No migration was marked applied without passing its validation.
* The one unresolved failure stopped the batch immediately and was reported before any recovery.

---

## 8. What is left for Phase 3

* Build the service so the API-layer matrix rows can run; treat every one as **unproven** until then.
* Create `sfc_app` and run the grant matrix (G-01…G-08, G-10…G-13) — deliberately out of Phase 2.
* Rehearse `ROLLBACK_ALL.sql` in a supervised window (X-06, R11-04, R11-05).
* Decide whether to re-seal the approved ZIP now that `RUNNER_DESIGN.md` differs, or keep the
  deviation record.
