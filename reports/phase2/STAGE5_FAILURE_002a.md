# Stage 5 — migration 002a failed: STOPPED (permission error)

Time: 2026-11-16 16:02 local
Target database: `smart_food_supply_chain_dev` (the only database that was migrated)
Original database: **not touched** (proof below)

## 1. What happened

| Order | Migration | Result |
|---|---|---|
| 1 | `001_user_credential.sql` | **applied** — 11 columns, 2 CHECKs, 1 unique index, 0 credentials, 15 users without credentials, original rows still 104 |
| 2 | `002a_donation_status_history.sql` | **FAILED** at line 91 |
| 3–9 | `002b` … `007` | **not attempted** (runner loop stopped at the first failure) |

Exact error:

```
ERROR 1419 (HY000) at line 91: You do not have the SUPER privilege and binary
logging is enabled (you *might* want to use the less safe
log_bin_trust_function_creators variable)
```

## 2. Root cause

The server has binary logging enabled, which makes `CREATE TRIGGER` require
`SUPER` (or `SYSTEM_VARIABLES_ADMIN`, or the global relaxation below). The
migration account was deliberately created **without** those privileges:

```
log_bin                          ON
binlog_format                    ROW
log_replica_updates              ON
log_bin_trust_function_creators  OFF
```

`sfc_migrator` holds exactly the approved set:
`SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER,
CREATE VIEW, TRIGGER` on `smart_food_supply_chain_dev.*` — and no global rights.

This is a genuine environment privilege issue, not a SQL defect in the migration.
Affected files: `002a` (2 triggers), `004b` (2 triggers), `005` (1 trigger).

## 3. Exact partial state

Because MySQL commits DDL per statement, the `CREATE TABLE` in 002a succeeded and
only the first `CREATE TRIGGER` failed:

| Object | State |
|---|---|
| `donation_status_history` table | **exists** |
| columns | 9 (complete, including the generated column) |
| CHECK constraints | 3 (complete) |
| `uq_dsh_one_reconstructed` | present |
| `trg_dsh_block_update` / `trg_dsh_block_delete` | **0 of 2 present** |
| rows in the new table | 0 |
| inbound foreign keys to it | 0 |
| outbound foreign keys | 2 (as designed, to `donation`, `app_user`) |
| triggers in dev total | 16 (the originals only) |

Ledger, as written by the runner:

| version | state | note |
|---|---|---|
| 001 | applied | 92 ms |
| 002a | **failed** | `ERROR 1419 … log_bin_trust_function_creators` |

The runner did **not** retry, did not continue, and did not roll back. That is the
designed behaviour.

## 4. Original database — proven untouched

| Metric | Value |
|---|---|
| tables / views / triggers / CHECKs | 15 / 2 / 16 / 6 |
| original rows | 104 |
| migration objects present | 0 |
| content digest | `42285b6097d4b84fc3323f306cf44031e8c621433697464b9265894ced9565cb` (identical to the pre-Phase-2 capture) |

## 5. Decision required (I have not improvised)

### Option A — recommended

Relax the trigger-creation check globally on this development server, once, as
root:

```sql
SET PERSIST log_bin_trust_function_creators = 1;
```

- Keeps `sfc_migrator` least-privileged (no `SUPER`, no `SYSTEM_VARIABLES_ADMIN`).
- Server-wide setting; reversible with `SET PERSIST log_bin_trust_function_creators = 0;`.
- Affects this machine's MySQL instance only, and only the requirement that a
  trigger's creator hold SUPER; it does not weaken row or DDL privileges.
- Then the partial 002a must be resolved before continuing (see §6).

### Option B — not recommended

`GRANT SUPER` (or `SYSTEM_VARIABLES_ADMIN`) to `sfc_migrator`. Fixes the symptom
but hands the migration account far more power than the approved design allows.

### Option C — not recommended

Create the three triggers as `root` outside the runner. They would carry
`DEFINER=root`, the ledger would no longer reflect who executed the migration, and
it contradicts "the runner must use the dedicated migration account".

## 6. Recovery plan for 002a once a decision is made (not executed)

The partial table is empty, has no dependents, and `002b` has not run, so the two
safe paths are:

**Path 1 (recommended, clean re-apply):**
1. `DROP TABLE smart_food_supply_chain_dev.donation_status_history;` — empty, created
   seconds ago, no inbound FKs, no data loss. Its 2 outbound FK constraints vanish
   with it.
2. `--resolve 002a --state failed --note "partial table dropped, clean re-apply"` is
   **not** needed; instead delete the ledger row so the runner's precondition
   (table absent) passes again:
   `DELETE FROM schema_migrations WHERE version='002a';`
3. Re-run `--file 002a` with the runner. All 4 statements then execute in order and
   the ledger records a genuine `applied`.

**Path 2 (create only the missing objects):** keep the table and execute just the
two `CREATE TRIGGER` statements from 002a, then mark the ledger `applied` with a
note. Less clean: the runner never verified the table DDL itself.

Both paths preserve the original database and the `001` result. Path 1 is preferred
because it leaves the ledger telling the truth with no manual state edit beyond
removing the failed attempt.

## 7. Evidence files

| File | Content |
|---|---|
| `reports/phase2/migration_001.log` | full runner output, 001 |
| `reports/phase2/migration_002a.log` | full runner output incl. error 1419 |
| `reports/phase2/audit_pre_primary.txt` | baseline audit of the original (exit 0) |
| `reports/phase2/audit_restore_verify.txt` | restore-copy audit (exit 0) |
| `reports/phase2/audit_pre_dev.txt` | clone audit before migration (exit 0) |
| `reports/phase2/preflight_primary.txt`, `preflight_dev.txt` | preflight results |
| `reports/phase2/pre_fingerprint_primary.txt`, `pre_fingerprint_dev.txt`, `pre_fingerprint_restore_verify.txt` | identical digests |
| `reports/phase2/restore_verified_*.txt` | restore marker |
| `reports/phase2/evidence/backup.sha256`, `backup_path.txt` | backup identity |
| `reports/phase2/evidence/package_deviation.txt` | approved-package deviation |
| `reports/phase2/evidence/original_recheck_fingerprint.txt` | original digest re-check after the failure |

---

# 8. RESOLUTION (Option A approved by the user)

Recorded after the fact; nothing above has been edited.

## 8.1 Blocker documented

MySQL 8.0.46, `log_bin = ON`, `binlog_format = ROW`,
`log_replica_updates = ON`, `log_bin_trust_function_creators = OFF` (runtime),
no pre-existing row in `performance_schema.persisted_variables`.
`ERROR 1419` on the first `CREATE TRIGGER` of 002a. This is a **server
configuration prerequisite**, not a defect in the migration SQL — the same file
applied complete and cleanly once the prerequisite was satisfied.

The variable is documented by MySQL as deprecated in favour of granting
`SYSTEM_VARIABLES_ADMIN`/`SUPER`; it was used **only** as a temporary
compatibility workaround for this MySQL 8.0 environment, and reverted.

## 8.2 Original configuration captured before any change

`reports/phase2/log_bin_trust_before.txt`: version 8.0.46, hostname `basil`,
port 3306, `log_bin=1`, `binlog_format=ROW`, `log_bin_trust_function_creators=0`,
`persisted_variables` **empty** (no entry to overwrite). Listener PID 6792 on
3306 = the previously identified `MySQL80_New` instance.

## 8.3 Enablement and verification

`reports/phase2/log_bin_trust_enabled.txt`: exact statement
`SET PERSIST log_bin_trust_function_creators = ON;` → runtime `1`,
persisted `ON`. `sfc_migrator` grants **unchanged** (still exactly the 12
database-level privileges on `smart_food_supply_chain_dev.*`; no `SUPER`, no
`SYSTEM_VARIABLES_ADMIN`, no `GRANT OPTION`).

## 8.4 Recovery performed (documented case "table + 0/1 trigger")

Preconditions re-asserted immediately before cleanup:
`SELECT DATABASE()` = `smart_food_supply_chain_dev`, 0 rows, 0 `trg_dsh_*`
triggers (nothing to DROP), 0 inbound foreign keys. Then, as `sfc_migrator`
(not root):

1. `DROP TABLE donation_status_history;` — empty, never populated.
2. `DELETE FROM schema_migrations WHERE version='002a';` — 1 row removed; the
   failed row's full contents are preserved verbatim in
   `reports/phase2/evidence/ledger_002a_verbatim.txt`.
3. Re-applied the whole file through the runner:
   `python database/phase2/run_migration.py --file 002a`.

Runner output: 9 columns, 3 CHECK constraints, 1 unique index, **2 append-only
triggers**, 0 rows, original tables still 104 → ledger `applied` (184 ms).

Evidence: `reports/phase2/recovery_002a.txt`,
`reports/phase2/migration_002a_recovery.log`.

## 8.5 Continuation and restoration

`002b, 003, 004a, 004b, 005` applied one per invocation with the variable
enabled (004b and 005 create the remaining three triggers). All five new
triggers verified with `DEFINER=sfc_migrator@localhost`
(`reports/phase2/evidence/five_triggers_verified.txt`), 21 triggers total.

Then the original configuration was restored:
`SET GLOBAL log_bin_trust_function_creators = OFF;` followed by
`RESET PERSIST IF EXISTS log_bin_trust_function_creators;` →
runtime `0`, no persisted entry, persisted list empty, binlog settings
unchanged (`reports/phase2/log_bin_trust_restored.txt`).

`006` and `007` were applied **after** the restoration, as instructed.

## 8.6 Outcome

Verdict changes from FAILED to RESOLVED. 001 and 002a–007 are all `applied`
with matching checksums; the original database remained at 104 rows and digest
`42285b60…9565cb` throughout.
