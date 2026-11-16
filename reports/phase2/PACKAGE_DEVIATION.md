# Package deviation from the approved Phase 1 revision

The approved archive `phase1_migration_prep_revision.zip` (156,430 bytes, 27 entries,
24 manifest entries) is **preserved untouched**. It remains the record of what was
approved.

The Phase 2 brief mandated documentation corrections that touch one file inside
that package, so the working copy no longer matches the approved manifest in
exactly one place.

## Deviation

| File | Approved SHA-256 | Current SHA-256 |
|---|---|---|
| `database/prep_phase1/RUNNER_DESIGN.md` | `d6b076a29aff4adab1d273135fd31ad52172a5a138571ae7addabc4e13d69dcc` | see `reports/phase2/evidence/package_deviation.txt` |

Everything else is byte-identical to the approved manifest: 23 of 24 entries
match, including **all 13 SQL files** (9 migrations, preflight, validation,
content fingerprint, rollback).

## Why this file changed (all mandated by the Phase 2 brief, §4)

1. **§5a** — `sfc_migrator` grants now target `smart_food_supply_chain_dev.*`.
   The account must not hold any privilege on the original database.
2. **§6** — the post-migration structure export is taken from
   `smart_food_supply_chain_dev`, never from the original.
3. **§8** — the outdated rule "the runner must never touch
   `smart_food_supply_chain_dev`" replaced with: the runner may operate only on the
   approved `_dev` target and must never touch the original
   `smart_food_supply_chain`.
4. **§5b** — `sfc_app` is explicitly not created in Phase 2, and the
   database-wide `INSERT` limitation (it would allow writing to
   `schema_migrations`) is recorded as a prerequisite for that account.
5. **§3** — one line making the runner's target database explicit.

No migration DDL, validation query, rollback step, test expectation or proposed
audit patch was modified.

## Consequences and handling

- `sha256sum -c database/prep_phase1/MANIFEST.sha256` inside the working copy now
  reports exactly one failure: `RUNNER_DESIGN.md`. That is expected and must not be
  "fixed" by rewriting the approved manifest or by reverting the mandated
  corrections.
- Execution safety is unaffected: the runner verifies the SHA-256 of each of the
  nine migration files independently against the ledger, and those nine files are
  unchanged.
- Decision needed from you after Phase 2: either (a) keep the approved ZIP as the
  signed record and carry this deviation note forward, or (b) re-seal a new archive
  (for example `phase1_migration_prep_revision_phase2docs.zip`) with a regenerated
  manifest. Option (a) is what is implemented; (b) is a one-command follow-up if you
  prefer a self-consistent archive.
