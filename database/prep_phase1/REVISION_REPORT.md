# PHASE 1 REVISION REPORT — response to the independent review

**Preparation only.** No SQL was executed, no database was contacted, no live
object or record was modified, and Phase 2 has not started. Every SQL file
remains an UNEXECUTED DRAFT.

---

## Summary of the twelve corrections

| # | Review finding | Correction made | Files |
|---|---|---|---|
| R1 | F2 combined DDL and backfill in one file | split into `002a` (table, constraints, guards) and `002b` (backfill); `002b` is a single repeatable `INSERT ... SELECT` with a five-case recovery procedure | `002a_…sql`, `002b_…sql` |
| R2 | F4 was described as split but was one file | real split: `004a` (columns, indexes, FK) and `004b` (triggers); plan, README, validation, rollback and checksums updated | `004a_…sql`, `004b_…sql` |
| R3 | UPDATE trigger revalidated the driver's current role | role checked only when attribution is newly set or changed; immutable from DELIVERED; IN_TRANSIT requires a driver; no correction workflow | `004b_…sql`, `TEST_MATRIX.md` |
| R4 | "Append-only" was only a comment | `trg_dsh_block_update` / `trg_dsh_block_delete` raise 45000; grant layer documented; UI sentence corrected (no `applied_at`) | `002a_…sql`, `RUNNER_DESIGN.md` §5, `MIGRATION_PLAN.md` §3 |
| R5 | Hashing policy ambiguous | scrypt documented as the v1 algorithm only, Argon2 explicitly unsupported; `chk_cred_token_pairing` added; 11 columns unchanged | `001_…sql` |
| R6 | Re-parenting left to the service | 005 now rejects a `donation_id` change when delivery or spoilage rows exist; API 409 specified; lock-order rule documented | `005_…sql`, `MIGRATION_PLAN.md` §3 |
| R7 | Delivered-kg truncated with `CAST(… AS SIGNED)` | proposed patch to `DECIMAL(20,2)`; 1.25 kg test case added | `proposed/02_decimal_precision.patch` |
| R8 | Fixed `SCHEMA_PATH`, no `--baseline` | proposed patch with frozen default, path validation, baseline echoed in the report | `proposed/01_baseline_option.patch` |
| R9 | Duplicate-branch test rejected any non-primary unique index | now tests only a unique index on exactly `(donation_id, recipient_branch_id)` in either column order | `validation/VALIDATION_ALL.sql` |
| R10 | Counts and sums are not a content proof | deterministic per-row SHA-256 fingerprint for all 15 original tables plus a combined digest, with truncation guard and post-batch assertions | `validation/CONTENT_FINGERPRINT.sql` |
| R11 | Ledger proposed without a runner design | `RUNNER_DESIGN.md`: ledger DDL and states, checksum policy, one-file apply, validate-before-record, partial-failure detection, per-version recovery table, rollback state | `RUNNER_DESIGN.md` |
| R12 | View security and restore procedure incomplete | `vw_donor_impact` is `SQL SECURITY INVOKER` with documented grants; full PowerShell backup/restore/verify sequence using the known MySQL bin path, no password on any command line | `007_…sql`, `README.md` §5, `RUNNER_DESIGN.md` §5, §7 |

---

## Detail and reasoning

### R1 — 002a / 002b
The failure mode was real: with `CREATE TABLE` and the backfill in one file, a
backfill error leaves the table in place, and the file cannot be re-run (1050).
Now the DDL is atomic on its own. The backfill is one `INSERT ... SELECT` joined
with `LEFT JOIN ... WHERE h.history_id IS NULL`, which is repeatable and atomic as
a single statement. To stop "exactly one snapshot per donation" from resting on a
`WHERE` clause, 002a adds a stored generated column
`reconstructed_donation_id = IF(is_reconstructed=1, donation_id, NULL)` with a
unique key: a duplicate now fails with 1062 even under concurrency, and genuine
transitions (all NULL) remain unlimited. Recovery cases A–E are written out in
the file, including the one case that needs the append-only guard temporarily
removed (a wrong snapshot), with an explicit instruction to delete only
`is_reconstructed = 1` rows.

### R2 — real 004 split
`004a` adds `driver_user_id`, `scheduled_for`, the FK and the two indexes.
`004b` creates the two triggers. The sequence, dependency notes, validation
blocks (`V004a-*`, `V004b-*`), rollback steps (4b then 4a) and checksums all
follow the split; the old combined file is deleted.

### R3 — trigger semantics
The corrected UPDATE trigger has three ordered guards:

1. `OLD.delivery_status = 'DELIVERED'` and the attribution differs → reject.
   NULL-safe (`<=>`), so the five legacy NULL rows can still be updated.
2. Role checked **only** when `NOT (NEW.driver_user_id <=> OLD.driver_user_id)`.
   An unrelated update on a row whose driver later changed role now passes — the
   exact contradiction the review identified.
3. `NEW.delivery_status = 'IN_TRANSIT'` with no driver → reject.

The insert trigger applies rules 2 and 3. No correction workflow is built: there
is no attribution-history table to record actor, time and reason, so permitting
an override would be an unaudited edit. The file specifies the future design
(`delivery_driver_correction` + a manager-scoped trigger) rather than shipping a
silent hole.

One deliberate limit, stated rather than hidden: a change between `IN_TRANSIT`
and `DELIVERED` is still possible in the database. Freezing at `IN_TRANSIT` would
block a legitimate mid-trip swap with no correction path; the service requires the
same driver across that transition and test F4-11b covers it.

### R4 — append-only
Chose triggers (the review allowed either). Deciding factor: a grant mistake is
silent, while a trigger fails loudly. The grant layer is specified in
RUNNER_DESIGN §5b as a database-wide `SELECT, INSERT` baseline plus per-table
`UPDATE, DELETE`, with `donation_status_history` in neither list and no `DROP` —
so `TRUNCATE`, which bypasses row triggers, is out of the application's reach. Both
limits are documented, and
the UI sentence is now exactly *"State observed when history tracking began;
earlier transitions were not recorded."* — no timestamp, because no timestamp is
stored.

### R5 — hashing policy
scrypt is now described as **the v1 algorithm**, and the file states that neither
the backend nor the audit supports Argon2 in v1, so nothing claims compatibility.
No `CHECK` was added for the hash prefix (policy, not structure; the audit's
`cred_non_scrypt_hash` invariant already fails loudly). The token-pairing CHECK is
the one structural addition; the table still has **11 columns**.

### R6 — re-parenting
The trigger checks `NOT (NEW.donation_id <=> OLD.donation_id)`, then whether any
`delivery_item` or `spoilage_record` row references the item, and raises 45000.
`EXISTS` is used directly (no counter variables). Re-parenting an item with no
references stays legal — nothing can be corrupted, and data-entry correction must
remain possible. `delivery_item_same_donation` remains the audit backstop. The
API 409 payload is specified so the user never sees a raw 1644. Lock order is
documented: `SELECT … FOR UPDATE` on the `donation_item` row **before** reading
children, because a plain SELECT in REPEATABLE READ can read a stale snapshot.

### R7 / R8 — audit patches
Both changes are isolated in `proposed/` as ordered unified diffs, a staged
candidate, a final candidate, and a reproducible build script. Verification done
here, with no database: candidate parses; `--self-test` passes 39/39; an alternate
baseline without views makes the view assertions fail (so the flag is honoured);
a missing baseline path exits 1; the **unpatched** original accepts `--baseline`
and ignores it, proving the flag is new; both patches apply cleanly in order and
produce a file byte-identical to `candidate.py`; `database/audit_db.py` is
unmodified (md5 `6f7dfc7eda395b8778bcfe23646faed5`).

### R9 — duplicate-branch test
The prohibited thing is a unique key on exactly `(donation_id, recipient_branch_id)`.
The query now groups `information_schema.statistics` by index and compares the
ordered column list against that pair in either order, so an unrelated legitimate
unique index can never fail the test. A companion query lists the unique indexes
that do exist (only `PRIMARY`) for transparency.

### R10 — exact content proof
Counts and sums cannot prove equality. `validation/CONTENT_FINGERPRINT.sql`
hashes every row of all 15 original tables:

- per row: `SHA2(CONCAT_WS(0x1f, IFNULL(HEX(col),'<NULL>'), …), 256)` — HEX makes
  types comparable, `'<NULL>'` is provably distinct from any HEX output, so a NULL
  can never masquerade as a value;
- per table: `SHA2` over the row hashes sorted ascending — order- and
  engine-independent;
- a `not_truncated` guard (`concatenated_chars = 64 * n`) so a silent
  `group_concat_max_len` truncation cannot be mistaken for a fingerprint;
- one combined digest for a one-line comparison.

The column list for `donation` and `delivery` is the **original** pre-migration
set, so the new columns do not disturb the comparison — that is what lets the same
file prove "the original 104 records are unchanged" on both sides. Post-batch
assertions then state the intended deltas: 5 snapshots / 5 donations, 5/5/5 NULL
pickup, 5/5 NULL driver and schedule.

### R11 — runner and ledger
`RUNNER_DESIGN.md` specifies the ledger (`started`/`applied`/`failed`/
`rolled_back`), checksum immutability, one-file-per-invocation, stop-at-first-error,
validate-before-record, and an object probe per file so a `started` row can be
resolved to "not started", "partial" or "actually complete". The recovery table
lists, per version, the diagnosis query and the exact action — and the rule that
partial DDL is never blindly re-run. Rollback records `rolled_back`, so the ledger
never claims a reverted migration is in effect. Not implemented, as instructed.

### R12 — view security and restore
`vw_donor_impact` is `SQL SECURITY INVOKER`: no definer account, no hidden
escalation, no dependence on root. Grants are stated in RUNNER_DESIGN §5b and the
example account is a documented placeholder, not a secret. README §5 now has the
full PowerShell sequence (dump → create scratch DB → restore → audit → fingerprint
→ cleanup) using `C:\Program Files\MySQL\MySQL Server 8.0\bin`, with the password
supplied by prompt or a local option file and never as a command-line argument.
Noted in passing: the two existing views are `DEFINER=root@localhost`; that is a
pre-existing elevation, left unchanged and recorded as open question 10.

---

## Synchronisation check (Deliverable 4 of the review brief)

| Pair | Agrees? |
|---|---|
| SQL files ↔ sequence in README/plan | yes: 000, 001, 002a, 002b, 003, 004a, 004b, 005, 006, 007 |
| Preflight object guards ↔ objects actually created | yes (P3–P5 name every new object) |
| Validation block names ↔ migration names | yes (`V001`, `V002a`, `V002b`, `V003`, `V004a`, `V004b`, `V005`, `V006`, `V007`) |
| Rollback order ↔ dependency order | yes (007 → 001, 004b before 004a, 002b before 002a) |
| Trigger names in SQL ↔ preflight/validation/rollback | yes (`trg_dsh_block_update/delete`, `trg_delivery_driver_insert/update`, `trg_donation_item_update_guard`) |
| CHECK names in SQL ↔ validation | yes (`chk_cred_lock_consistency`, `chk_cred_token_pairing`, `chk_dsh_*`, `chk_temperature_range`) |
| Column count claim (11) ↔ 001 | yes |
| Grants referenced by 002a/007 ↔ RUNNER_DESIGN §5a/§5b | yes |
| Audit baseline workflow ↔ proposed patch | yes (`DEFAULT_SCHEMA_PATH` frozen, `--baseline` override, post-migration export) |
| Fingerprint column lists ↔ original 86 columns | yes (5+8+8+6+4+4+6+2+7+8+6+6+4+6+6 = 86) |
| File names ↔ MANIFEST.sha256 | generated last, after every edit |

---

## Second review — grant-model corrections

Two privilege-design errors were found after the first revision. Both are
corrected; no migration SQL changed, because neither issue was in the DDL — it was
in the privilege contract the migrations assume.

### C1 — runner privileges were incomplete

The runner grant omitted `TRIGGER` and `CREATE VIEW`. Without them the batch
cannot run at all: 002a, 004b and 005 create triggers, and 007 creates a view.
`CREATE` does not cover `CREATE VIEW`, and `DROP` does not cover `DROP TRIGGER`
(a trigger drop additionally requires `TRIGGER` on its table), so the omission
would have surfaced as a mid-batch permission failure — precisely the partial
state the runner design exists to avoid.

The grant is now:

```sql
GRANT ALTER, CREATE, DROP, INDEX, REFERENCES, TRIGGER, CREATE VIEW,
      INSERT, SELECT, UPDATE, DELETE
   ON smart_food_supply_chain.* TO 'sfc_migrator'@'localhost';
```

Sufficiency was re-checked file by file and is tabulated in RUNNER_DESIGN §5a:
`CREATE` (001, 002a, ledger bootstrap), `ALTER` (003, 004a, 006, rollback),
`DROP` (rollback, partial-object repair), `INDEX` (004a), `REFERENCES` (001,
002a, 004a), `TRIGGER` (002a, 004b, 005), `CREATE VIEW` (007), `INSERT` (002b,
ledger), `SELECT` (the 002b read, trigger bodies, view creation, ledger),
`UPDATE` (ledger state transitions), `DELETE` (002b recovery case D, rollback data
steps). Deliberately withheld: `GRANT OPTION`, `CREATE USER`, `SUPER`,
`SYSTEM_VARIABLES_ADMIN`, `CREATE ROUTINE`, `EXECUTE`, `EVENT`, and `FILE` — the
optional `INTO OUTFILE` export snippets in `ROLLBACK_ALL.sql` are manual DBA
statements, not runner steps.

### C2 — the `sfc_app` design relied on an impossible `REVOKE`

The previous draft granted `SELECT, INSERT, UPDATE, DELETE ON db.*` and then ran
`REVOKE UPDATE, DELETE ON db.donation_status_history`. That cannot work:

- **Privileges are additive.** The effective set is the union of database-wide,
table-level and column-level grants. MySQL has no deny rule and no scope
precedence, so a narrower grant can add rights but never subtract them.
- **There is nothing at table level to revoke.** `REVOKE ... ON db.table` removes a
  privilege granted *on that table*. When the right came from `ON db.*`, no
  table-level grant exists and the statement fails with
  `ER_NONEXISTING_TABLE_GRANT` (1147) / `ER_NONEXISTING_GRANT` (1141) — leaving the
  wildcard right intact.
- **Order is irrelevant**, and a later re-run of the wildcard `GRANT` would silently
  restore anything that had been removed.

The design is now inverted, which is the only faithful way to express it:

```sql
GRANT SELECT, INSERT ON smart_food_supply_chain.* TO 'sfc_app'@'localhost';

-- 12 statements, one table each: MySQL allows only ONE privilege level per GRANT,
-- so a comma-separated table list is a syntax error (1064), not a shorthand.
GRANT UPDATE ON smart_food_supply_chain.organization    TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.branch          TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.app_user        TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.user_credential TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.route           TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.coverage_area   TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.food_category   TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.donation        TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.donation_item   TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.delivery        TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.spoilage_record TO 'sfc_app'@'localhost';
GRANT UPDATE ON smart_food_supply_chain.delivery_review TO 'sfc_app'@'localhost';

-- 3 statements, one table each.
GRANT DELETE ON smart_food_supply_chain.route_assignment TO 'sfc_app'@'localhost';
GRANT DELETE ON smart_food_supply_chain.dependent        TO 'sfc_app'@'localhost';
GRANT DELETE ON smart_food_supply_chain.delivery_item    TO 'sfc_app'@'localhost';
```

`donation_status_history` appears in neither list, so there is no `UPDATE` or
`DELETE` to revoke in the first place. The append-only triggers from 002a are kept
as an independent second layer: even a future over-grant (someone re-adding
`UPDATE ON db.*`) still fails with 1644.

The distinction is now a test rather than a claim (`TEST_MATRIX.md` G-01…G-09): an
`UPDATE` on history as `sfc_app` must fail with **1142 (command denied)**; if it
fails with 1644, the grant layer has regressed and only the trigger saved it.

Consequential choices, documented rather than silent: no `UPDATE` on
`inspection_log` (an inspection record is a historical fact; correction needs its
own auditable workflow), no `DELETE` on `donation`/`delivery`/`app_user` (rows are
cancelled or deactivated, never removed), and no `DROP` for `sfc_app` (so no
`TRUNCATE`). Residual limit: the database-wide `INSERT` also lets the app insert
into `schema_migrations`; hardening options (separate metadata schema, or
per-table `SELECT`/`INSERT`) are recorded in RUNNER_DESIGN §5d rather than assumed
away.

### Files changed by this second review

`RUNNER_DESIGN.md` (§5 rewritten as 5a/5b/5c/5d, §8 extended),
`002a_donation_status_history.sql` (grant comment corrected),
`007_vw_donor_impact.sql` (grant comment corrected),
`MIGRATION_PLAN.md` (§3 grant wording for 002a and 007), `TEST_MATRIX.md` (R12-04/05
updated, G-01…G-09 added), `REVISION_REPORT.md` (this section), `MANIFEST.sha256`
and the ZIP regenerated. No migration DDL, no validation query and no rollback step
changed, because no privilege error had reached them.

---

## Unresolved design problems (stated, not hidden)

1. **No attribution-correction workflow.** Deliberate: no history table exists to
   record actor/time/reason. Design proposed, not built.
2. **`IN_TRANSIT` → `DELIVERED` driver change is permitted by the database.**
   Service-enforced only (F4-11b). Freezing earlier has no safe correction path.
3. **`TRUNCATE` bypasses the append-only triggers.** Mitigated by grants (no
   `DROP`); detected by the audit, not prevented by the schema.
4. **Existing views are `DEFINER=root`.** Left as-is; open question 10.
5. **Re-parenting an unallocated item is allowed.** Intentional.
6. **006 aborts if existing readings are out of band.** By design: a data question
   must be reviewed, not accommodated by widening the band.
7. **No SQL has ever been parsed by MySQL.** Syntax, `DELIMITER` handling and
   CHECK/trigger behaviour are unproven until run on `smart_food_supply_chain_dev`
   — which does not exist yet and must not be created in this phase.
8. **Nine proposed audit checks are not implemented** (history lag, transit
   without driver, donor reconciliation, stale tokens, format observations,
   append-only guard presence). They are suggestions for the next audit revision.
9. **The runner is a design, not code.** Phase 2 implements it.
10. **`chk_cred_token_pairing` requires the service to set or clear both token
    fields in one UPDATE.** Documented; a split write now fails loudly with 3819.
