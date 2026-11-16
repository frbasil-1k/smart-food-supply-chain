# PROPOSED AUDIT-SCRIPT CHANGES (ISOLATED — NOT APPLIED)

`database/audit_db.py` has **not** been modified. Everything here is a proposed
change, kept separate so the current audit keeps working exactly as reviewed.

| File | What it is |
|---|---|
| `01_baseline_option.patch` | R8: adds `--baseline PATH`; default stays the frozen `database/schema.sql` |
| `02_decimal_precision.patch` | R7: delivered-kg observations keep DECIMAL precision instead of `CAST(... AS SIGNED)` |
| `candidate_1_baseline.py` | the original with only patch 01 applied |
| `candidate.py` | the original with both patches applied (ready to copy over when approved) |
| `build_candidate.py` | regenerates the two candidates and both diffs from the original |

The patches apply in order, from the project root:

```powershell
git apply --check database/prep_phase1/proposed/01_baseline_option.patch
git apply        database/prep_phase1/proposed/01_baseline_option.patch
git apply --check database/prep_phase1/proposed/02_decimal_precision.patch
git apply        database/prep_phase1/proposed/02_decimal_precision.patch
python database/audit_db.py --self-test      # expect 39 assertions PASS
```

`git apply` needs a repository, so run `git init` first (checklist step 2), or use
the candidate directly:

```powershell
Copy-Item database/audit_db.py database/audit_db.py.pre-baseline-patch   # keep the original
Copy-Item database/prep_phase1/proposed/candidate.py database/audit_db.py
```

## What patch 01 does (R8)

- Introduces `DEFAULT_SCHEMA_PATH` (frozen, never rewritten) and keeps
  `SCHEMA_PATH` as the active baseline.
- `set_baseline(path)` rebinds the active baseline; `--baseline PATH` calls it
  before anything is parsed or validated. A missing path exits 1.
- Prints one `BASELINE: <path> (frozen original | override via --baseline)` line
  into the report, so a saved audit report always states what it compared against.
- Nothing else changes: all seven comparison stages, all 7 invariants, all 10
  observations, the self-test, the gate self-test and the donor-impact preview are
  untouched. No check is relaxed.

## What patch 02 does (R7)

Replaces, in both delivered-kg observations:

```sql
SELECT CAST(COALESCE(SUM(i.quantity_delivered_kg),0) AS SIGNED) AS n
```
with
```sql
SELECT CAST(COALESCE(SUM(i.quantity_delivered_kg),0) AS DECIMAL(20,2)) AS n
```

`SIGNED` truncated 1.25 kg to 1, so per-driver reporting under-stated delivered
weight. `DECIMAL(20,2)` matches `delivery_item.quantity_delivered_kg`
(`decimal(8,2)`) and prints `n=1.25`.

## Verification performed in this phase (no database contacted)

- `candidate.py` parses (AST check) and `--self-test` passes: 39 assertions, 0
  failures.
- `--baseline` is honoured: pointing it at an export with the views stripped makes
  the view assertions fail, while the default still passes.
- `--baseline missing.sql` exits 1 with `ERROR: --baseline ... not found`.
- The unpatched original accepts `--baseline` and ignores it (still reports 2
  views), which proves the flag is genuinely new.
- Both patches apply cleanly in order onto a copy of `database/audit_db.py`, and
  the result is byte-identical to `candidate.py`.
- `database/audit_db.py` is unchanged: `md5 6f7dfc7eda395b8778bcfe23646faed5`.

## Not proposed here

`--baseline` does not add new checks. The nine checks suggested in
`MIGRATION_PLAN.md` §7 (history/status lag, transit-without-driver, donor
reconciliation, stale tokens, format observations, append-only guard presence) are
a separate, later change so this patch stays a minimal, reviewable diff.
