"""Phase 2 migration runner — target-locked to smart_food_supply_chain_dev.

Implements only what this project needs: one file per invocation, checksum
verification, a ledger with started/applied/failed/rolled_back states, per-file
precondition and validation checks, and hard refusal to touch the original
database.

It deliberately does NOT: generate SQL, split statements (the mysql client handles
DELIMITER), retry, continue after errors, or run a rollback.

Usage
-----
    python database/phase2/run_migration.py --defaults-extra-file C:\\path\\sfc.cnf --bootstrap
    python database/phase2/run_migration.py --defaults-extra-file C:\\path\\sfc.cnf --file 001
    python database/phase2/run_migration.py --defaults-extra-file C:\\path\\sfc.cnf --status
    python database/phase2/run_migration.py --defaults-extra-file C:\\path\\sfc.cnf --probe 002a
    python database/phase2/run_migration.py --defaults-extra-file C:\\path\\sfc.cnf \\
        --resolve 004b --state failed --note "reviewed: no trigger created"

Credentials: only ever read by the mysql client from the option file. This script
never sees, stores or prints a password, and refuses an option file inside the
project directory.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

MYSQL = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
HOST = "127.0.0.1"
PORT = "3306"

TARGET_DB = "smart_food_supply_chain_dev"
FORBIDDEN_DB = "smart_food_supply_chain"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DIR = PROJECT_ROOT / "database" / "prep_phase1"

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `version`     VARCHAR(20)  NOT NULL,
  `name`        VARCHAR(120) NOT NULL,
  `checksum`    CHAR(64)     NOT NULL,
  `state`       ENUM('started','applied','failed','rolled_back')
                             NOT NULL DEFAULT 'started',
  `started_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `applied_at`  DATETIME     NULL DEFAULT NULL,
  `finished_at` DATETIME     NULL DEFAULT NULL,
  `duration_ms` INT UNSIGNED NULL DEFAULT NULL,
  `note`        VARCHAR(255) NULL DEFAULT NULL,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""

# Row total of the 15 original tables. Must never change.
ORIGINAL_TABLES = [
    "organization", "branch", "app_user", "route", "coverage_area",
    "route_assignment", "donation", "food_category", "donation_item",
    "inspection_log", "dependent", "delivery", "delivery_item",
    "spoilage_record", "delivery_review",
]
ORIGINAL_ROWS_SQL = "SELECT " + " + ".join(
    f"(SELECT COUNT(*) FROM `{t}`)" for t in ORIGINAL_TABLES) + " AS n"

# version -> file, preconditions, validation checks, object probe
# Every check is (label, sql, expected_int). Preconditions must already hold;
# validation checks must hold AFTER the file runs.
MIGRATIONS: dict[str, dict] = {
    "001": {
        "file": "001_user_credential.sql",
        "purpose": "USER_CREDENTIAL table, scrypt v1, token pairing",
        "pre": [
            ("table absent",
             "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() "
             "AND table_name='user_credential'", 0),
            ("columns absent",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='user_credential'", 0),
        ],
        "post": [
            ("11 columns",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='user_credential'", 11),
            ("2 CHECK constraints",
             "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() "
             "AND table_name='user_credential' AND constraint_type='CHECK' AND enforced='YES'", 2),
            ("1 unique index",
             "SELECT COUNT(DISTINCT index_name) FROM information_schema.statistics "
             "WHERE table_schema=DATABASE() AND table_name='user_credential' AND non_unique=0 "
             "AND index_name<>'PRIMARY'", 1),
            ("zero credentials invented", "SELECT COUNT(*) FROM user_credential", 0),
            ("15 users still without credentials",
             "SELECT COUNT(*) FROM app_user u LEFT JOIN user_credential c USING (user_id) "
             "WHERE c.user_id IS NULL", 15),
        ],
        "probe": ("object count",
                  "SELECT (SELECT COUNT(*) FROM information_schema.tables WHERE "
                  "table_schema=DATABASE() AND table_name='user_credential') + "
                  "(SELECT COUNT(*) FROM information_schema.columns WHERE "
                  "table_schema=DATABASE() AND table_name='user_credential')"),
    },
    "002a": {
        "file": "002a_donation_status_history.sql",
        "purpose": "history table, one-snapshot guarantee, append-only triggers",
        "pre": [
            ("table absent",
             "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() "
             "AND table_name='donation_status_history'", 0),
            ("append-only triggers absent",
             "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
             "AND trigger_name LIKE 'trg_dsh_%'", 0),
        ],
        "post": [
            ("9 columns",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='donation_status_history'", 9),
            ("3 CHECK constraints",
             "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() "
             "AND table_name='donation_status_history' AND constraint_type='CHECK' AND enforced='YES'", 3),
            ("unique one-snapshot index",
             "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE() "
             "AND table_name='donation_status_history' AND index_name='uq_dsh_one_reconstructed'", 1),
            ("2 append-only triggers",
             "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
             "AND trigger_name LIKE 'trg_dsh_%'", 2),
            ("empty before backfill", "SELECT COUNT(*) FROM donation_status_history", 0),
        ],
        "probe": ("trigger and table count",
                  "SELECT (SELECT COUNT(*) FROM information_schema.tables WHERE "
                  "table_schema=DATABASE() AND table_name='donation_status_history') + "
                  "(SELECT COUNT(*) FROM information_schema.triggers WHERE "
                  "trigger_schema=DATABASE() AND trigger_name LIKE 'trg_dsh_%')"),
    },
    "002b": {
        "file": "002b_backfill_donation_history.sql",
        "purpose": "five reconstructed legacy snapshots",
        "pre": [
            ("no snapshots yet",
             "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1", 0),
            ("five donations to cover", "SELECT COUNT(*) FROM donation", 5),
        ],
        "post": [
            ("5 reconstructed snapshots",
             "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1", 5),
            ("5 donations covered",
             "SELECT COUNT(DISTINCT donation_id) FROM donation_status_history "
             "WHERE is_reconstructed=1", 5),
            ("all donations covered",
             "SELECT COUNT(*) FROM donation d WHERE NOT EXISTS (SELECT 1 FROM "
             "donation_status_history h WHERE h.donation_id=d.donation_id)", 0),
            ("no fabricated timestamps",
             "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1 "
             "AND changed_at IS NOT NULL", 0),
            ("no actors on snapshots",
             "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1 "
             "AND changed_by_user_id IS NOT NULL", 0),
            ("exact approved note",
             "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1 "
             "AND note='State observed when history tracking began; earlier transitions "
             "were not recorded'", 5),
        ],
        "probe": ("snapshot count",
                  "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1"),
    },
    "003": {
        "file": "003_donation_pickup.sql",
        "purpose": "nullable pickup address, pincode, contact",
        "pre": [
            ("columns absent",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='donation' AND column_name IN "
             "('pickup_address','pickup_pincode','pickup_contact')", 0),
        ],
        "post": [
            ("3 columns, all nullable",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='donation' AND column_name IN "
             "('pickup_address','pickup_pincode','pickup_contact') AND is_nullable='YES'", 3),
            ("5 legacy addresses NULL",
             "SELECT COUNT(*) FROM donation WHERE pickup_address IS NULL", 5),
            ("5 legacy pincodes NULL",
             "SELECT COUNT(*) FROM donation WHERE pickup_pincode IS NULL", 5),
            ("5 legacy contacts NULL",
             "SELECT COUNT(*) FROM donation WHERE pickup_contact IS NULL", 5),
        ],
        "probe": ("new column count",
                  "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
                  "AND table_name='donation' AND column_name IN "
                  "('pickup_address','pickup_pincode','pickup_contact')"),
    },
    "004a": {
        "file": "004a_delivery_attribution.sql",
        "purpose": "driver_user_id, scheduled_for, FK and indexes",
        "pre": [
            ("columns absent",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='delivery' AND column_name IN ('driver_user_id','scheduled_for')", 0),
        ],
        "post": [
            ("2 nullable columns",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='delivery' AND column_name IN ('driver_user_id','scheduled_for') "
             "AND is_nullable='YES'", 2),
            ("fk_delivery_driver present",
             "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() "
             "AND table_name='delivery' AND constraint_name='fk_delivery_driver'", 1),
            ("2 new indexes",
             "SELECT COUNT(DISTINCT index_name) FROM information_schema.statistics "
             "WHERE table_schema=DATABASE() AND table_name='delivery' AND index_name IN "
             "('idx_delivery_driver_status','idx_delivery_scheduled')", 2),
            ("5 legacy drivers NULL",
             "SELECT COUNT(*) FROM delivery WHERE driver_user_id IS NULL", 5),
            ("5 legacy schedules NULL",
             "SELECT COUNT(*) FROM delivery WHERE scheduled_for IS NULL", 5),
            ("no forbidden unique pair",
             "SELECT COUNT(*) FROM (SELECT index_name FROM information_schema.statistics "
             "WHERE table_schema=DATABASE() AND table_name='delivery' AND non_unique=0 "
             "GROUP BY index_name HAVING GROUP_CONCAT(column_name ORDER BY seq_in_index) IN "
             "('donation_id,recipient_branch_id','recipient_branch_id,donation_id')) x", 0),
        ],
        "probe": ("new column count",
                  "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
                  "AND table_name='delivery' AND column_name IN ('driver_user_id','scheduled_for')"),
    },
    "004b": {
        "file": "004b_delivery_driver_triggers.sql",
        "purpose": "role-on-change, immutability after DELIVERED, IN_TRANSIT gate",
        "pre": [
            ("triggers absent",
             "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
             "AND trigger_name IN ('trg_delivery_driver_insert','trg_delivery_driver_update')", 0),
            ("columns present",
             "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
             "AND table_name='delivery' AND column_name IN ('driver_user_id','scheduled_for')", 2),
        ],
        "post": [
            ("2 triggers",
             "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
             "AND trigger_name IN ('trg_delivery_driver_insert','trg_delivery_driver_update')", 2),
            ("no wrongly attributed driver",
             "SELECT COUNT(*) FROM delivery d JOIN app_user u ON u.user_id=d.driver_user_id "
             "WHERE u.user_role<>'DRIVER'", 0),
            ("no transit without driver",
             "SELECT COUNT(*) FROM delivery WHERE delivery_status='IN_TRANSIT' "
             "AND driver_user_id IS NULL", 0),
            ("5 legacy drivers still NULL",
             "SELECT COUNT(*) FROM delivery WHERE driver_user_id IS NULL", 5),
        ],
        "probe": ("driver trigger count",
                  "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
                  "AND trigger_name IN ('trg_delivery_driver_insert','trg_delivery_driver_update')"),
    },
    "005": {
        "file": "005_donation_item_update_guard.sql",
        "purpose": "shrink guard and re-parenting guard",
        "pre": [
            ("trigger absent",
             "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
             "AND trigger_name='trg_donation_item_update_guard'", 0),
            ("no pre-existing over-allocation",
             "SELECT COUNT(*) FROM donation_item di WHERE di.quantity_kg < "
             "COALESCE((SELECT SUM(quantity_delivered_kg) FROM delivery_item "
             "WHERE food_item_id=di.food_item_id),0) + "
             "COALESCE((SELECT SUM(quantity_spoiled_kg) FROM spoilage_record "
             "WHERE food_item_id=di.food_item_id),0)", 0),
        ],
        "post": [
            ("trigger present",
             "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
             "AND trigger_name='trg_donation_item_update_guard'", 1),
            ("no over-allocation",
             "SELECT COUNT(*) FROM donation_item di WHERE di.quantity_kg < "
             "COALESCE((SELECT SUM(quantity_delivered_kg) FROM delivery_item "
             "WHERE food_item_id=di.food_item_id),0) + "
             "COALESCE((SELECT SUM(quantity_spoiled_kg) FROM spoilage_record "
             "WHERE food_item_id=di.food_item_id),0)", 0),
            ("no cross-donation allocation",
             "SELECT COUNT(*) FROM delivery_item di JOIN delivery d ON d.delivery_id=di.delivery_id "
             "JOIN donation_item i ON i.food_item_id=di.food_item_id "
             "WHERE d.donation_id<>i.donation_id", 0),
        ],
        "probe": ("guard trigger count",
                  "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
                  "AND trigger_name='trg_donation_item_update_guard'"),
    },
    "006": {
        "file": "006_inspection_temperature_check.sql",
        "purpose": "temperature plausibility CHECK (-50..150)",
        "pre": [
            ("constraint absent",
             "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() "
             "AND constraint_name='chk_temperature_range'", 0),
            ("no out-of-band readings",
             "SELECT COUNT(*) FROM inspection_log WHERE temperature_c IS NOT NULL "
             "AND (temperature_c < -50 OR temperature_c > 150)", 0),
        ],
        "post": [
            ("constraint enforced",
             "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() "
             "AND constraint_name='chk_temperature_range' AND enforced='YES'", 1),
            ("no out-of-band readings",
             "SELECT COUNT(*) FROM inspection_log WHERE temperature_c IS NOT NULL "
             "AND (temperature_c < -50 OR temperature_c > 150)", 0),
            ("5 inspection rows intact", "SELECT COUNT(*) FROM inspection_log", 5),
        ],
        "probe": ("constraint count",
                  "SELECT COUNT(*) FROM information_schema.table_constraints WHERE "
                  "table_schema=DATABASE() AND constraint_name='chk_temperature_range'"),
    },
    "007": {
        "file": "007_vw_donor_impact.sql",
        "purpose": "donor impact view (SQL SECURITY INVOKER)",
        "pre": [
            ("view absent",
             "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() "
             "AND table_name='vw_donor_impact'", 0),
            ("original views present",
             "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() "
             "AND table_name IN ('vw_donor_sustainability','vw_driver_performance')", 2),
        ],
        "post": [
            ("view exists as INVOKER",
             "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() "
             "AND table_name='vw_donor_impact' AND security_type='INVOKER'", 1),
            ("original views preserved",
             "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() "
             "AND table_name IN ('vw_donor_sustainability','vw_driver_performance')", 2),
            ("4 donor rows", "SELECT COUNT(*) FROM vw_donor_impact", 4),
            ("no negative balance",
             "SELECT COUNT(*) FROM vw_donor_impact WHERE undistributed_balance_kg < 0", 0),
            ("delivered never exceeds donated",
             "SELECT COUNT(*) FROM vw_donor_impact WHERE delivered_kg > total_donated_kg", 0),
        ],
        "probe": ("view count",
                  "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() "
                  "AND table_name='vw_donor_impact'"),
    },
}

ORDER = ["001", "002a", "002b", "003", "004a", "004b", "005", "006", "007"]


class Abort(RuntimeError):
    """A condition that must stop the run without changing anything further."""


def log(msg: str = "") -> None:
    print(msg, flush=True)


def rule(title: str) -> None:
    log(f"\n=== {title} ===")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


class Client:
    """Thin wrapper around the mysql CLI. Credentials live only in the option file."""

    def __init__(self, defaults_file: Path):
        self.defaults_file = defaults_file

    def _args(self, database: str = "") -> list[str]:
        args = [
            MYSQL,
            f"--defaults-extra-file={self.defaults_file}",
            "--protocol=TCP", "-h", HOST, "-P", PORT,
            "--default-character-set=utf8mb4",
            "--batch", "--skip-column-names",
        ]
        if database:
            args.append(database)
        return args

    def rows(self, sql: str) -> list[list[str]]:
        proc = subprocess.run(self._args(TARGET_DB) + ["-e", sql],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise Abort(f"query failed: {proc.stderr.strip()[:400]}\nSQL: {sql[:300]}")
        out = [line.split("\t") for line in proc.stdout.splitlines() if line != ""]
        return out

    def scalar(self, sql: str) -> str:
        rows = self.rows(sql)
        if not rows or not rows[0]:
            raise Abort(f"no value returned for: {sql[:200]}")
        return rows[0][0]

    def execute_file(self, path: Path) -> subprocess.CompletedProcess:
        with open(path, "rb") as handle:
            return subprocess.run(self._args(TARGET_DB),
                                  stdin=handle, capture_output=True, text=True)

    def execute(self, sql: str) -> None:
        proc = subprocess.run(self._args(TARGET_DB) + ["-e", sql],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise Abort(f"statement failed: {proc.stderr.strip()[:400]}")


def check_target(client: Client) -> None:
    """Hard guard, run before every operation."""
    name = client.scalar("SELECT DATABASE()")
    if name != TARGET_DB:
        raise Abort(f"selected database is {name!r}, expected {TARGET_DB!r}")
    if not name.endswith("_dev"):
        raise Abort(f"database {name!r} does not end in '_dev'")
    if name == FORBIDDEN_DB:
        raise Abort("refusing to operate on the original database")


def ensure_ledger(client: Client) -> None:
    client.execute(LEDGER_DDL)


def ledger_row(client: Client, version: str) -> list[str] | None:
    rows = client.rows(
        "SELECT version, name, checksum, state, COALESCE(applied_at,''), "
        "COALESCE(note,'') FROM schema_migrations WHERE version=" + quote(version))
    return rows[0] if rows else None


def set_state(client: Client, version: str, name: str, checksum: str, state: str,
              duration_ms: int | None = None, note: str = "") -> None:
    applied = "NOW()" if state == "applied" else "NULL"
    dur = "NULL" if duration_ms is None else str(duration_ms)
    note_sql = "NULL" if not note else quote(note[:255])
    client.execute(
        "INSERT INTO schema_migrations (version, name, checksum, state, applied_at, "
        f"finished_at, duration_ms, note) VALUES ({quote(version)}, {quote(name)}, "
        f"{quote(checksum)}, {quote(state)}, {applied}, NOW(), {dur}, {note_sql}) "
        "ON DUPLICATE KEY UPDATE name=VALUES(name), checksum=VALUES(checksum), "
        "state=VALUES(state), applied_at=VALUES(applied_at), "
        "finished_at=VALUES(finished_at), duration_ms=VALUES(duration_ms), "
        "note=VALUES(note)")


def run_checks(client: Client, checks: list[tuple[str, str, int]], phase: str) -> bool:
    ok = True
    for label, sql, expected in checks:
        value = client.scalar(sql)
        got = int(value) if value not in ("", "NULL", None) else None
        good = got == expected
        log(f"  [{'ok ' if good else 'FAIL'}] {phase:12} {label:42} got={got} expected={expected}")
        ok = ok and good
    return ok


def original_rows(client: Client) -> int:
    return int(client.scalar(ORIGINAL_ROWS_SQL))


def cmd_bootstrap(client: Client) -> int:
    rule("bootstrap ledger")
    check_target(client)
    ensure_ledger(client)
    log("  schema_migrations ready")
    return 0


def cmd_status(client: Client) -> int:
    rule("ledger status")
    check_target(client)
    ensure_ledger(client)
    rows = client.rows(
        "SELECT version, name, checksum, state, COALESCE(applied_at,'-'), "
        "COALESCE(duration_ms,'-'), COALESCE(note,'') FROM schema_migrations "
        "ORDER BY version")
    if not rows:
        log("  (empty ledger)")
    for r in rows:
        log(f"  {r[0]:5} {r[3]:12} {r[1]:38} {r[2][:12]}  applied={r[4]}  {r[5]}ms  {r[6]}")
    rule("file checksums vs recorded")
    for version in ORDER:
        spec = MIGRATIONS[version]
        path = MIGRATION_DIR / spec["file"]
        actual = sha256(path)
        row = ledger_row(client, version)
        if row is None:
            log(f"  {version:5} {actual[:12]}  not recorded")
        else:
            same = row[2] == actual
            log(f"  {version:5} {actual[:12]}  {'match' if same else 'MISMATCH'}"
                f"  state={row[3]}")
    return 0


def cmd_probe(client: Client, version: str) -> int:
    spec = MIGRATIONS[version]
    rule(f"object probe for {version} ({spec['file']})")
    check_target(client)
    label, sql = spec["probe"]
    log(f"  {label}: {client.scalar(sql)}")
    log("  expected after a successful apply: see the spec in RUNNER_DESIGN.md §4")
    return 0


def cmd_resolve(client: Client, version: str, state: str, note: str) -> int:
    rule(f"resolve {version} -> {state}")
    check_target(client)
    ensure_ledger(client)
    if version not in MIGRATIONS:
        raise Abort(f"unknown version {version}")
    row = ledger_row(client, version)
    if row is None:
        raise Abort(f"no ledger row for {version}; nothing to resolve")
    log(f"  current state: {row[3]}")
    spec = MIGRATIONS[version]
    label, sql = spec["probe"]
    log(f"  probe ({label}): {client.scalar(sql)}")
    set_state(client, version, spec["file"], row[2], state, None, note)
    log(f"  recorded state={state}  note={note!r}")
    return 0


def cmd_apply(client: Client, version: str) -> int:
    spec = MIGRATIONS[version]
    path = MIGRATION_DIR / spec["file"]
    checksum = sha256(path)

    rule(f"apply {version} — {spec['file']}")
    log(f"  purpose : {spec['purpose']}")
    log(f"  sha256  : {checksum}")

    check_target(client)
    ensure_ledger(client)

    row = ledger_row(client, version)
    if row is not None:
        if row[3] == "applied":
            if row[2] != checksum:
                raise Abort("file was edited AFTER being applied (checksum mismatch). "
                            "Applied migrations are immutable: create a new version.")
            log("  already applied with a matching checksum — nothing to do")
            return 0
        raise Abort(f"ledger state is {row[3]!r}; unresolved. Inspect with --probe "
                    f"{version}, then --resolve {version} after review. Do not rerun DDL.")

    log("  preconditions:")
    if not run_checks(client, spec["pre"], "precondition"):
        raise Abort("a precondition did not hold; nothing was recorded or executed")

    before_rows = original_rows(client)
    log(f"  original-table rows before: {before_rows}")

    set_state(client, version, spec["file"], checksum, "started")
    log("  ledger: started")

    started = time.time()
    proc = client.execute_file(path)
    elapsed = int((time.time() - started) * 1000)
    if proc.stdout.strip():
        for line in proc.stdout.strip().splitlines():
            log(f"    mysql> {line}")
    if proc.returncode != 0:
        set_state(client, version, spec["file"], checksum, "failed", elapsed,
                  proc.stderr.strip().splitlines()[0][:250] if proc.stderr.strip() else "sql error")
        log(f"  sql FAILED (exit {proc.returncode}):")
        for line in proc.stderr.strip().splitlines()[:8]:
            log(f"    {line}")
        log(f"  ledger: failed. Do NOT rerun. Diagnose with --probe {version}, "
            f"then apply the recovery procedure in RUNNER_DESIGN.md §4.")
        return 1

    log("  validation:")
    ok = run_checks(client, spec["post"], "validation")

    check_target(client)
    after_rows = original_rows(client)
    rows_ok = after_rows == before_rows == 104
    log(f"  original-table rows after : {after_rows} "
        f"(expected 104, unchanged: {rows_ok})")
    ok = ok and rows_ok

    if not ok:
        set_state(client, version, spec["file"], checksum, "failed", elapsed,
                  "validation did not pass")
        log("  ledger: failed (validation). Objects may exist; inspect before acting.")
        return 1

    set_state(client, version, spec["file"], checksum, "applied", elapsed)
    log(f"  ledger: applied ({elapsed} ms)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 migration runner (dev-only).")
    parser.add_argument("--defaults-extra-file", required=True,
                        help="MySQL option file holding the credentials (outside the project)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bootstrap", action="store_true", help="create the ledger table")
    group.add_argument("--status", action="store_true", help="show ledger and checksums")
    group.add_argument("--file", metavar="VERSION", help="apply exactly one migration")
    group.add_argument("--probe", metavar="VERSION", help="report object state for recovery")
    group.add_argument("--resolve", metavar="VERSION", help="set a reviewed ledger state")
    parser.add_argument("--state", choices=["applied", "failed", "rolled_back"], default="failed",
                        help="state for --resolve")
    parser.add_argument("--note", default="", help="short note recorded with --resolve")
    args = parser.parse_args()

    defaults_file = Path(args.defaults_extra_file).expanduser().resolve()
    if not defaults_file.is_file():
        log(f"ERROR: option file not found: {defaults_file}")
        return 1
    try:
        defaults_file.relative_to(PROJECT_ROOT)
    except ValueError:
        pass
    else:
        log("ERROR: the credential option file must live OUTSIDE the project directory")
        return 1
    if not Path(MYSQL).is_file():
        log(f"ERROR: mysql client not found at {MYSQL}")
        return 1

    client = Client(defaults_file)

    if args.file and args.file not in MIGRATIONS:
        log(f"ERROR: {args.file!r} is not an approved migration version. "
            f"Known: {', '.join(ORDER)}")
        return 1

    try:
        if args.bootstrap:
            return cmd_bootstrap(client)
        if args.status:
            return cmd_status(client)
        if args.probe:
            return cmd_probe(client, args.probe)
        if args.resolve:
            return cmd_resolve(client, args.resolve, args.state, args.note)
        return cmd_apply(client, args.file)
    except Abort as exc:
        log(f"\nABORTED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
