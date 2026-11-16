# PHASE 2 MIGRATION RUNNER — DESIGN AND RECOVERY POLICY

**Status: design only.** No runner is implemented in this phase, nothing here
has been executed, and no database was contacted. This document exists so the
ledger described in the README is a real design rather than a promise.

---

## 1. Why a runner at all

The project currently has no migration infrastructure. Applying ten files by
hand in Workbench is how migrations end up half-applied: a trigger fails, the
operator retries the whole file, `CREATE TABLE` errors with 1050, and nobody can
tell whether the ALTER before it committed. MySQL commits implicitly around DDL,
so "it's all one transaction" is never true.

The runner's job is narrow: apply one file, verify it, record it. It is not a
schema diffing tool and it does not generate SQL.

---

## 2. Ledger

Created once by the runner's bootstrap (this is the only place
`CREATE TABLE IF NOT EXISTS` is acceptable, because the ledger is infrastructure,
not a migration):

```sql
CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `version`     VARCHAR(20)  NOT NULL,          -- '001', '002a', ...
  `name`        VARCHAR(120) NOT NULL,          -- file basename
  `checksum`    CHAR(64)     NOT NULL,          -- SHA-256 of the file bytes
  `state`       ENUM('started','applied','failed','rolled_back')
                             NOT NULL DEFAULT 'started',
  `started_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `applied_at`  DATETIME     NULL DEFAULT NULL,
  `finished_at` DATETIME     NULL DEFAULT NULL,
  `duration_ms` INT UNSIGNED NULL DEFAULT NULL,
  `note`        VARCHAR(255) NULL DEFAULT NULL, -- error class, operator, reason
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

`state` is the whole point:

| state | meaning |
|---|---|
| `started` | the runner began the file and has not confirmed success — **this is the dangerous state** |
| `applied` | the file ran and its validation query passed |
| `failed` | it ran and validation did not pass; see §4 |
| `rolled_back` | it was reversed and is no longer in effect |

Rule: **`applied` is written only after validation**, never after the SQL returns.
A file that executes without error but leaves the schema wrong is not applied.

Checksum policy: SHA-256 over the file's exact bytes. A file whose checksum no
longer matches its `applied` row is an error, not an update — migration files are
immutable once applied. Changed intent means a new versioned file.

---

## 3. Apply algorithm

Every step below runs against the development target
`smart_food_supply_chain_dev`. The original `smart_food_supply_chain` is never a
runner target (§8).

```
for each file in sorted order:
    if ledger.applied(version):
        require checksum match           # else abort: file edited after apply
        continue
    if ledger.state(version) == 'started' or 'failed':
        abort with the §4 recovery instruction for that version
    assert preconditions(file)           # the -- PRECONDITION block; abort if non-zero
    snapshot_probe(version)              # record which target objects exist now
    ledger.insert(version, checksum, state='started')
    execute(file)                        # one file per mysql invocation, stop on error
    run validation block V<version>
    if validation passed:
        ledger.update(state='applied', applied_at=NOW(), duration_ms=...)
    else:
        ledger.update(state='failed', note=validation failure summary)
        abort
```

- **One file per invocation.** A single `mysql < file` process per migration, so
  the exit status belongs to exactly one file and a crash cannot silently skip one.
- **Stop at the first error.** No `--force`, no "continue on error" flag, no
  retry loop.
- **`snapshot_probe`** records the existence of the objects that file is supposed
  to create (from a small per-file manifest: table, columns, triggers, constraint,
  view). It is how a `started` row is later resolved: compare the recorded probe
  with the current `information_schema` and the answer is "not started",
  "partially applied" or "actually complete".
- **No implicit commits to undo.** The runner never claims transactional
  behaviour it does not have.

---

## 4. Partial failure and recovery, per migration

A `started` or `failed` row means: **do not re-run the file**. Diagnose with the
probe below, then take the stated action.

| Version | Object | Failure shape | Diagnosis | Recovery |
|---|---|---|---|---|
| 001 | table | single `CREATE TABLE` — atomic | `information_schema.tables` for `user_credential` + 11 columns | complete → mark `applied`; absent → re-run; present but wrong (e.g. 1050 on a stray table) → `DROP TABLE user_credential` after exporting, then re-run |
| 002a | table + 2 triggers | table can exist while a trigger failed | table exists? `trg_dsh_block_%` count = 2? | table + 2 triggers → `applied`; table + 0/1 trigger → `DROP TRIGGER` leftovers, then create the missing ones only; no table → re-run |
| 002b | DML only | single `INSERT ... SELECT`, atomic | `COUNT(*) WHERE is_reconstructed = 1` vs `COUNT(*) FROM donation` | counts equal → `applied`; zero → re-run; fewer than donations → re-run (the `LEFT JOIN` skips existing); **never** delete genuine rows |
| 003 | 3 columns, one ALTER | atomic per statement | count of the 3 columns in `information_schema.columns` | 3 → `applied`; 0 → re-run; 1–2 → impossible from one statement: investigate before touching anything, do not re-run (1060) |
| 004a | 2 columns + 2 indexes + FK | atomic per statement | columns, index names, `fk_delivery_driver` | all → `applied`; none → re-run; partial → inspect `information_schema.statistics`/`key_column_usage`, add only what is missing |
| 004b | 2 triggers | each `CREATE TRIGGER` atomic | `trg_delivery_driver_%` count | 2 → `applied`; 0 → re-run; 1 → `DROP TRIGGER` the survivor, re-run the file for both |
| 005 | 1 trigger | atomic | `trg_donation_item_update_guard` exists | exists → `applied`; absent → re-run |
| 006 | 1 CHECK | atomic, validates existing rows | `constraint_name = 'chk_temperature_range'` | exists + `ENFORCED=YES` → `applied`; absent → re-run **after** re-checking the zero out-of-band precondition |
| 007 | 1 view | atomic | `information_schema.views` | exists with `SECURITY_TYPE='INVOKER'` → `applied`; absent → re-run |

Universal rules:

- Never "fix" a partial state by running the whole batch again.
- Never `DROP` an object that has collected data without exporting it first.
- After any recovery, re-run `CONTENT_FINGERPRINT.sql` and require the pre-batch
  digest. Structural recovery must not have touched the 104 original rows.
- Record the outcome: `applied` (with a note naming the repair), or `failed`
  followed by the documented rollback, which sets `rolled_back`.

---

## 5. Least-privilege accounts (includes the R4 append-only second layer)

The application must not connect as `root`. The runner and the app use different
accounts, and neither is granted more than its job requires. Grants are written
to start from the narrowest base and add per-table rights — never from a
wildcard plus exceptions, because MySQL cannot express exceptions (see §5c).

### 5a. Runner account

```sql
CREATE USER 'sfc_migrator'@'localhost' IDENTIFIED BY '<from secret store>';

-- Phase 2 target is the DEVELOPMENT clone only. The original database name must
-- never appear in this account's grants: one migration reaching it is exactly the
-- mistake this design exists to prevent.
GRANT ALTER, CREATE, DROP, INDEX, REFERENCES, TRIGGER, CREATE VIEW,
      INSERT, SELECT, UPDATE, DELETE
   ON smart_food_supply_chain_dev.* TO 'sfc_migrator'@'localhost';
```

Every privilege above is required by a file in this package. The two additions
made in this revision are `TRIGGER` and `CREATE VIEW`; without them 002a, 004b,
005 and 007 cannot run at all.

| Privilege | Needed by | Why exactly this one |
|---|---|---|
| `CREATE` | 001, 002a, ledger bootstrap | `CREATE TABLE` (inline PK, UNIQUE, CHECK and FK definitions are covered by `CREATE` + `REFERENCES`) |
| `ALTER` | 003, 004a, 006, rollback | `ADD COLUMN`, `ADD KEY`, `ADD CONSTRAINT`, `DROP CHECK`, `DROP COLUMN` |
| `DROP` | rollback, partial-object repair | `DROP TABLE`, `DROP VIEW` |
| `INDEX` | 004a, future `CREATE INDEX` | creating and removing indexes |
| `REFERENCES` | 001, 002a, 004a | creating foreign keys |
| **`TRIGGER`** | **002a, 004b, 005, and the trigger step of rollback** | `CREATE TRIGGER` / `DROP TRIGGER`. `DROP` alone is **not** sufficient: dropping a trigger also requires `TRIGGER` on its table |
| **`CREATE VIEW`** | **007** | `CREATE VIEW`. No other privilege covers it; `CREATE` does not |
| `INSERT` | 002b, ledger | the backfill `INSERT ... SELECT`, and ledger rows |
| `SELECT` | 002b, ledger, trigger bodies, 007 | reading `donation` for the backfill; trigger bodies read `app_user`, `delivery_item`, `spoilage_record` and run as the definer, so the definer needs `SELECT`; MySQL also checks privileges on the columns a view references |
| `UPDATE` | ledger only | `started` -> `applied` / `failed` / `rolled_back` transitions |
| `DELETE` | ledger cleanup, documented recovery | 002b's recovery case D (delete reconstructed rows only) and rollback data steps |

Deliberately **not** granted to the runner:

- `GRANT OPTION`, `CREATE USER`, `SUPER`, `SYSTEM_VARIABLES_ADMIN` — the runner
  migrates one schema, it does not administer the server.
- `CREATE ROUTINE`, `EXECUTE`, `EVENT` — no stored procedures, functions or events
  exist in this design.
- `FILE` — the optional pre-rollback export snippets in `ROLLBACK_ALL.sql`
  (`SELECT ... INTO OUTFILE`) are **DBA statements run manually as an
  administrator**, not runner steps. If they were ever automated, `FILE` would
  have to be granted explicitly and that would be a separate review.

The ledger table lives in the same schema, so `CREATE`, `INSERT`, `SELECT` and
`UPDATE` above already cover it.

### 5b. Application account

Base grant is read-and-append only. Mutation is then granted **table by table**.

```sql
CREATE USER 'sfc_app'@'localhost' IDENTIFIED BY '<from secret store>';

-- 1. Baseline: read anything, append anything. Nothing is mutated yet.
GRANT SELECT, INSERT ON smart_food_supply_chain.* TO 'sfc_app'@'localhost';

-- 2. Mutate only the tables a workflow actually changes: ONE STATEMENT PER
--    TABLE. MySQL accepts exactly one privilege level (table) per GRANT, so a
--    comma-separated table list is a syntax error (1064), not a shorthand.
--    donation_status_history is NOT in this list. Neither is schema_migrations.
GRANT UPDATE ON smart_food_supply_chain.organization      TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.branch            TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.app_user          TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.user_credential   TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.route             TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.coverage_area     TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.food_category     TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.donation          TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.donation_item     TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.delivery          TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.spoilage_record   TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.delivery_review   TO 'sfc_app'@'localhost';

-- 3. Rows that may genuinely be removed. A donation is cancelled, never deleted.
GRANT DELETE ON smart_food_supply_chain.route_assignment  TO 'sfc_app'@'localhost';
GRANT DELETE ON smart_food_supply_chain.dependent         TO 'sfc_app'@'localhost';
GRANT DELETE ON smart_food_supply_chain.delivery_item     TO 'sfc_app'@'localhost';
```

That is 1 database-wide `SELECT, INSERT` plus **15 single-table statements**: 12
`UPDATE` grants and 3 `DELETE` grants, none of them for
`donation_status_history`. Keep the statements separate: MySQL accepts exactly one
table per `GRANT`, so combining several tables after `ON` in a single statement is
a syntax error (1064) that fails before any privilege is checked.

**Phase 2 does not create `sfc_app` and does not execute any of these grants.** They
are written against the production database name because that is the database the
application will use in service; an application developed against
`smart_food_supply_chain_dev` would name that database instead. Creating this
account is deferred until the ledger-`INSERT` limitation in §5d is resolved by the
application-security review — the database-wide `INSERT` would otherwise let the
application write rows into `schema_migrations`.

Resulting ability, stated per table that matters:

| Table | App can | Note |
|---|---|---|
| `donation_status_history` | `SELECT`, `INSERT` | **no `UPDATE`, no `DELETE`, no `DROP`** — append-only, by grant *and* by trigger |
| `inspection_log` | `SELECT`, `INSERT` | no `UPDATE`: an inspection record is a historical fact; correction needs an explicit, auditable workflow (flagged in §5d) |
| `user_credential` | `SELECT`, `INSERT`, `UPDATE` | login updates counters, lock and token fields; no `DELETE` (users are deactivated, not removed) |
| `donation`, `delivery` | `SELECT`, `INSERT`, `UPDATE` | status and attribution change; rows are never deleted |
| `delivery_item`, `route_assignment`, `dependent` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` | allocation lines, assignments and dependents are removed legitimately |
| `schema_migrations` | `SELECT`, `INSERT` | runner-owned; the app cannot update or delete ledger rows |
| everything else | `SELECT`, `INSERT` (+`UPDATE` where listed) | no destructive rights |

No `DROP` for `sfc_app`, therefore **no `TRUNCATE`** either (`TRUNCATE` requires
`DROP` on the table) — the one statement that bypasses row triggers stays out of
the application's reach.

The append-only triggers from 002a remain in place as an **independent second
layer**. They do not depend on grant hygiene: if a future operator re-grants
`UPDATE` on `donation_status_history` by mistake, writes still fail with 1644.

Views need no extra grant: `vw_donor_impact` is `SQL SECURITY INVOKER`, so the
database-wide `SELECT` in step 1 already covers the view and its six base tables.

### 5c. Why table-level `REVOKE` cannot override a database-wide `GRANT`

The previous draft granted `SELECT, INSERT, UPDATE, DELETE ON smart_food_supply_chain.*`
and then tried:

```sql
REVOKE UPDATE, DELETE ON smart_food_supply_chain.donation_status_history
  FROM 'sfc_app'@'localhost';   -- does NOT do what it looks like
```

That does not work, for three separate reasons:

1. **Privileges are additive.** MySQL's effective privilege set is the union of
   every grant whose scope matches the object — database-wide, table, and column
   levels together. There is no deny rule, no negative privilege, and no
   precedence between scopes. A narrower grant can add rights; it can never
   subtract them.
2. **There is nothing at the table level to revoke.** `REVOKE ... ON db.table`
   removes a privilege that was granted *on that table*. When the privilege came
   from `ON db.*`, no table-level grant row exists, so the statement fails with
   `ER_NONEXISTING_TABLE_GRANT` (1147) — historically `ER_NONEXISTING_GRANT`
   (1141). Either way the wildcard grant survives intact, and the app can still
   `UPDATE` history.
3. **Statement order does not help.** Revoking before or after the wildcard grant
   makes no difference: the union is the same. Re-running the wildcard `GRANT`
   later would also silently undo any such attempt, which is exactly the accident
   the old draft was exposed to.

The only faithful way to express "may update these tables but not that one" is to
start from a base that never includes the withheld privilege and add it per
table — which is what §5b does. This is also why 002a does not rely on grants for
append-only: the trigger is unconditional, the grant is the second layer.

### 5d. Known limits of the grant model

- The database-wide `INSERT` in §5b also lets the app insert into
  `schema_migrations`. That is a residual, low-impact hole (the ledger is
  infrastructure, not tenant data). Hardening options, if wanted later: move the
  ledger to a separate metadata schema the app has no grants on, or replace the
  base grant with per-table `SELECT`/`INSERT` grants (verbose, but the strictest
  form). Both are listed as open items rather than silently assumed.
- No `UPDATE` on `inspection_log` is deliberate. If inspectors must correct a
  recorded reading, that is an explicit auditable workflow (who, when, why) and
  needs its own grant change — not a blanket `UPDATE`.
- `sfc_app` holds `SELECT` on every table, so the audit's data-profile views do
  not need a second account. Read access to `user_credential` is unavoidable for
  the login path; the API must still never serialise `password_hash` or
  `reset_token_hash` (enforced in Phase 3 by the response models).
- The two existing views are `DEFINER=root@localhost`. They keep working for
  `sfc_app` because a definer view runs with the definer's privileges. That is a
  pre-existing condition, recorded as open question 10, not changed here.
- Verify grants in Phase 2 with `SHOW GRANTS FOR 'sfc_app'@'localhost';`, and test
  the distinction that matters: an `UPDATE` on `donation_status_history` should
  fail with **1142 (command denied)**, which proves the grant layer; if it fails
  with 1644 instead, the privilege is too broad and only the trigger saved you.

---

## 6. Audit workflow around the batch (R8)

`audit_db.py` compares the live schema to one reference export. The frozen
default is the pre-migration export, so running it unchanged after the batch
would correctly report the new objects as differences.

```
before batch:
  python database/audit_db.py --out reports\audit_pre.txt          # expect 0
  (plus proposed/ candidate when adopting --baseline)
after the whole batch is applied and validated:
  # structure-only export of the migrated DEVELOPMENT database; the frozen
  # original export (database/schema.sql) is never overwritten
  mysqldump --no-data --routines --triggers --events \
      smart_food_supply_chain_dev > database/schema_post_migrations.sql
  python database/audit_db.py --baseline database/schema_post_migrations.sql \
      --out reports\audit_post.txt                                  # expect 0
```

- The frozen `database/schema.sql` is **never** rewritten. The post-migration
  export is a new file that becomes the baseline for everything after the batch.
- Per-migration validation (`validation/VALIDATION_ALL.sql`) is the immediate,
  cheap check. The full structural and semantic audit runs once at the end,
  because a per-stage baseline would freeze schemas that exist only inside the
  maintenance window.
- If a future batch needs mid-batch auditing, generate a baseline at each accepted
  stage and keep it in `database/baselines/` with the ledger version in its name.
  That is optional and not part of this plan.
- The patch that adds `--baseline` is in `proposed/`; it preserves every existing
  check and the 39-assertion self-test (verified: default self-test still passes).

---

## 7. Restore rehearsal (detail behind README §5)

The runner refuses to start unless a marker file proves a restore was verified:

1. Dump with `--single-transaction --routines --triggers --events`.
2. `CREATE DATABASE sfc_restore_verify`.
3. Restore the dump into `sfc_restore_verify` (never into the live name: the dump
   contains `DROP TABLE IF EXISTS`).
4. `DB_NAME=sfc_restore_verify python database/audit_db.py` → exit 0, 104 rows.
5. `validation/CONTENT_FINGERPRINT.sql` on the restored copy → combined digest
   must equal the live capture.
6. Write `reports/restore_verified_<stamp>.txt` and pass its path to the runner.

Step 5 is the one that matters: the audit proves the *structure* restored, the
fingerprint proves the *data* did. A dump that restores 104 rows with one changed
value would pass step 4 and fail step 5.

---

## 8. What the runner must never do

- Run `database/schema.sql` (it contains `DROP TABLE`).
- Apply more than one file per invocation, or continue after an error.
- Write `applied` before validation.
- Re-run DDL whose object already exists, or "clean up" by dropping and
  recreating an object that holds data.
- Store, print or accept a password on the command line.
- Touch the original `smart_food_supply_chain` in any way. The runner operates
  only on the explicitly approved development target
  `smart_food_supply_chain_dev` — a name that must end in `_dev` — and only after
  `SELECT DATABASE()` confirms it. Read-only work against the original (baseline
  audit, preflight, fingerprint capture, `mysqldump`) is performed by separate,
  non-runner commands and never by this tool.
- Apply a file to any database whose name does not end in `_dev`, or continue
  after a resolver has not cleared a `started`/`failed` row.
- Grant `UPDATE`/`DELETE` database-wide and then try to `REVOKE` them on one
  table. Privileges are additive; the revoke fails with 1147 (or 1141) and the
  wildcard right survives (§5c). Start from the narrow base instead.
- Grant `sfc_app` any structural privilege (`CREATE`, `ALTER`, `DROP`, `INDEX`,
  `REFERENCES`, `TRIGGER`, `CREATE VIEW`) — those belong to `sfc_migrator` alone.
