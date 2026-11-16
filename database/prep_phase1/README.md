# PHASE 1 — MIGRATION PREPARATION (REVISED, UNEXECUTED DRAFTS)

> **STATUS: DRAFT ONLY. NOTHING IN THIS DIRECTORY HAS BEEN RUN.**
> No table was created or altered, no trigger or view was added, no row was
> written, and `smart_food_supply_chain_dev` was not created. The audit script
> and the export have not been modified; proposed audit changes are isolated in
> `proposed/`.

Project: **Smart Food Supply Chain & Surplus Redistribution System**
Target: MySQL Server 8.0.46, InnoDB, utf8mb4 / utf8mb4_0900_ai_ci
Primary database: `smart_food_supply_chain` (104 rows, must be preserved)

---

## 1. Read this first

1. `database/schema.sql` is a **reference export containing `DROP TABLE` statements**.
   Never import it into the live database. It stays frozen as the pre-migration
   baseline that `database/audit_db.py` compares against.
2. These drafts are applied **only** through the approved runner (design:
   `RUNNER_DESIGN.md`), **only** after a backup that has been restore-verified.
3. Every migration is **forward-only**. Rollback lives in
   `rollback/ROLLBACK_ALL.sql` and is not automatic — read its warnings first.
4. Nothing here backfills historical facts. Legacy `NULL` means "not recorded".
5. The package was revised after review; every correction is listed in
   `REVISION_REPORT.md`.

---

## 2. Directory contents

| File | Purpose | DDL? | Reversible |
|---|---|---|---|
| `README.md` | index, order, rules, backup/restore | no | n/a |
| `REVISION_REPORT.md` | R1–R12: what the review found and what changed | no | n/a |
| `MIGRATION_PLAN.md` | full specification, decisions, audit integration, API impact, checklist | no | n/a |
| `TEST_MATRIX.md` | positive/negative tests, SQL + API + audit layers | no | n/a |
| `RUNNER_DESIGN.md` | Phase 2 runner, ledger, partial-failure recovery, grants | no | n/a |
| `MANIFEST.sha256` | checksums of every file in this package | no | n/a |
| `000_preflight.sql` | read-only pre-checks and legacy-NULL populations | **no** | n/a |
| `001_user_credential.sql` | F1 — auth table, scrypt v1, token pairing | yes | drop table (loses hashes) |
| `002a_donation_status_history.sql` | F2a — history table + append-only guards | yes | drop table (loses history) |
| `002b_backfill_donation_history.sql` | F2b — 5 reconstructed snapshots (repeatable) | DML only | re-run safe |
| `003_donation_pickup.sql` | F3 — nullable pickup columns | yes | drop columns (loses data) |
| `004a_delivery_attribution.sql` | F4a — driver_user_id, scheduled_for, FK, indexes | yes | drop (loses data) |
| `004b_delivery_driver_triggers.sql` | F4b — role-on-change, immutability, transit gate | yes | drop triggers — full |
| `005_donation_item_update_guard.sql` | F5 — shrink guard + re-parent guard | yes | drop trigger — full |
| `006_inspection_temperature_check.sql` | F8 — plausibility CHECK | yes | drop check — full |
| `007_vw_donor_impact.sql` | donor impact view (**review-gated**) | yes | drop view — full |
| `rollback/ROLLBACK_ALL.sql` | reverse order, per-object, with recovery notes | yes | n/a |
| `validation/VALIDATION_ALL.sql` | per-migration verification queries | **no** | n/a |
| `validation/CONTENT_FINGERPRINT.sql` | exact per-row SHA-256 proof (R10) | **no** | n/a |
| `proposed/` | audit-script patch + candidate, isolated | no | n/a |

---

## 3. Recommended execution order

```
000 preflight (read-only) + CONTENT_FINGERPRINT capture (pre)
 └─ backup → restore-verify → fingerprint the restored copy
     ├─ 001 user_credential              independent
     ├─ 002a history table + guards      ┐ split: DDL commits separately from
     ├─ 002b legacy snapshots            ┘ the backfill, so neither can strand the other
     ├─ 003 donation pickup columns      independent
     ├─ 004a delivery attribution        ┐ split: a trigger mistake cannot leave
     ├─ 004b delivery driver triggers    ┘ a partly-applied ALTER behind
     ├─ 005 donation_item update guard   independent
     ├─ 006 temperature CHECK            independent
     └─ 007 vw_donor_impact              review-gated, last
```

**Why this order.** 001–006 have no SQL-level dependencies on each other; the
order is risk-based: additive structure first, behavioural objects (triggers,
CHECK) later, reporting view last. 002b must follow 002a; 004b must follow 004a.
Nothing depends on `vw_donor_sustainability` or `vw_driver_performance`, which
are preserved untouched.

---

## 4. Rules the runner must enforce

1. Read files in this exact order; **stop at the first error** — never `--force`.
2. Record every applied file in the `schema_migrations` ledger
   (`version`, `name`, `checksum`, `started_at`, `applied_at`, `state`).
3. Refuse to run if a file's checksum differs from the recorded one.
4. Refuse to run if a precondition query in the file returns a non-zero count.
5. Use the `mysql` CLI (or a splitter that understands `DELIMITER`) because
   trigger bodies contain `;`.
6. Credentials come from a local, non-versioned option file
   (`--defaults-extra-file`); **never** on a command line, in source, or in chat.
7. After each file: run the matching `V0NN` block, then record the ledger entry.
   Only after the whole batch: run the full audit against the post-migration
   baseline (MIGRATION_PLAN §7, RUNNER_DESIGN §6).
8. Never re-run DDL blindly after a failure — see RUNNER_DESIGN §4.

---

## 5. Backup and restore verification (Windows PowerShell)

MySQL binaries (not on PATH):

```powershell
$MYSQL = "C:\Program Files\MySQL\MySQL Server 8.0\bin"
$Stamp = Get-Date -Format "yyyyMMdd_HHmm"
$Backup = "C:\backup\sfc_before_migrations_$Stamp.sql"
```

**1. Backup.** Never put a password on the command line. Either let the client
prompt, or use a local option file that is not in the repository:

```powershell
# Option A - interactive prompt (simplest, no secret stored anywhere)
& "$MYSQL\mysqldump.exe" -u root -p --single-transaction --routines --triggers `
    --events --set-gtid-purged=OFF --no-tablespaces `
    --result-file="$Backup" smart_food_supply_chain

# Option B - local option file, e.g. %USERPROFILE%\.my_sfc.cnf containing
#   [client]
#   user=root
#   password=...
#   host=127.0.0.1
& "$MYSQL\mysqldump.exe" --defaults-extra-file="$env:USERPROFILE\.my_sfc.cnf" `
    --single-transaction --routines --triggers --events `
    --set-gtid-purged=OFF --no-tablespaces `
    --result-file="$Backup" smart_food_supply_chain
```

Confirm the file is non-trivial before continuing:

```powershell
Get-Item $Backup | Select-Object FullName, Length
Select-String -Path $Backup -Pattern "CREATE TABLE ``donation``" | Select-Object -First 1
```

**2. Create the scratch database and restore into it.**

```powershell
& "$MYSQL\mysql.exe" -u root -p -e "CREATE DATABASE sfc_restore_verify CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
& "$MYSQL\mysql.exe" -u root -p sfc_restore_verify -e "SELECT DATABASE(), @@sql_mode;"
# restore (the dump contains DROP TABLE IF EXISTS for the 15 tables, which is why
# this must target sfc_restore_verify and never the live schema name)
cmd /c "`"$MYSQL\mysql.exe`" -u root -p sfc_restore_verify < `"$Backup`""
```

**3. Prove the restore matches the source before trusting the backup.**

```powershell
$env:DB_NAME = "sfc_restore_verify"
$env:DB_USER = "root"
# prompt for the password into an environment variable - do not pass it as an argument
$env:DB_PASSWORD = Read-Host "MySQL password" -AsSecureString |
    ForEach-Object { [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($_)) }
python database/audit_db.py --out reports\audit_restore_verify.txt
$LASTEXITCODE
```

Expect exit 0, 7/7 invariants, 104 rows. Then the strongest check: run
`validation/CONTENT_FINGERPRINT.sql` on **both** the live database and the
restored copy and compare the combined digest — they must be identical.

**4. Clean up** only after the batch is accepted:

```powershell
& "$MYSQL\mysql.exe" -u root -p -e "DROP DATABASE sfc_restore_verify;"
Remove-Item Env:DB_PASSWORD
```

---

## 6. Content fingerprint workflow (R10)

Counts and sums cannot prove "the same 104 records". Before the batch:

```
mysql> source database/prep_phase1/validation/CONTENT_FINGERPRINT.sql
```

Save the 15 per-table fingerprints **and** the combined digest. After the batch,
run the same file again and compare byte for byte. The query hashes the ORIGINAL
column set of `donation` and `delivery`, so the new columns do not change it —
that is what makes the comparison meaningful.

---

## 7. What this directory deliberately does not contain

- No `DROP DATABASE`, no `TRUNCATE`, no blanket `DELETE` (only the documented,
  trigger-gated recovery step in ROLLBACK_ALL step 7).
- No `ALTER` of an existing constraint or trigger.
- No backfill of `delivery.driver_user_id`.
- No invented pickup addresses, contacts, timestamps, actors or passwords.
- No `CREATE TABLE IF NOT EXISTS` for the migration objects (state is verified by
  preconditions; the ledger bootstrap is the only exception, and it lives in the
  runner, not in a migration).
- No application code, no data generator, no dev database, no runner
  implementation.
- No modified `audit_db.py`: proposed changes are in `proposed/` only.
