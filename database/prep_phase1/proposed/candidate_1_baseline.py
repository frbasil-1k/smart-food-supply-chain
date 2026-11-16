#!/usr/bin/env python
"""
Read-only audit for the Smart Food Supply Chain database (Phase 0 tool).

    A. STATIC   parses database/schema.sql. Always runs, no credentials.
    B. LIVE     inspects the running server. Needs DB_USER / DB_PASSWORD.
    --self-test  verifies the parser and comparator against a synthetic
                 catalog derived from the export. No database needed.

The live part never writes: read-only consistent-snapshot transaction,
statement timeout, rollback. The only write path is --negative-probes, which
requires DB_NAME ending in _dev, and also rolls back.

What the live part checks
-------------------------
  B.1  server, sql_mode, isolation, read-only state
  B.2  exact row counts via COUNT(*)   (AUTO_INCREMENT is never used)
  B.3  live vs export, seven stages:
         1 tables + every column definition (type/nullability/default/extra)
         2 primary keys + unique/secondary indexes
         3 foreign keys incl. ON DELETE / ON UPDATE rules
         4 CHECK constraints: name, table, clause, ENFORCED flag
         5 triggers: timing/event/table + BODY, compared semantically
         6 views: definition, compared semantically
         7 engine + collation
       Trigger and view bodies are compared as SQL, not as bytes. A difference
       that normalises away (whitespace, delimiters, backticks, DEFINER
       metadata, database qualification, formatting) is reported PASS with the
       reason. A difference that survives normalisation is reported FAIL as a
       SEMANTIC difference, with a unified diff.
  B.4  objects inventory
  B.5  data profile
  B.6  INVARIANTS (must be 0)
  B.7  OBSERVATIONS (business signals, including route_assignment role mix).
       Historical delivery-driver attribution is reported NOT AVAILABLE on the
       pre-F4 schema: DELIVERY stores no driver, and ROUTE.designated_driver is
       a current designation, so a past driver cannot be established. That is
       an intentional limitation: it is never a failure and never affects the
       exit code.
  B.8  query plans
  B.9  post-migration checks, only for objects that exist
  B.10 inspection-gate predicate self-test
  B.11 proposed donor-impact query: preview only, nothing is created

CHECK constraints: presence is not enforcement. B.3 reports the catalog and
the ENFORCED flag; enforcement itself is proven only by --negative-probes,
which is refused outside a *_dev database.

Usage (PowerShell, project root)
--------------------------------
    $env:DB_USER="root"
    $env:DB_PASSWORD="<password>"
    python database/audit_db.py --out audit-report.txt

    python database/audit_db.py --self-test        # no database needed

Optional env: DB_HOST (127.0.0.1), DB_PORT (3306),
              DB_NAME (smart_food_supply_chain),
              DB_DRIVER (pymysql | mysql.connector),
              DB_PASSWORD_FILE (file holding the password)

Usage
-----
    python database/audit_db.py [--baseline PATH] [--out PATH]
                                [--self-test | --negative-probes]

    --baseline PATH  Compare the live schema against a different
                     reference export instead of the frozen
                     database/schema.sql - for example the
                     post-migration export created after an approved
                     batch. The frozen original is never modified.

Exit codes
----------
    0  clean: no structural or semantic mismatch, no invariant violated,
       no check could not run
    1  a mismatch, violation, or check that could not run
    2  not connected - static report only, nothing verified
"""

from __future__ import annotations

import difflib
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

# Frozen pre-migration reference export. Never rewritten by this script.
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Active baseline for every structural comparison. Rebinding this global
# is how --baseline switches references without touching the default.
SCHEMA_PATH = DEFAULT_SCHEMA_PATH


def set_baseline(path: str) -> Path:
    """Point parse_schema()/compare_export() at `path` instead.

    The default baseline is deliberately NOT replaced: database/schema.sql
    stays the frozen pre-migration export, and a post-migration export is
    a separate file passed here.
    """
    global SCHEMA_PATH
    SCHEMA_PATH = Path(path).expanduser().resolve()
    return SCHEMA_PATH

TABLES = [
    "organization", "branch", "app_user", "route", "coverage_area",
    "route_assignment", "donation", "food_category", "donation_item",
    "inspection_log", "dependent", "delivery", "delivery_item",
    "spoilage_record", "delivery_review",
]

VIEWS = ["vw_donor_sustainability", "vw_driver_performance"]

KNOWN_ROW_TOTAL = 104

# Roles this project permits on ROUTE_ASSIGNMENT (decided in Step 5.4:
# safety inspectors are assigned to routes as employees). NGO_MANAGER and
# DONOR must never be assigned through this table.
ROUTE_ASSIGNMENT_ROLES = ("DRIVER", "SAFETY_INSPECTOR")

# Proposed replacement for donor-impact reporting. NOT installed: the audit
# only runs it as a SELECT to show what the numbers would be.
DONOR_IMPACT_SQL = """
SELECT u.user_id                                   AS donor_id,
       u.full_name                                 AS donor_name,
       COALESCE(h.total_donations, 0)              AS total_donations,
       COALESCE(h.total_donated_kg, 0)             AS total_donated_kg,
       COALESCE(dv.delivered_kg, 0)                AS delivered_kg,
       COALESCE(sp.spoiled_kg, 0)                  AS spoiled_kg,
       COALESCE(h.total_donated_kg, 0)
         - COALESCE(dv.delivered_kg, 0)
         - COALESCE(sp.spoiled_kg, 0)              AS undistributed_balance_kg
  FROM app_user u
  LEFT JOIN (SELECT d.donor_user_id,
                    COUNT(DISTINCT d.donation_id) AS total_donations,
                    SUM(i.quantity_kg)            AS total_donated_kg
               FROM donation d
               LEFT JOIN donation_item i ON i.donation_id = d.donation_id
              WHERE d.donation_status <> 'CANCELLED'
              GROUP BY d.donor_user_id) h ON h.donor_user_id = u.user_id
  LEFT JOIN (SELECT d.donor_user_id,
                    SUM(di.quantity_delivered_kg) AS delivered_kg
               FROM donation d
               JOIN delivery d2 ON d2.donation_id = d.donation_id
               JOIN delivery_item di ON di.delivery_id = d2.delivery_id
              WHERE d2.delivery_status = 'DELIVERED'
                AND d.donation_status <> 'CANCELLED'
              GROUP BY d.donor_user_id) dv ON dv.donor_user_id = u.user_id
  LEFT JOIN (SELECT d.donor_user_id,
                    SUM(s.quantity_spoiled_kg) AS spoiled_kg
               FROM donation d
               JOIN donation_item i2 ON i2.donation_id = d.donation_id
               JOIN spoilage_record s ON s.food_item_id = i2.food_item_id
              WHERE d.donation_status <> 'CANCELLED'
              GROUP BY d.donor_user_id) sp ON sp.donor_user_id = u.user_id
 WHERE u.user_role = 'DONOR'
 ORDER BY delivered_kg DESC, total_donated_kg DESC
"""


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------
class Tee:
    def __init__(self, path: str | None) -> None:
        self.file = open(path, "w", encoding="utf-8") if path else None
        self.stdout = sys.stdout

    def write(self, s: str) -> int:
        if self.file:
            self.file.write(s)
        return self.stdout.write(s)

    def flush(self) -> None:
        if self.file:
            self.file.flush()
        self.stdout.flush()

    def close(self) -> None:
        if self.file:
            self.file.close()


def hr(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------------
# SQL normalisation and semantic comparison
# --------------------------------------------------------------------------
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def norm_sql(s: str, db: str | None = None) -> str:
    """Canonical text: no comments, ticks, DB qualification, case or spacing."""
    s = _BLOCK_COMMENT.sub(" ", s)
    s = s.replace("`", "")
    if db:
        s = s.replace(f"{db}.", "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\s*([(),;=<>!+*/%-])\s*", r"\1", s)
    return s.rstrip(";").strip()


def sql_skeleton(s: str, db: str | None = None) -> str:
    """norm_sql plus operator aliases that mean the same thing."""
    t = norm_sql(s, db)
    t = t.replace("!=", "<>")
    t = re.sub(r"\bifnull\(", "coalesce(", t)
    t = re.sub(r"\bisnull\(", "coalesce(", t)
    t = re.sub(r"\bvalues\(", "(", t)
    return t


def sql_equivalent(a: str, b: str, db: str | None = None) -> tuple[bool, str]:
    if norm_sql(a, db) == norm_sql(b, db):
        return True, "identical after normalisation"
    if sql_skeleton(a, db) == sql_skeleton(b, db):
        return True, "equivalent after alias/formatting normalisation"
    return False, "semantic difference"


def readable_lines(s: str, db: str | None = None) -> list[str]:
    """Best-effort pretty form for a unified diff."""
    t = _BLOCK_COMMENT.sub(" ", s).replace("`", "")
    if db:
        t = t.replace(f"{db}.", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r";\s*", ";\n", t)
    t = re.sub(r"\b(BEGIN|END IF|END|THEN|ELSE|ELSEIF)\b", r"\n\1", t, flags=re.I)
    lines = [ln.strip() for ln in t.splitlines()]
    return [ln for ln in lines if ln]


def diff_sql(a: str, b: str, db: str | None = None,
             from_label: str = "schema.sql", to_label: str = "live") -> str:
    return "\n".join(
        difflib.unified_diff(
            readable_lines(a, db), readable_lines(b, db),
            fromfile=from_label, tofile=to_label, lineterm="", n=2,
        )
    )


def short_hash(s: str) -> str:
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


# --------------------------------------------------------------------------
# A. static parse
# --------------------------------------------------------------------------
COLUMN_ATTR = re.compile(
    r"^([a-zA-Z]+(?:\([^()]*\))?)((?:\s+unsigned)?)(.*)$", re.S
)


def norm_type(raw: str) -> str:
    """Canonical type. ENUM literal case is preserved: it is data, not syntax."""
    s = raw.strip()
    payload = ""
    i = s.find("(")
    if i != -1:
        payload = re.sub(r"\s+", "", s[i:])
        s = s[:i]
    return re.sub(r"\s+", " ", s.strip().lower()) + payload


def parse_column(name: str, definition: str) -> dict[str, Any]:
    m = COLUMN_ATTR.match(definition.strip())
    if not m:
        return {"type": norm_type(definition), "nullable": True,
                "default": None, "extra": ""}
    ctype, unsigned, rest = m.group(1), m.group(2), m.group(3)
    ctype = norm_type(ctype + unsigned)
    low = rest.lower()

    dm = re.search(
        r"default\s+('(?:[^']*)'|null|current_timestamp(?:\(\d*\))?|[-\w.]+)",
        rest, re.I,
    )
    default: str | None = None
    if dm:
        raw = dm.group(1)
        if raw.startswith("'"):
            default = raw[1:-1]
        elif raw.lower() == "null":
            default = None
        elif "current_timestamp" in raw.lower():
            default = "CURRENT_TIMESTAMP"
        else:
            default = raw

    extra_bits = []
    if "auto_increment" in low:
        extra_bits.append("auto_increment")
    if "on update current_timestamp" in low:
        extra_bits.append("on update current_timestamp")

    return {
        "type": ctype,
        "nullable": "not null" not in low,
        "default": default,
        "extra": " ".join(extra_bits),
    }


def split_cols(s: str) -> tuple[str, ...]:
    return tuple(c.strip().strip("`") for c in s.split(",") if c.strip())


def parse_schema() -> dict[str, Any]:
    sql = SCHEMA_PATH.read_text(encoding="utf-8", errors="replace")

    table_blocks = re.findall(
        r"CREATE TABLE `(\w+)` \((.*?)\n\) ENGINE=([^\n]*)", sql, re.S
    )

    tables: dict[str, Any] = {}
    for name, body, tail in table_blocks:
        columns: dict[str, Any] = {}
        pk: tuple[str, ...] = ()
        keys: dict[str, tuple[bool, tuple[str, ...]]] = {}
        fks: dict[str, dict[str, Any]] = {}
        checks: dict[str, str] = {}

        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            if not line.upper().startswith(("PRIMARY", "UNIQUE", "KEY",
                                            "CONSTRAINT", "FOREIGN")):
                cm = re.match(r"^`(\w+)`\s+(.+)$", line)
                if cm:
                    columns[cm.group(1)] = parse_column(cm.group(1), cm.group(2))
                    continue
            m = re.match(r"^PRIMARY KEY \((.+)\)$", line, re.I)
            if m:
                pk = split_cols(m.group(1))
                continue
            m = re.match(r"^UNIQUE KEY `(\w+)` \((.+)\)$", line, re.I)
            if m:
                keys[m.group(1)] = (True, split_cols(m.group(2)))
                continue
            m = re.match(r"^KEY `(\w+)` \((.+)\)$", line, re.I)
            if m:
                keys[m.group(1)] = (False, split_cols(m.group(2)))
                continue
            m = re.match(
                r"^CONSTRAINT `(\w+)` FOREIGN KEY \((.+?)\) "
                r"REFERENCES `(\w+)` \((.+?)\)(.*)$", line, re.I
            )
            if m:
                rules = m.group(5).upper()
                dm = re.search(r"ON DELETE (\w+(?: \w+)?)", rules)
                um = re.search(r"ON UPDATE (\w+(?: \w+)?)", rules)
                fks[m.group(1)] = {
                    "columns": split_cols(m.group(2)),
                    "ref_table": m.group(3),
                    "ref_columns": split_cols(m.group(4)),
                    "on_delete": (dm.group(1) if dm else "RESTRICT").upper(),
                    "on_update": (um.group(1) if um else "RESTRICT").upper(),
                }
                continue
            m = re.match(r"^CONSTRAINT `(chk_\w+)` CHECK \((.+)\)$", line, re.I)
            if m:
                checks[m.group(1)] = norm_sql(m.group(2))

        trigs = re.findall(
            r"TRIGGER `(\w+)` (BEFORE|AFTER) (INSERT|UPDATE|DELETE) ON `(\w+)`",
            sql,
        )
        tables[name] = {
            "columns": columns,
            "pk": pk,
            "keys": keys,
            "fks": fks,
            "checks": checks,
            "trigger_names": [t[0] for t in trigs if t[3] == name],
            "collation": (re.search(r"COLLATE=(\w+)", tail) or [None, "?"])[1],
            "engine": (re.search(r"ENGINE=(\w+)", tail) or [None, "?"])[1],
        }

    # Trigger bodies: the trailing "END" belongs to the body. The previous
    # pattern stopped before it, which is why every body hash differed.
    triggers: dict[str, Any] = {}
    for m in re.finditer(
        r"TRIGGER `(\w+)` (BEFORE|AFTER) (INSERT|UPDATE|DELETE) ON `(\w+)` "
        r"FOR EACH ROW (BEGIN.*?END)\s*\*/;;",
        sql, re.S,
    ):
        triggers[m.group(1)] = {
            "timing": m.group(2).upper(),
            "event": m.group(3).upper(),
            "table": m.group(4),
            "body": m.group(5),
        }

    views: dict[str, str] = {}
    for m in re.finditer(r"VIEW `(\w+)` AS (select .*?)\*/;", sql, re.S | re.I):
        views[m.group(1)] = m.group(2)

    all_checks: dict[str, str] = {}
    for t in tables.values():
        all_checks.update(t["checks"])

    return {
        "tables": tables,
        "triggers": triggers,
        "trigger_names": sorted(triggers),
        "views": views,
        "checks": all_checks,
    }


def print_static(schema: dict[str, Any]) -> None:
    tables = schema["tables"]
    hr("A. STATIC SCHEMA EXPORT  (database/schema.sql)")
    print(f"Tables  : {len(tables)}  (CREATE TABLE objects only)")
    print(f"Views   : {len(schema['views'])}  -> {', '.join(sorted(schema['views']))}")
    print(f"Columns : {sum(len(t['columns']) for t in tables.values())}")
    print(f"Triggers: {len(schema['triggers'])}")
    print(f"CHECKs  : {len(schema['checks'])}")
    print(f"FKs     : {sum(len(t['fks']) for t in tables.values())}")
    print(f"Indexes : {sum(len(t['keys']) + 1 for t in tables.values())} "
          f"(incl. primary keys)")

    print("\nPer-table detail")
    print(f"{'table':18} {'cols':>4} {'fk':>3} {'chk':>3} {'idx':>3} {'trg':>3}")
    for name, info in tables.items():
        print(f"{name:18} {len(info['columns']):>4} {len(info['fks']):>3} "
              f"{len(info['checks']):>3} {len(info['keys']):>3} "
              f"{len(info['trigger_names']):>3}")

    print("\nCHECK constraints (names; clauses compared in B.3)")
    for name in sorted(schema["checks"]):
        print(f"  {name}")

    print("\nRow counts")
    print("  Structure-only export: it carries no rows. AUTO_INCREMENT is not a")
    print("  row count and is not used anywhere in this script.")
    print(f"  Last verified total (Workbench, 2026-11-13): {KNOWN_ROW_TOTAL}")
    print("  Authoritative per-table counts come from COUNT(*) in B.2.")


# --------------------------------------------------------------------------
# connection
# --------------------------------------------------------------------------
class AuditError(RuntimeError):
    pass


def _read_password() -> str:
    path = os.environ.get("DB_PASSWORD_FILE", "").strip()
    if path:
        p = Path(path)
        if not p.exists():
            raise AuditError(f"DB_PASSWORD_FILE points at a missing file: {path}")
        return p.read_text(encoding="utf-8").rstrip("\r\n")
    pw = os.environ.get("DB_PASSWORD", "")
    if not pw:
        raise AuditError("DB_PASSWORD is not set (and DB_PASSWORD_FILE is unused)")
    return pw


def _describe_connect_error(exc: BaseException) -> str:
    text = str(exc)
    errno = getattr(exc, "errno", None)
    if not isinstance(errno, int):
        m = re.search(r"\((\d{4})\)", text)
        errno = int(m.group(1)) if m else None
    hints = {
        1044: "the user is not allowed to access this database",
        1045: "credentials rejected - wrong user name or password",
        1049: "database does not exist on this server",
        2003: "cannot reach the server - is mysqld listening on this port?",
        2013: "connection lost during handshake",
    }
    hint = hints.get(errno or -1)
    return text + (f"  [{hint}]" if hint else "")


def db_config() -> dict[str, Any]:
    host = os.environ.get("DB_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("DB_PORT", "3306"))
    except ValueError as exc:
        raise AuditError(f"DB_PORT is not a number: {os.environ.get('DB_PORT')!r}") from exc
    user = os.environ.get("DB_USER", "")
    if not user:
        raise AuditError("DB_USER is not set")
    name = os.environ.get("DB_NAME", "smart_food_supply_chain").strip()
    if not name:
        raise AuditError("DB_NAME is empty")
    return {"host": host, "port": port, "user": user,
            "password": _read_password(), "database": name}


def connect_mysql() -> tuple[Any, str]:
    cfg = db_config()
    preferred = os.environ.get("DB_DRIVER", "").strip().lower()
    order = [preferred] if preferred else ["pymysql", "mysql.connector"]
    attempts: list[str] = []

    for driver in order:
        try:
            if driver == "pymysql":
                import pymysql  # type: ignore

                return pymysql.connect(
                    host=cfg["host"], port=cfg["port"], user=cfg["user"],
                    password=cfg["password"], database=cfg["database"],
                    charset="utf8mb4", autocommit=True, connect_timeout=6,
                ), "PyMySQL"
            if driver == "mysql.connector":
                import mysql.connector  # type: ignore

                return mysql.connector.connect(
                    host=cfg["host"], port=cfg["port"], user=cfg["user"],
                    password=cfg["password"], database=cfg["database"],
                    charset="utf8mb4", autocommit=True,
                    connection_timeout=6, use_pure=True,
                ), "mysql-connector-python"
            raise AuditError(f"unknown DB_DRIVER: {driver!r}")
        except ImportError:
            attempts.append(f"{driver}: driver not installed")
        except AuditError:
            raise
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"{driver}: {_describe_connect_error(exc)}")

    raise AuditError("no driver could connect:\n    " + "\n    ".join(attempts))


# --------------------------------------------------------------------------
# live audit
# --------------------------------------------------------------------------
class LiveAudit:
    def __init__(self, conn: Any, driver: str, db: str) -> None:
        self.conn = conn
        self.driver = driver
        self.db = db
        self.cur = conn.cursor()
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.results: list[tuple[str, str, str]] = []
        self.read_only = False

    # -- plumbing ---------------------------------------------------------
    def q(self, sql: str, args: Any = None) -> list[dict[str, Any]]:
        if args is None:
            self.cur.execute(sql)
        else:
            self.cur.execute(sql, args)
        if self.cur.description is None:
            return []
        cols = [d[0] for d in self.cur.description]
        return [dict(zip(cols, row)) for row in self.cur.fetchall()]

    def exists(self, kind: str, name: str) -> bool:
        try:
            if kind == "table":
                return bool(self.q(
                    "SELECT 1 AS x FROM information_schema.tables "
                    "WHERE table_schema=%s AND table_name=%s "
                    "AND table_type='BASE TABLE'", (self.db, name)))
            if kind.startswith("column:"):
                return bool(self.q(
                    "SELECT 1 AS x FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
                    (self.db, kind.split(":", 1)[1], name)))
            if kind == "check":
                return bool(self.q(
                    "SELECT 1 AS x FROM information_schema.table_constraints "
                    "WHERE table_schema=%s AND constraint_name=%s "
                    "AND constraint_type='CHECK'", (self.db, name)))
            if kind == "view":
                return bool(self.q(
                    "SELECT 1 AS x FROM information_schema.views "
                    "WHERE table_schema=%s AND table_name=%s", (self.db, name)))
            if kind == "trigger":
                return bool(self.q(
                    "SELECT 1 AS x FROM information_schema.triggers "
                    "WHERE trigger_schema=%s AND trigger_name=%s", (self.db, name)))
        except Exception:  # noqa: BLE001
            return False
        return False

    def start(self) -> None:
        for stmt in ("SET SESSION max_execution_time = 60000",
                     "SET SESSION group_concat_max_len = 16384"):
            try:
                self.cur.execute(stmt)
            except Exception:  # noqa: BLE001
                pass
        try:
            self.cur.execute("SET SESSION TRANSACTION READ ONLY")
            self.cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            self.read_only = True
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"read-only snapshot unavailable: {exc}")
            print(f"  note: read-only snapshot unavailable ({exc}); "
                  f"continuing with SELECT/SHOW only")

    def section(self, title: str, fn: Callable[[], None]) -> None:
        hr(title)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"{title}: {type(exc).__name__}: {exc}")
            print(f"  !! SECTION FAILED - {type(exc).__name__}: {exc}")

    def want(self, cond: bool, label: str, detail: str = "") -> None:
        if cond:
            print(f"  PASS  {label}" + (f"   {detail}" if detail else ""))
        else:
            print(f"  FAIL  {label}" + (f"   {detail}" if detail else ""))
            self.failures.append(f"{label} {detail}".strip())

    def note(self, cond: bool, label: str, detail: str = "") -> None:
        if cond:
            print(f"  PASS  {label}")
        else:
            print(f"  WARN  {label}  {detail}")
            self.warnings.append(f"{label} {detail}".strip())

    def show_diff(self, text: str) -> None:
        if not text.strip():
            print("      (no textual difference after normalisation)")
            return
        for line in text.splitlines():
            print(f"      {line}")

    # -- summary -----------------------------------------------------------
    def summary(self) -> int:
        """Print the summary and return the exit code.

        NOT AVAILABLE entries are informational: they are neither failures nor
        'could not run', and never change the exit code.
        """
        hr("SUMMARY")
        inv = [r for r in self.results if r[1] in ("PASS", "FAIL")]
        failed = [r for r in inv if r[1] == "FAIL"]
        broken = [r for r in self.results if r[1] == "COULD NOT RUN"]
        unavailable = [r for r in self.results if r[1] == "NOT AVAILABLE"]

        print(f"INVARIANTS run : {len(inv)}  passed {len(inv) - len(failed)}"
              f"  failed {len(failed)}")
        for key, _v, detail in failed:
            print(f"  FAIL {key} {detail}")
        print(f"Checks not run : {len(broken)}")
        for key, _v, detail in broken:
            print(f"  {key}: {detail}")
        if unavailable:
            print(f"Not auditable by design: {len(unavailable)} "
                  f"(informational, does not affect the exit code)")
            for key, _v, detail in unavailable:
                print(f"  {key}:")
                print(f"    {detail}")
        print(f"Structural/semantic failures: {len(self.failures)}")
        for f in self.failures:
            print(f"  - {f}")
        if self.warnings:
            print(f"Warnings: {len(self.warnings)}")
            for w in self.warnings:
                print(f"  - {w}")
        code = 0 if not self.failures and not broken else 1
        print(f"\nRESULT: exit {code}")
        return code

    # -- B.1 ---------------------------------------------------------------
    def server(self) -> None:
        row = self.q(
            "SELECT VERSION() AS version, @@sql_mode AS sql_mode, "
            "DATABASE() AS db, CURRENT_USER() AS principal, "
            "@@transaction_isolation AS isolation"
        )[0]
        print(f"Driver         : {self.driver}")
        print(f"Server         : {row['version']}")
        print(f"Database       : {row['db']}")
        print(f"Connected as   : {row['principal']}")
        print(f"Isolation      : {row['isolation']}")
        print(f"Read-only txn  : {self.read_only}")
        print(f"sql_mode       : {row['sql_mode']}")
        print("CHECK enforced : not asserted from data. See B.3 (catalog +")
        print("                 ENFORCED flag) and --negative-probes (proof).")

    # -- B.2 ---------------------------------------------------------------
    def row_counts(self) -> None:
        live = [r["t"] for r in self.q(
            "SELECT table_name AS t FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name",
            (self.db,))]
        if not live:
            raise AuditError(f"no base tables in database {self.db!r}")
        print(f"{'table':20} {'rows':>8}")
        total = 0
        for t in live:
            n = self.q(f"SELECT COUNT(*) AS n FROM `{t}`")[0]["n"]
            total += n
            print(f"{t:20} {n:>8}")
        print(f"{'TOTAL':20} {total:>8}")
        print()
        print(f"COUNT(*) total : {total}")
        print(f"Workbench total: {KNOWN_ROW_TOTAL}   delta {total - KNOWN_ROW_TOTAL:+d}")
        if total != KNOWN_ROW_TOTAL:
            self.warnings.append(
                f"row total {total} differs from the verified {KNOWN_ROW_TOTAL}")

    # -- B.3 ---------------------------------------------------------------
    def _object_types(self) -> dict[str, str]:
        """name -> BASE TABLE | VIEW. One query, filtered in Python so the
        table/view split cannot leak into the table comparison again."""
        return {
            r["t"]: (r["tt"] or "").upper()
            for r in self.q(
                "SELECT table_name AS t, table_type AS tt "
                "FROM information_schema.tables WHERE table_schema=%s",
                (self.db,))
        }

    def _live_columns(self, base: set[str]) -> dict[str, dict[str, dict[str, Any]]]:
        out: dict[str, dict[str, dict[str, Any]]] = {}
        for r in self.q(
            "SELECT table_name AS t, column_name AS c, column_type AS ty, "
            "is_nullable AS nul, column_default AS def, extra AS ex "
            "FROM information_schema.columns WHERE table_schema=%s "
            "ORDER BY table_name, ordinal_position", (self.db,)
        ):
            if r["t"] not in base:
                continue
            ex = (r["ex"] or "").replace("DEFAULT_GENERATED", "").strip().lower()
            ex = re.sub(r"\s+", " ", ex)
            out.setdefault(r["t"], {})[r["c"]] = {
                "type": norm_type(r["ty"] or ""),
                "nullable": (r["nul"] or "YES") == "YES",
                "default": r["def"],
                "extra": ex,
            }
        return out

    def compare_export(self, schema: dict[str, Any]) -> None:
        expected_tables = schema["tables"]
        types = self._object_types()
        base = {t for t, tt in types.items() if tt == "BASE TABLE"}
        live_views = {t for t, tt in types.items() if tt == "VIEW"}
        live_cols = self._live_columns(base)

        print("Stage 1 - tables and column definitions")
        print(f"  live objects: {len(base)} base table(s), {len(live_views)} view(s)")
        print(f"  export:       {len(expected_tables)} CREATE TABLE, "
              f"{len(schema['views'])} CREATE VIEW")
        self.want(set(expected_tables) == base, "table set matches",
                  f"missing={sorted(set(expected_tables) - base)} "
                  f"extra={sorted(base - set(expected_tables))}")
        self.want(not (live_views & set(expected_tables)),
                  "no view is classified as a table",
                  f"leaked={sorted(live_views & set(expected_tables))}")

        for tname, tinfo in expected_tables.items():
            if tname not in live_cols:
                continue
            exp_cols = tinfo["columns"]
            got_cols = live_cols[tname]
            problems: list[str] = []
            if set(exp_cols) != set(got_cols):
                problems.append(
                    f"columns missing={sorted(set(exp_cols) - set(got_cols))} "
                    f"extra={sorted(set(got_cols) - set(exp_cols))}")
            for cname in sorted(set(exp_cols) & set(got_cols)):
                e, g = exp_cols[cname], got_cols[cname]
                diffs = []
                if e["type"] != g["type"]:
                    diffs.append(f"type {e['type']}!={g['type']}")
                if e["nullable"] != g["nullable"]:
                    diffs.append(f"nullability {'NULL' if e['nullable'] else 'NOT NULL'}"
                                 f"!={'NULL' if g['nullable'] else 'NOT NULL'}")
                if (e["default"] or None) != (g["default"] or None):
                    diffs.append(f"default {e['default']!r}!={g['default']!r}")
                if e["extra"] != g["extra"]:
                    diffs.append(f"extra {e['extra']!r}!={g['extra']!r}")
                if diffs:
                    problems.append(f"{cname}: " + "; ".join(diffs))
            self.want(not problems, f"{tname}.columns",
                      "" if not problems else " | ".join(problems[:4]))

        print("\nStage 2 - primary keys and indexes")
        live_pk = {r["t"]: tuple((r["cols"] or "").split(",")) for r in self.q(
            "SELECT table_name AS t, "
            "GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols "
            "FROM information_schema.statistics WHERE table_schema=%s "
            "AND index_name='PRIMARY' GROUP BY table_name", (self.db,))
            if r["t"] in base}
        for tname, tinfo in expected_tables.items():
            if tname not in live_cols:
                continue
            self.want(tuple(tinfo["pk"]) == live_pk.get(tname, ()),
                      f"{tname}.primary_key",
                      f"export={tinfo['pk']} live={live_pk.get(tname)}")

        live_keys: dict[str, dict[str, tuple[bool, tuple[str, ...]]]] = {}
        for r in self.q(
            "SELECT table_name AS t, index_name AS i, non_unique AS nu, "
            "GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols "
            "FROM information_schema.statistics WHERE table_schema=%s "
            "AND index_name<>'PRIMARY' "
            "GROUP BY table_name, index_name, non_unique", (self.db,)
        ):
            if r["t"] not in base:
                continue
            live_keys.setdefault(r["t"], {})[r["i"]] = (
                r["nu"] == 0, tuple((r["cols"] or "").split(",")))
        for tname, tinfo in expected_tables.items():
            if tname not in live_cols:
                continue
            exp, got = dict(tinfo["keys"]), live_keys.get(tname, {})
            if exp == got:
                self.want(True, f"{tname}.indexes", f"{len(exp)} index(es)")
            else:
                self.want(False, f"{tname}.indexes",
                          f"export_only={ {k: exp[k] for k in exp if exp.get(k) != got.get(k)} } "
                          f"live_only={ {k: got[k] for k in got if got.get(k) != exp.get(k)} }")

        print("\nStage 3 - foreign keys and referential rules")
        live_fks: dict[str, dict[str, Any]] = {}
        for r in self.q(
            "SELECT k.table_name AS t, k.constraint_name AS c, "
            "GROUP_CONCAT(k.column_name ORDER BY k.ordinal_position) AS cols, "
            "k.referenced_table_name AS rt, "
            "GROUP_CONCAT(k.referenced_column_name ORDER BY k.ordinal_position) AS rcols, "
            "rc.delete_rule AS dr, rc.update_rule AS ur "
            "FROM information_schema.key_column_usage k "
            "JOIN information_schema.referential_constraints rc "
            "  ON rc.constraint_schema=k.constraint_schema "
            " AND rc.constraint_name=k.constraint_name "
            "WHERE k.table_schema=%s AND k.referenced_table_name IS NOT NULL "
            "GROUP BY k.table_name, k.constraint_name, k.referenced_table_name, "
            "         rc.delete_rule, rc.update_rule", (self.db,)
        ):
            if r["t"] not in base:
                continue
            live_fks.setdefault(r["t"], {})[r["c"]] = {
                "columns": tuple((r["cols"] or "").split(",")),
                "ref_table": r["rt"],
                "ref_columns": tuple((r["rcols"] or "").split(",")),
                "on_delete": (r["dr"] or "RESTRICT").upper(),
                "on_update": (r["ur"] or "RESTRICT").upper(),
            }

        def rule_norm(v: str) -> str:
            return "RESTRICT" if v in ("RESTRICT", "NO ACTION", "") else v

        for tname, tinfo in expected_tables.items():
            if tname not in live_cols:
                continue
            exp, got = tinfo["fks"], live_fks.get(tname, {})
            if set(exp) != set(got):
                self.want(False, f"{tname}.foreign_keys",
                          f"missing={sorted(set(exp) - set(got))} "
                          f"extra={sorted(set(got) - set(exp))}")
                continue
            diffs = []
            for name, e in exp.items():
                g = got[name]
                if (e["columns"] != g["columns"] or e["ref_table"] != g["ref_table"]
                        or e["ref_columns"] != g["ref_columns"]):
                    diffs.append(f"{name}: {e['columns']}->{e['ref_table']}"
                                 f"{e['ref_columns']} vs {g['columns']}->"
                                 f"{g['ref_table']}{g['ref_columns']}")
                if rule_norm(e["on_delete"]) != rule_norm(g["on_delete"]):
                    diffs.append(f"{name}: ON DELETE {e['on_delete']} vs {g['on_delete']}")
                if rule_norm(e["on_update"]) != rule_norm(g["on_update"]):
                    diffs.append(f"{name}: ON UPDATE {e['on_update']} vs {g['on_update']}")
            self.want(not diffs, f"{tname}.foreign_keys",
                      f"{len(exp)} FK(s)" if not diffs else " | ".join(diffs[:3]))

        print("\nStage 4 - CHECK constraints (definition + ENFORCED flag)")
        enforcable = bool(self.q(
            "SELECT 1 AS x FROM information_schema.columns "
            "WHERE table_schema='information_schema' "
            "AND table_name='TABLE_CONSTRAINTS' AND column_name='ENFORCED'"))
        print(f"  catalog exposes ENFORCED: {'yes' if enforcable else 'no'}")
        live_checks: dict[str, Any] = {}
        for r in self.q(
            "SELECT tc.table_name AS t, tc.constraint_name AS c, "
            "cc.check_clause AS cl" + (", tc.enforced AS en" if enforcable
                                       else ", NULL AS en") +
            " FROM information_schema.table_constraints tc "
            "JOIN information_schema.check_constraints cc "
            "  ON cc.constraint_schema=tc.constraint_schema "
            " AND cc.constraint_name=tc.constraint_name "
            "WHERE tc.table_schema=%s AND tc.constraint_type='CHECK'",
            (self.db,)
        ):
            live_checks[r["c"]] = {
                "table": r["t"], "clause": norm_sql(r["cl"] or ""),
                "enforced": "YES" if r["en"] is None else r["en"],
            }
        print(f"  export defines {len(schema['checks'])} / live has {len(live_checks)}")
        for name, exp_clause in schema["checks"].items():
            got = live_checks.get(name)
            if not got:
                self.want(False, f"check {name}", "missing from the live database")
                continue
            if got["clause"] == exp_clause:
                self.want(True, f"check {name}", f"ENFORCED={got['enforced']}")
            else:
                self.want(False, f"check {name}",
                          f"ENFORCED={got['enforced']} clause differs")
                self.show_diff(diff_sql(exp_clause, got["clause"]))
        for name, got in live_checks.items():
            if name not in schema["checks"]:
                self.note(False, f"check {name}",
                          f"only in live DB ({got['table']}), not in the export")

        print("\nStage 5 - triggers (semantic body comparison)")
        live_trig = {r["n"]: r for r in self.q(
            "SELECT trigger_name AS n, event_object_table AS t, "
            "action_timing AS tm, event_manipulation AS e, "
            "action_statement AS body FROM information_schema.triggers "
            "WHERE trigger_schema=%s", (self.db,))}
        self.want(set(schema["triggers"]) == set(live_trig),
                  "trigger set matches",
                  f"missing={sorted(set(schema['triggers']) - set(live_trig))} "
                  f"extra={sorted(set(live_trig) - set(schema['triggers']))}")
        semantic = 0
        for name, exp in schema["triggers"].items():
            got = live_trig.get(name)
            if not got:
                continue
            meta_ok = (exp["timing"] == (got["tm"] or "").upper()
                       and exp["event"] == (got["e"] or "").upper()
                       and exp["table"] == got["t"])
            if not meta_ok:
                self.want(False, f"trigger {name}",
                          f"export={exp['timing']} {exp['event']} on {exp['table']} "
                          f"live={got['tm']} {got['e']} on {got['t']}")
                continue
            eq, why = sql_equivalent(exp["body"], got["body"] or "", self.db)
            if eq:
                self.want(True, f"trigger {name}", why)
            else:
                semantic += 1
                self.want(False, f"trigger {name}", f"SEMANTIC difference")
                self.show_diff(diff_sql(exp["body"], got["body"] or "", self.db))
        if semantic:
            print(f"\n  {semantic} trigger(s) differ semantically - review the diffs above.")

        print("\nStage 6 - views (semantic definition comparison)")
        live_views_def = {r["n"]: r["d"] for r in self.q(
            "SELECT table_name AS n, view_definition AS d "
            "FROM information_schema.views WHERE table_schema=%s", (self.db,))}
        self.want(set(schema["views"]) == set(live_views_def), "view set matches",
                  f"missing={sorted(set(schema['views']) - set(live_views_def))} "
                  f"extra={sorted(set(live_views_def) - set(schema['views']))}")
        for name, exp in schema["views"].items():
            got = live_views_def.get(name)
            if got is None:
                continue
            eq, why = sql_equivalent(exp, got, self.db)
            if eq:
                self.want(True, f"view {name}", why)
            else:
                self.want(False, f"view {name}", "SEMANTIC difference")
                self.show_diff(diff_sql(exp, got, self.db))

        print("\nStage 7 - table options")
        for r in self.q(
            "SELECT table_name AS t, engine AS e, table_collation AS coll "
            "FROM information_schema.tables WHERE table_schema=%s "
            "AND table_type='BASE TABLE' ORDER BY table_name", (self.db,)
        ):
            exp = expected_tables.get(r["t"], {})
            self.want(r["e"] == "InnoDB", f"{r['t']}.engine", str(r["e"]))
            if exp.get("collation"):
                self.note(r["coll"] == exp["collation"], f"{r['t']}.collation",
                          f"export={exp['collation']} live={r['coll']}")

    # -- B.4 ---------------------------------------------------------------
    def objects(self) -> None:
        print("Views")
        for r in self.q(
            "SELECT table_name AS n FROM information_schema.views "
            "WHERE table_schema=%s ORDER BY table_name", (self.db,)
        ):
            n = self.q(f"SELECT COUNT(*) AS n FROM `{r['n']}`")[0]["n"]
            print(f"  {r['n']:30} rows={n}")

        print("\nTriggers")
        for r in self.q(
            "SELECT trigger_name AS n, event_object_table AS t, "
            "action_timing AS tm, event_manipulation AS e "
            "FROM information_schema.triggers WHERE trigger_schema=%s "
            "ORDER BY event_object_table, action_timing, event_manipulation",
            (self.db,)
        ):
            print(f"  {r['t']:18} {r['tm']:6} {r['e']:6} {r['n']}")

        print("\nIndexes")
        for r in self.q(
            "SELECT table_name AS t, index_name AS i, "
            "GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols, "
            "non_unique AS nu, MAX(cardinality) AS card "
            "FROM information_schema.statistics WHERE table_schema=%s "
            "GROUP BY table_name, index_name, non_unique "
            "ORDER BY table_name, index_name", (self.db,)
        ):
            kind = "UNIQUE" if r["nu"] == 0 else "INDEX "
            print(f"  {r['t']:18} {kind} {r['i']:24} ({r['cols']}) card={r['card']}")

    # -- B.5 ---------------------------------------------------------------
    def profile(self) -> None:
        for label, sql in [
            ("donation_status", "SELECT donation_status AS k, COUNT(*) AS n "
                                "FROM donation GROUP BY donation_status ORDER BY 2 DESC"),
            ("safety_status", "SELECT safety_status AS k, COUNT(*) AS n "
                              "FROM inspection_log GROUP BY safety_status ORDER BY 2 DESC"),
            ("delivery_status", "SELECT delivery_status AS k, COUNT(*) AS n "
                                "FROM delivery GROUP BY delivery_status ORDER BY 2 DESC"),
            ("user_role", "SELECT user_role AS k, COUNT(*) AS n "
                          "FROM app_user GROUP BY user_role ORDER BY 2 DESC"),
            ("account_status", "SELECT account_status AS k, COUNT(*) AS n "
                               "FROM app_user GROUP BY account_status ORDER BY 2 DESC"),
        ]:
            print(f"\n  {label}")
            try:
                rows = self.q(sql)
                if not rows:
                    print("    (no rows)")
                for r in rows:
                    print(f"    {str(r['k']):22} {r['n']}")
            except Exception as exc:  # noqa: BLE001
                self.failures.append(f"profile {label}: {exc}")
                print(f"    COULD NOT RUN: {exc}")

    # -- B.6 ---------------------------------------------------------------
    def not_available(self, key: str, reason: str) -> None:
        """Record a question this schema cannot answer.

        Deliberately NOT a failure and NOT 'could not run': nothing errored,
        the data simply does not exist. The exit code is unaffected.
        """
        print(f"  {key:34} NOT AVAILABLE")
        print(f"      {reason}")
        self.results.append((key, "NOT AVAILABLE", reason))

    def check(self, key: str, kind: str, meaning: str, sql: str) -> None:
        try:
            rows = self.q(sql)
            value = rows[0]["n"] if rows else None
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"check {key} could not run: {exc}")
            self.results.append((key, "COULD NOT RUN", str(exc)))
            print(f"  {key:34} COULD NOT RUN  ({exc})")
            return
        if value is None:
            self.failures.append(f"check {key} returned no row")
            self.results.append((key, "COULD NOT RUN", "no row"))
            print(f"  {key:34} COULD NOT RUN  (no row)")
            return
        if kind == "INVARIANT":
            verdict = "PASS" if value == 0 else "FAIL"
            if value != 0:
                self.failures.append(f"{key} violated: {value} row(s)")
            print(f"  {key:34} {verdict:5} n={value}")
            print(f"      asserts: {meaning}")
        else:
            verdict = "OBSERVE"
            print(f"  {key:34} n={value}")
            print(f"      meaning: {meaning}")
        self.results.append((key, verdict, f"n={value}"))

    @staticmethod
    def inspection_gate(delivery_alias: str = "d",
                        inspection_source: str = "inspection_log") -> str:
        """NOT EXISTS (a PASSED inspection with no later inspection).

        A donation with no inspection at all is flagged: 'missing' must never
        read as 'fine'.
        """
        return (
            "NOT EXISTS ("
            f"  SELECT 1 FROM {inspection_source} il"
            f"   WHERE il.donation_id = {delivery_alias}.donation_id"
            "     AND il.safety_status = 'PASSED'"
            "     AND NOT EXISTS ("
            f"       SELECT 1 FROM {inspection_source} nx"
            "        WHERE nx.donation_id = il.donation_id"
            "          AND (nx.inspected_at > il.inspected_at"
            "               OR (nx.inspected_at = il.inspected_at"
            "                   AND nx.inspection_id > il.inspection_id))))"
        )

    def invariants(self) -> None:
        print("INVARIANT checks - each must return 0. A FAIL is real inconsistent")
        print("data, not a cosmetic warning.\n")

        self.check(
            "alloc_le_donated", "INVARIANT",
            "delivered + spoiled never exceeds the donated quantity of an item "
            "(correlated subqueries, so neither child table fans out)",
            "SELECT COUNT(*) AS n FROM donation_item di "
            "WHERE di.quantity_kg < "
            "  COALESCE((SELECT SUM(quantity_delivered_kg) FROM delivery_item "
            "            WHERE food_item_id = di.food_item_id), 0) + "
            "  COALESCE((SELECT SUM(quantity_spoiled_kg) FROM spoilage_record "
            "            WHERE food_item_id = di.food_item_id), 0)")

        self.check(
            "delivery_item_same_donation", "INVARIANT",
            "every delivery_item points at a food item of the delivery's donation",
            "SELECT COUNT(*) AS n FROM delivery_item i "
            "JOIN delivery d ON d.delivery_id = i.delivery_id "
            "JOIN donation_item di ON di.food_item_id = i.food_item_id "
            "WHERE di.donation_id <> d.donation_id")

        self.check(
            "moved_delivery_has_passed", "INVARIANT",
            "no IN_TRANSIT/DELIVERED delivery unless the LATEST inspection "
            "passed; no inspection at all counts as a failure",
            "SELECT COUNT(*) AS n FROM delivery d "
            "WHERE d.delivery_status IN ('IN_TRANSIT','DELIVERED') AND "
            + self.inspection_gate())

        # ACTIVE routes only. P1 permits a DRIVER role change once the user has
        # no active-route responsibility, so an INACTIVE route still naming a
        # former driver is history, not a violation (reported in B.7).
        self.check(
            "route_driver_has_role_active", "INVARIANT",
            "every ACTIVE route's designated driver holds the DRIVER role now; "
            "inactive routes are excluded because their designation is "
            "historical after an approved role change",
            "SELECT COUNT(*) AS n FROM route r "
            "JOIN app_user u ON u.user_id = r.designated_driver_user_id "
            "WHERE r.route_status = 'ACTIVE' AND u.user_role <> 'DRIVER'")

        self.check(
            "branch_manager_has_role", "INVARIANT",
            "every branch's regional manager still has the NGO_MANAGER role",
            "SELECT COUNT(*) AS n FROM branch b "
            "JOIN app_user u ON u.user_id = b.regional_manager_user_id "
            "WHERE u.user_role <> 'NGO_MANAGER'")

        self.check(
            "route_assignment_role_allowed", "INVARIANT",
            "every route_assignment belongs to a DRIVER or SAFETY_INSPECTOR; "
            "NGO_MANAGER and DONOR are never assignable",
            "SELECT COUNT(*) AS n FROM route_assignment ra "
            "JOIN app_user u ON u.user_id = ra.user_id "
            "WHERE u.user_role NOT IN ("
            + ", ".join(f"'{r}'" for r in ROUTE_ASSIGNMENT_ROLES) + ")")

        self.check(
            "no_orphan_branch_refs", "INVARIANT",
            "app_user.primary_branch_id and branch.organization_id resolve",
            "SELECT (SELECT COUNT(*) FROM app_user u LEFT JOIN branch b "
            "          ON b.branch_id = u.primary_branch_id "
            "        WHERE u.primary_branch_id IS NOT NULL "
            "          AND b.branch_id IS NULL) + "
            "       (SELECT COUNT(*) FROM branch b LEFT JOIN organization o "
            "          ON o.organization_id = b.organization_id "
            "        WHERE o.organization_id IS NULL) AS n")

        print("\n  Declarative constraints are compared in B.3 against the catalog.")
        print("  Positive data cannot prove enforcement: these checks would pass")
        print("  even if the server ignored every CHECK. B.10 tests the logic of")
        print("  the inspection gate; --negative-probes tests the server's CHECKs.")

    def observations(self) -> None:
        print("OBSERVATION checks - business signals, not defects.\n")

        self.check(
            "donations_without_items", "OBSERVATION",
            "donation headers with no items",
            "SELECT COUNT(*) AS n FROM donation d WHERE NOT EXISTS "
            "(SELECT 1 FROM donation_item i WHERE i.donation_id = d.donation_id)")

        self.check(
            "deliveries_without_items", "OBSERVATION",
            "deliveries with nothing allocated yet (normal for PLANNED)",
            "SELECT COUNT(*) AS n FROM delivery d WHERE NOT EXISTS "
            "(SELECT 1 FROM delivery_item i WHERE i.delivery_id = d.delivery_id)")

        self.check(
            "approved_without_inspection", "OBSERVATION",
            "APPROVED/PARTIALLY_DISTRIBUTED/COMPLETED with no PASSED inspection - "
            "state drift the API state machine prevents going forward",
            "SELECT COUNT(*) AS n FROM donation d "
            "WHERE d.donation_status IN "
            "  ('APPROVED','PARTIALLY_DISTRIBUTED','COMPLETED') AND NOT EXISTS "
            "  (SELECT 1 FROM inspection_log i WHERE i.donation_id = d.donation_id "
            "   AND i.safety_status = 'PASSED')")

        self.check(
            "duplicate_branch_deliveries", "OBSERVATION",
            "same donation to the same branch more than once - allowed by "
            "decision, surfaced so allocation can explain it",
            "SELECT COUNT(*) AS n FROM (SELECT donation_id, recipient_branch_id "
            "FROM delivery GROUP BY donation_id, recipient_branch_id "
            "HAVING COUNT(*) > 1) t")

        self.check(
            "expired_items_still_open", "OBSERVATION",
            "items past best_before on PENDING/SCHEDULED/COLLECTED donations",
            "SELECT COUNT(*) AS n FROM donation_item i "
            "JOIN donation d ON d.donation_id = i.donation_id "
            "WHERE d.donation_status IN ('PENDING','SCHEDULED','COLLECTED') "
            "  AND i.best_before < NOW()")

        self.check(
            "branches_without_manager", "OBSERVATION",
            "branches with no regional manager (nobody can review deliveries)",
            "SELECT COUNT(*) AS n FROM branch WHERE regional_manager_user_id IS NULL")

        self.check(
            "spoilage_by_non_operational", "OBSERVATION",
            "spoilage reported by a role that cannot normally witness it",
            "SELECT COUNT(*) AS n FROM spoilage_record s "
            "JOIN app_user u ON u.user_id = s.reported_by_user_id "
            "WHERE u.user_role NOT IN ('NGO_MANAGER','DRIVER','SAFETY_INSPECTOR')")

        # Authority-at-the-time cannot be reconstructed from current state.
        # These two are therefore OBSERVATIONS, not invariants: after a
        # legitimate, P1-approved role change or manager handover the
        # historical rows are still correct.
        self.check(
            "review_before_handover", "OBSERVATION",
            "reviews whose reviewer is no longer the receiving branch's manager - "
            "expected after a manager handover; the trigger guarantees the "
            "relationship at insert time, so this is a signal, not corruption",
            "SELECT COUNT(*) AS n FROM delivery_review rv "
            "JOIN delivery d ON d.delivery_id = rv.delivery_id "
            "JOIN branch b ON b.branch_id = d.recipient_branch_id "
            "WHERE b.regional_manager_user_id IS NULL "
            "   OR b.regional_manager_user_id <> rv.reviewer_user_id")

        # Pre-F4 there is no delivery-level driver. DELIVERY stores route_id;
        # ROUTE.designated_driver_user_id is that route's CURRENT designation,
        # not the person who drove a past delivery. Joining through the route
        # would manufacture history, so the question is reported as
        # unanswerable rather than answered wrongly.
        if self.exists("column:delivery", "driver_user_id"):
            self.check(
                "driver_role_changed_historical", "OBSERVATION",
                "completed deliveries attributed to a user who is no longer a "
                "DRIVER - legitimate after an approved role change, and the "
                "reason historic per-driver totals do not disappear",
                "SELECT COUNT(*) AS n FROM delivery d "
                "JOIN app_user u ON u.user_id = d.driver_user_id "
                "WHERE d.delivery_status IN ('DELIVERED','FAILED','CANCELLED') "
                "  AND u.user_role <> 'DRIVER'")
        else:
            self.not_available(
                "delivery_driver_history",
                "DELIVERY.driver_user_id is not present; the actual driver of a "
                "historical delivery cannot be established from the pre-F4 "
                "schema. DELIVERY stores only route_id, and "
                "ROUTE.designated_driver_user_id is the route's current "
                "designation, not necessarily the driver at delivery time. "
                "No attribution is inferred and no id is backfilled. Becomes "
                "auditable once F4 adds a nullable delivery.driver_user_id.")

        self.check(
            "route_driver_role_changed_inactive", "OBSERVATION",
            "INACTIVE routes whose former designated driver is no longer a "
            "DRIVER - expected after a P1-approved role change; keeps the route "
            "history readable without treating it as corruption. The same "
            "active/historical split applies to deliveries above.",
            "SELECT COUNT(*) AS n FROM route r "
            "JOIN app_user u ON u.user_id = r.designated_driver_user_id "
            "WHERE r.route_status <> 'ACTIVE' AND u.user_role <> 'DRIVER'")

        # Route assignments: distribution first, then only disallowed roles.
        print("\n  route_assignment by role")
        allowed = ", ".join(f"'{r}'" for r in ROUTE_ASSIGNMENT_ROLES)
        try:
            rows = self.q(
                "SELECT u.user_role AS role, COUNT(*) AS n, "
                f"       SUM(u.user_role IN ({allowed})) AS allowed_n "
                "FROM route_assignment ra "
                "JOIN app_user u ON u.user_id = ra.user_id "
                "GROUP BY u.user_role ORDER BY n DESC")
            if not rows:
                print("    (no route assignments)")
            for r in rows:
                flag = "allowed" if r["allowed_n"] == r["n"] else "DISALLOWED"
                print(f"    {r['role']:18} {r['n']:>4}  {flag}")
            print(f"    permitted roles: {', '.join(ROUTE_ASSIGNMENT_ROLES)}")
        except Exception as exc:  # noqa: BLE001
            self.failures.append(f"route_assignment distribution: {exc}")
            print(f"    COULD NOT RUN: {exc}")

        print("\n  The same rule is asserted as an INVARIANT in B.6 "
              "(route_assignment_role_allowed); the table above exists so a "
              "disallowed role is visible in context, not only as a count.")

    # -- B.8 ---------------------------------------------------------------
    def plans(self) -> None:
        for label, sql in [
            ("expiry monitor",
             "SELECT i.food_item_id, i.item_name, i.best_before FROM donation_item i "
             "JOIN donation d ON d.donation_id = i.donation_id "
             "WHERE d.donation_status IN ('PENDING','SCHEDULED','COLLECTED') "
             "ORDER BY i.best_before LIMIT 25"),
            ("donation list, page 1",
             "SELECT d.donation_id, u.full_name, d.donation_status, d.pickup_datetime "
             "FROM donation d JOIN app_user u ON u.user_id = d.donor_user_id "
             "ORDER BY d.pickup_datetime DESC LIMIT 25 OFFSET 0"),
            ("branch distribution",
             "SELECT b.branch_name, SUM(i.quantity_delivered_kg) AS kg FROM delivery d "
             "JOIN branch b ON b.branch_id = d.recipient_branch_id "
             "JOIN delivery_item i ON i.delivery_id = d.delivery_id "
             "WHERE d.delivery_status = 'DELIVERED' GROUP BY b.branch_id"),
            ("donor sustainability view (existing)",
             "SELECT * FROM vw_donor_sustainability LIMIT 20"),
            ("driver performance view (attributed via route)",
             "SELECT * FROM vw_driver_performance LIMIT 20"),
            ("proposed donor-impact query (B.11)", DONOR_IMPACT_SQL.strip()),
        ]:
            print(f"\n  {label}")
            try:
                first = True
                for row in self.q("EXPLAIN " + sql):
                    if first:
                        print("    " + " | ".join(row.keys()))
                        first = False
                    print("    " + " | ".join(str(v) for v in row.values()))
            except Exception as exc:  # noqa: BLE001
                self.failures.append(f"EXPLAIN {label}: {exc}")
                print(f"    COULD NOT RUN: {exc}")

    # -- B.9 ---------------------------------------------------------------
    def post_migration(self) -> None:
        print("Runs only when the proposed objects exist; otherwise skipped, not")
        print("failed, so the same script stays useful after each migration.\n")

        if self.exists("table", "user_credential"):
            self.check("cred_users_missing", "OBSERVATION",
                       "users with no credential (cannot log in until provisioned)",
                       "SELECT COUNT(*) AS n FROM app_user u LEFT JOIN user_credential c "
                       "ON c.user_id = u.user_id WHERE c.user_id IS NULL")
            self.check("cred_non_scrypt_hash", "INVARIANT",
                       "every stored hash is a Werkzeug scrypt hash, never plaintext",
                       "SELECT COUNT(*) AS n FROM user_credential "
                       "WHERE password_hash NOT LIKE 'scrypt:%'")
            self.check("cred_locked_out", "OBSERVATION",
                       "accounts currently locked by failed attempts",
                       "SELECT COUNT(*) AS n FROM user_credential "
                       "WHERE locked_until IS NOT NULL AND locked_until > NOW()")
        else:
            print("  skipped  user_credential (F1 not applied)")

        if self.exists("table", "donation_status_history"):
            self.check("hist_missing_donation", "INVARIANT",
                       "every donation has at least one history row",
                       "SELECT COUNT(*) AS n FROM donation d WHERE NOT EXISTS "
                       "(SELECT 1 FROM donation_status_history h "
                       " WHERE h.donation_id = d.donation_id)")
            self.check("hist_invented_timestamp", "INVARIANT",
                       "no reconstructed row carries a timestamp",
                       "SELECT COUNT(*) AS n FROM donation_status_history "
                       "WHERE is_reconstructed = 1 AND changed_at IS NOT NULL")
            self.check("hist_missing_timestamp", "INVARIANT",
                       "no recorded transition lacks its timestamp",
                       "SELECT COUNT(*) AS n FROM donation_status_history "
                       "WHERE is_reconstructed = 0 AND changed_at IS NULL")
            self.check("hist_duplicate_snapshot", "INVARIANT",
                       "one reconstructed snapshot per legacy donation",
                       "SELECT COUNT(*) AS n FROM (SELECT donation_id "
                       "FROM donation_status_history WHERE is_reconstructed = 1 "
                       "GROUP BY donation_id HAVING COUNT(*) > 1) t")
        else:
            print("  skipped  donation_status_history (F2 not applied)")

        if self.exists("column:donation", "pickup_address"):
            self.check("donation_missing_pickup_address", "OBSERVATION",
                       "donations without a pickup address (legacy NULL stays NULL; "
                       "shown as Not recorded, never inferred)",
                       "SELECT COUNT(*) AS n FROM donation WHERE pickup_address IS NULL")
        else:
            print("  skipped  donation.pickup_address (F3 not applied)")

        if self.exists("column:delivery", "driver_user_id"):
            self.check("driver_role_invalid_active", "INVARIANT",
                       "every PLANNED/IN_TRANSIT delivery is attributed to a user "
                       "who holds the DRIVER role NOW, whatever the route's "
                       "status - these are active work items; completed deliveries "
                       "are historical facts and are not re-validated",
                       "SELECT COUNT(*) AS n FROM delivery d "
                       "JOIN app_user u ON u.user_id = d.driver_user_id "
                       "WHERE d.delivery_status IN ('PLANNED','IN_TRANSIT') "
                       "  AND u.user_role <> 'DRIVER'")
            self.check("driver_legacy_null", "OBSERVATION",
                       "deliveries with no recorded driver (historical, excluded "
                       "from confirmed per-driver totals; no backfill by decision)",
                       "SELECT COUNT(*) AS n FROM delivery WHERE driver_user_id IS NULL")
            self.check("driver_confirmed_delivered_kg", "OBSERVATION",
                       "DELIVERED kg attributable to a RECORDED driver only",
                       "SELECT CAST(COALESCE(SUM(i.quantity_delivered_kg),0) AS SIGNED) AS n "
                       "FROM delivery d JOIN delivery_item i ON i.delivery_id = d.delivery_id "
                       "WHERE d.delivery_status = 'DELIVERED' AND d.driver_user_id IS NOT NULL")
            self.check("driver_unconfirmed_delivered_kg", "OBSERVATION",
                       "DELIVERED kg with no recorded driver (reported separately, "
                       "never attributed to the route's current driver)",
                       "SELECT CAST(COALESCE(SUM(i.quantity_delivered_kg),0) AS SIGNED) AS n "
                       "FROM delivery d JOIN delivery_item i ON i.delivery_id = d.delivery_id "
                       "WHERE d.delivery_status = 'DELIVERED' AND d.driver_user_id IS NULL")
        else:
            print("  skipped  delivery.driver_user_id (F4 not applied)")

        if self.exists("check", "chk_temperature_range"):
            self.check("temperature_out_of_range", "INVARIANT",
                       "no reading outside the approved -50..150 plausibility band "
                       "(input sanity, not a food-safety rule)",
                       "SELECT COUNT(*) AS n FROM inspection_log "
                       "WHERE temperature_c IS NOT NULL "
                       "AND (temperature_c < -50 OR temperature_c > 150)")
        else:
            print("  skipped  chk_temperature_range (F8 not applied)")

    # -- B.10 --------------------------------------------------------------
    def gate_self_test(self) -> None:
        print("Synthetic cases evaluated with the same predicate as B.6.")
        print("No table is read and nothing is written.\n")
        sql = (
            "WITH d(donation_id, st) AS ("
            "  SELECT 1,'DELIVERED' UNION ALL SELECT 2,'DELIVERED'"
            "  UNION ALL SELECT 3,'DELIVERED' UNION ALL SELECT 4,'DELIVERED'"
            "  UNION ALL SELECT 5,'PLANNED'),"
            "i(donation_id, inspection_id, safety_status, inspected_at) AS ("
            "  SELECT 2,1,'FAILED', NOW()"
            "  UNION ALL SELECT 3,1,'PASSED', NOW()"
            "  UNION ALL SELECT 4,1,'FAILED', NOW() - INTERVAL 1 DAY"
            "  UNION ALL SELECT 4,2,'PASSED', NOW())"
            "SELECT d.donation_id AS id, d.st, ("
            "  d.st IN ('IN_TRANSIT','DELIVERED') AND "
            + self.inspection_gate("d", "i") +
            ") AS flagged FROM d ORDER BY d.donation_id"
        )
        rows = self.q(sql)
        got = [(r["id"], bool(r["flagged"])) for r in rows]
        expected = [(1, True), (2, True), (3, False), (4, False), (5, False)]
        reasons = {
            1: "no inspection at all -> must be flagged",
            2: "latest inspection FAILED -> flagged",
            3: "latest inspection PASSED -> clear",
            4: "FAILED then PASSED -> clear (latest wins)",
            5: "status PLANNED -> gate not applicable",
        }
        for row_id, flagged in got:
            print(f"  case {row_id}: flagged={flagged!s:5} {reasons.get(row_id, '')}")
        self.want(got == expected, "inspection gate predicate",
                  "" if got == expected else f"got {got} expected {expected}")

    # -- B.11 --------------------------------------------------------------
    def donor_impact_preview(self) -> None:
        print("The existing view counts delivery allocations regardless of")
        print("delivery status. Below: the same donors under the proposed query")
        print("(DELIVERED only, CANCELLED excluded from all three aggregates,")
        print("spoiled kept separate) and the existing view. Nothing is created")
        print("or modified; this is a SELECT preview.\n")
        rows = self.q(DONOR_IMPACT_SQL)
        if not rows:
            print("  (no donor rows)")
            return
        old = {r["donor_id"]: r for r in self.q(
            "SELECT * FROM vw_donor_sustainability")}
        print(f"{'donor':26} {'donated':>9} {'DELIVERED':>9} {'spoiled':>8} "
              f"{'undistrib.':>11} {'view says':>10}")
        changed = 0
        for r in rows:
            donor_id = r["donor_id"]
            view_total = old.get(donor_id, {}).get("total_distributed_kg", 0) or 0
            delivered = float(r["delivered_kg"] or 0)
            if abs(float(view_total) - delivered) > 0.005:
                changed += 1
            print(f"{str(r['donor_name'])[:25]:26} "
                  f"{float(r['total_donated_kg'] or 0):>9.2f} "
                  f"{delivered:>9.2f} "
                  f"{float(r['spoiled_kg'] or 0):>8.2f} "
                  f"{float(r['undistributed_balance_kg'] or 0):>11.2f} "
                  f"{float(view_total):>10.2f}")
        print(f"\n  {changed} of {len(rows)} donor(s) differ between the proposed")
        print("  query and the existing view (the gap is un-DELIVERED allocations).")
        print("\n  Definitions used here:")
        print("    CANCELLED donations are excluded from ALL THREE aggregates, so a")
        print("    cancelled donation contributes nothing to donated, delivered or")
        print("    spoiled - the denominators cannot disagree with each other.")
        print("    total_donated_kg = SUM(donation_item.quantity_kg) over non-cancelled")
        print("                       donations")
        print("    delivered_kg     = SUM(delivery_item.quantity_delivered_kg) where")
        print("                       delivery.delivery_status = 'DELIVERED' and the")
        print("                       donation is not CANCELLED")
        print("    spoiled_kg       = SUM(spoilage_record.quantity_spoiled_kg) over")
        print("                       non-cancelled donations, kept separate so it is")
        print("                       never counted as impact")
        print("    undistributed_balance_kg = donated - delivered - spoiled. This is an")
        print("                       ACCOUNTING BALANCE, not a physical stock figure:")
        print("                       the food may be in transit, awaiting inspection,")
        print("                       or already gone without a recorded delivery or")
        print("                       spoilage entry. Label it 'undistributed balance',")
        print("                       never 'on hand' or 'remaining stock'.")


# --------------------------------------------------------------------------
# negative probes - opt-in, *_dev only
# --------------------------------------------------------------------------
def run_negative_probes() -> int:
    cfg = db_config()
    if not cfg["database"].endswith("_dev"):
        print("REFUSED: negative probes may only run against a *_dev database.")
        print(f"         DB_NAME is {cfg['database']!r}.")
        return 1

    print("Negative probes: each statement MUST be rejected by the server.")
    print("All attempts run in one transaction that is rolled back.\n")
    conn, _driver = connect_mysql()
    cur = conn.cursor()
    failures = 0
    probes: list[tuple[str, str, Any]] = []
    try:
        cur.execute("START TRANSACTION")

        def one_row(sql: str) -> Any:
            cur.execute(sql)
            return cur.fetchone()

        donation = one_row("SELECT donation_id FROM donation ORDER BY donation_id LIMIT 1")
        category = one_row("SELECT category_id FROM food_category ORDER BY category_id LIMIT 1")
        user = one_row("SELECT user_id FROM app_user ORDER BY user_id LIMIT 1")
        route = one_row("SELECT route_id FROM route ORDER BY route_id LIMIT 1")
        item = one_row("SELECT food_item_id FROM donation_item ORDER BY food_item_id LIMIT 1")

        if donation and category:
            probes.append((
                "chk_donation_quantity",
                "INSERT INTO donation_item (donation_id, category_id, item_name, "
                "quantity_kg, prepared_at, best_before) VALUES (%s, %s, "
                "'audit probe', -1, NULL, NOW() + INTERVAL 1 DAY)",
                (donation[0], category[0])))
            probes.append((
                "chk_food_dates",
                "INSERT INTO donation_item (donation_id, category_id, item_name, "
                "quantity_kg, prepared_at, best_before) VALUES (%s, %s, "
                "'audit probe', 1, NOW(), NOW() - INTERVAL 1 DAY)",
                (donation[0], category[0])))
        if user and route:
            probes.append((
                "chk_route_hours",
                "INSERT INTO route_assignment (user_id, route_id, hours_per_week, "
                "assigned_date) VALUES (%s, %s, 0, CURDATE())",
                (user[0], route[0])))
        if item and user:
            probes.append((
                "chk_spoilage_quantity",
                "INSERT INTO spoilage_record (food_item_id, reported_by_user_id, "
                "quantity_spoiled_kg, reported_at, reason) VALUES (%s, %s, -1, "
                "NOW(), 'audit probe')",
                (item[0], user[0])))

        if not probes:
            print("  SKIPPED: no parent rows available to build probes.")
            return 1

        for label, sql, args in probes:
            try:
                cur.execute(sql, args)
            except Exception as exc:  # noqa: BLE001 - rejection is the pass
                errno = getattr(exc, "errno", None)
                if errno is None:
                    m = re.search(r"\((\d{4})\)", str(exc))
                    errno = int(m.group(1)) if m else None
                ok = errno in (3819, 1644)
                print(f"  {'PASS' if ok else 'FAIL'}  {label:26} rejected errno={errno}")
                if not ok:
                    failures += 1
            else:
                print(f"  FAIL  {label:26} ACCEPTED the violating row - "
                      f"constraint not enforced")
                failures += 1
    finally:
        try:
            conn.rollback()
            print("\n  rollback issued; nothing was committed")
        except Exception as exc:  # noqa: BLE001
            print(f"\n  ROLLBACK FAILED: {exc} - check the database immediately")
            failures += 1
        try:
            cur.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    print(f"\nNegative probes: {len(probes) - failures} passed, {failures} failed")
    return 0 if failures == 0 else 1


# --------------------------------------------------------------------------
# self-test: comparator + parser, no database
# --------------------------------------------------------------------------
def build_fake_catalog(schema: dict[str, Any], db: str) -> dict[str, Any]:
    """Derive catalog rows from the export, then dirty them the way a real
    server would: views listed among tables, DB-qualified view text,
    reformatted trigger bodies, DEFINER noise."""
    tables = schema["tables"]
    cat: dict[str, Any] = {}

    cat["objects"] = (
        [{"t": t, "tt": "BASE TABLE"} for t in tables]
        + [{"t": v, "tt": "VIEW"} for v in schema["views"]]
    )

    cols = []
    for t, info in tables.items():
        for c, d in info["columns"].items():
            cols.append({"t": t, "c": c, "ty": d["type"],
                         "nul": "YES" if d["nullable"] else "NO",
                         "def": d["default"], "ex": d["extra"]})
    cat["columns"] = cols

    cat["pk"] = [{"t": t, "cols": ",".join(i["pk"])} for t, i in tables.items()]

    idx = []
    for t, i in tables.items():
        for name, (uniq, cs) in i["keys"].items():
            idx.append({"t": t, "i": name, "nu": 0 if uniq else 1,
                        "cols": ",".join(cs)})
    cat["indexes"] = idx

    fks = []
    for t, i in tables.items():
        for name, f in i["fks"].items():
            fks.append({"t": t, "c": name, "cols": ",".join(f["columns"]),
                        "rt": f["ref_table"], "rcols": ",".join(f["ref_columns"]),
                        "dr": f["on_delete"], "ur": f["on_update"]})
    cat["fks"] = fks

    cat["checks"] = [
        {"t": t, "c": name, "cl": clause, "en": "YES"}
        for t, i in tables.items() for name, clause in i["checks"].items()
    ]

    # Trigger bodies: re-mess them the way mysqldump/server text differs.
    trig = []
    for name, tr in schema["triggers"].items():
        body = tr["body"]
        messy = ("/*!50003 DEFINER=`root`@`localhost`*/ " + body
                 .replace(";", ";\n    ")
                 .replace("begin", "BEGIN\n  ")
                 + "\n")
        trig.append({"n": name, "t": tr["table"], "tm": tr["timing"],
                     "e": tr["event"], "body": messy})
    cat["triggers"] = trig

    # Views: server output qualifies objects with the schema name.
    cat["views"] = [
        {"n": name, "d": re.sub(r"\bfrom ", f"from `{db}`.", body)}
        for name, body in schema["views"].items()
    ]

    cat["table_options"] = [
        {"t": t, "e": "InnoDB", "coll": i["collation"]} for t, i in tables.items()
    ]
    return cat


class FakeAudit(LiveAudit):
    """LiveAudit with q() served from a canned catalog.

    has_driver_column models the schema generation: False = pre-F4 (no
    delivery.driver_user_id), True = post-F4.
    """

    def __init__(self, catalog: dict[str, Any], db: str,
                 has_driver_column: bool = False) -> None:  # noqa: D107
        self.catalog = catalog
        self.db = db
        self.has_driver_column = has_driver_column
        self.driver = "fake"
        self.failures = []
        self.warnings = []
        self.results = []
        self.read_only = True
        self.conn = None
        self.cur = None

    def q(self, sql: str, args: Any = None) -> list[dict[str, Any]]:
        s = sql.lower()
        if "table_type as tt" in s and "information_schema.tables" in s:
            return self.catalog["objects"]
        if "information_schema.columns" in s and "column_type" in s:
            return self.catalog["columns"]
        if "index_name='primary'" in s:
            return self.catalog["pk"]
        if "index_name<>'primary'" in s:
            return self.catalog["indexes"]
        if "referential_constraints" in s:
            return self.catalog["fks"]
        if "table_constraints" in s and "enforced" in s and "column_name='enforced'" in s:
            return [{"x": 1}]
        if "constraint_type='check'" in s:
            return self.catalog["checks"]
        if "information_schema.triggers" in s:
            return self.catalog["triggers"]
        if "information_schema.views" in s:
            return self.catalog["views"]
        if "table_collation" in s:
            return self.catalog["table_options"]
        if "column_name=" in s:
            # exists('column:delivery','driver_user_id')
            return [{"x": 1}] if self.has_driver_column else []
        if "group by u.user_role" in s:
            return [{"role": "DRIVER", "n": 5, "allowed_n": 5},
                    {"role": "SAFETY_INSPECTOR", "n": 3, "allowed_n": 3}]
        if " as n" in s:
            return [{"n": 0}]
        raise AssertionError(f"FakeAudit has no answer for: {sql[:120]}")


def run_self_test() -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: {SCHEMA_PATH} not found")
        return 1
    schema = parse_schema()
    db = "smart_food_supply_chain"
    failures = 0

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  {'PASS' if cond else 'FAIL'}  {label}"
              + (f"   {detail}" if detail else ""))
        if not cond:
            failures += 1

    hr("SELF-TEST 1 - export parsing")
    check("15 tables parsed", len(schema["tables"]) == 15, str(len(schema["tables"])))
    check("2 views parsed", len(schema["views"]) == 2, ",".join(schema["views"]))
    check("16 triggers parsed", len(schema["triggers"]) == 16,
          str(len(schema["triggers"])))
    check("6 CHECK constraints parsed", len(schema["checks"]) == 6)
    check("25 foreign keys parsed",
          sum(len(t["fks"]) for t in schema["tables"].values()) == 25)
    check("86 columns parsed",
          sum(len(t["columns"]) for t in schema["tables"].values()) == 86, "")
    check("trigger bodies end with END",
          all(t["body"].strip().lower().endswith("end")
              for t in schema["triggers"].values()))
    check("view definitions contain SELECT",
          all(v.strip().lower().startswith("select")
              for v in schema["views"].values()))

    hr("SELF-TEST 2 - clean catalog produces no structural failures")
    audit = FakeAudit(build_fake_catalog(schema, db), db)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit.compare_export(schema)
    out = buf.getvalue()
    check("no structural failures", not audit.failures, str(audit.failures[:3]))
    check("no warnings", not audit.warnings, str(audit.warnings[:3]))
    check("views not reported as extra tables",
          "extra=[]" in out or "extra=['" not in out.split("table set matches")[1][:200])
    check("16 triggers reported equivalent",
          out.count("trigger ") >= 16 and "SEMANTIC" not in out)
    check("2 views reported equivalent",
          out.count("view vw_") == 2 and "SEMANTIC" not in out)
    check("all columns PASS", out.count("FAIL") == 0)

    hr("SELF-TEST 3 - semantic difference is detected, not hidden")
    bad = build_fake_catalog(schema, db)
    target = "trg_delivery_inspection_insert"
    for row in bad["triggers"]:
        if row["n"] == target:
            row["body"] = row["body"].replace("'PASSED'", "'FAILED'")
    audit2 = FakeAudit(bad, db)
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit2.compare_export(schema)
    out2 = buf.getvalue()
    check("semantic trigger difference fails the comparison",
          any(target in f for f in audit2.failures), str(audit2.failures[:2]))
    check("a unified diff is printed", "@@" in out2 and "+" in out2)
    check("only one trigger flagged",
          sum(1 for f in audit2.failures if "trigger " in f) == 1,
          str([f for f in audit2.failures if "trigger " in f]))

    hr("SELF-TEST 4 - structural differences are detected")
    bad2 = build_fake_catalog(schema, db)
    for row in bad2["columns"]:
        if row["t"] == "donation_item" and row["c"] == "quantity_kg":
            row["ty"] = "decimal(10,2)"
    audit3 = FakeAudit(bad2, db)
    buf = io.StringIO()
    with redirect_stdout(buf):
        audit3.compare_export(schema)
    check("column type drift fails",
          any("donation_item.columns" in f for f in audit3.failures),
          str(audit3.failures[:2]))

    hr("SELF-TEST 5 - proposed donor-impact query shape")
    sql_up = " ".join(DONOR_IMPACT_SQL.split())
    cancelled_filters = sql_up.count("donation_status <> 'CANCELLED'")
    check("CANCELLED excluded from all three aggregates",
          cancelled_filters == 3, f"occurrences={cancelled_filters}")
    check("delivered_kg restricted to DELIVERED",
          "d2.delivery_status = 'DELIVERED'" in sql_up)
    check("balance is labelled undistributed, not stock",
          "undistributed_balance_kg" in sql_up
          and "remaining_kg" not in sql_up)
    check("spoiled kept as its own column",
          "AS spoiled_kg" in sql_up)

    hr("SELF-TEST 6 - normalisation rules")
    check("whitespace/backticks ignored",
          sql_equivalent("BEGIN  IF `a` > 0 THEN\n END", "begin if a>0 then end")[0])
    check("DEFINER comment ignored",
          sql_equivalent("/*!50003 DEFINER=`root`@`localhost`*/ BEGIN END",
                         "BEGIN END")[0])
    check("database qualification ignored",
          sql_equivalent(f"select * from `{db}`.app_user",
                         "select * from app_user", db)[0])
    check("alias qualification preserved (alias use is semantic)",
          not sql_equivalent("select u.id from app_user u",
                             "select x.id from app_user u")[0])
    check("IFNULL/COALESCE treated as equivalent",
          sql_equivalent("select ifnull(a,0)", "select coalesce(a,0)")[0])
    check("<>/!= treated as equivalent",
          sql_equivalent("select 1 where a != 2", "select 1 where a <> 2")[0])
    check("changed literal is a semantic difference",
          not sql_equivalent("if s='PASSED' then", "if s='FAILED' then")[0])
    check("missing inspection is flagged by the gate",
          "NOT EXISTS" in LiveAudit.inspection_gate())

    hr("SELF-TEST 7 - pre-F4 historical driver is a limitation, not a failure")
    pre = FakeAudit(build_fake_catalog(schema, db), db)  # no driver column
    buf = io.StringIO()
    with redirect_stdout(buf):
        pre.observations()
        pre_code = pre.summary()
    pre_out = buf.getvalue()
    verdicts = {r[0]: r[1] for r in pre.results}
    check("delivery_driver_history reported NOT AVAILABLE",
          verdicts.get("delivery_driver_history") == "NOT AVAILABLE",
          str(verdicts.get("delivery_driver_history")))
    check("the pre-F4 SQL is never executed",
          "driver_role_changed_historical" not in verdicts)
    check("no failure recorded for the limitation",
          not pre.failures, str(pre.failures[:2]))
    check("no check reported COULD NOT RUN",
          "COULD NOT RUN" not in verdicts.values())
    check("explanation names the missing column and the route caveat",
          "driver_user_id" in pre_out and "NOT AVAILABLE" in pre_out
          and "current" in pre_out.lower())
    check("exit code stays 0", pre_code == 0, f"code={pre_code}")
    check("the nine other observations still run",
          sum(1 for v in verdicts.values() if v in ("PASS", "OBSERVE")) == 9,
          str(sorted(verdicts)))

    post = FakeAudit(build_fake_catalog(schema, db), db, has_driver_column=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        post.observations()
    post_verdicts = {r[0]: r[1] for r in post.results}
    check("after F4 the historical-driver observation runs",
          post_verdicts.get("driver_role_changed_historical") == "OBSERVE",
          str(post_verdicts.get("driver_role_changed_historical")))
    check("post-F4 leaves no NOT AVAILABLE entry",
          "NOT AVAILABLE" not in post_verdicts.values())

    print()
    print(f"SELF-TEST RESULT: {'PASS' if failures == 0 else 'FAIL'} "
          f"({failures} failed assertion(s))")
    return 0 if failures == 0 else 1


# --------------------------------------------------------------------------
def main() -> int:
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    if "--baseline" in args:
        i = args.index("--baseline")
        if i + 1 >= len(args):
            print("--baseline needs a path", file=sys.stderr)
            return 1
        if not Path(args[i + 1]).expanduser().is_file():
            print(f"ERROR: --baseline {args[i + 1]} not found",
                  file=sys.stderr)
            return 1
        set_baseline(args[i + 1])

    if "--self-test" in args:
        return run_self_test()

    out_path = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            print("--out needs a path", file=sys.stderr)
            return 1
        out_path = args[i + 1]
    probes = "--negative-probes" in args

    tee = Tee(out_path)
    sys.stdout = tee
    try:
        if not SCHEMA_PATH.exists():
            print(f"ERROR: {SCHEMA_PATH} not found")
            return 1

        origin = ("frozen original" if SCHEMA_PATH == DEFAULT_SCHEMA_PATH
                  else "override via --baseline")
        print(f"BASELINE: {SCHEMA_PATH}  ({origin})")
        schema = parse_schema()
        print_static(schema)

        hr("B. LIVE DATABASE INSPECTION (read-only)")
        try:
            conn, driver = connect_mysql()
        except AuditError as exc:
            print(f"NOT CONNECTED\n  {exc}")
            print()
            print("No live check ran. Row counts, the definition comparisons and")
            print("every invariant are UNVERIFIED.")
            print("Set DB_USER and DB_PASSWORD (or DB_PASSWORD_FILE) and re-run:")
            print('  $env:DB_USER="root"; $env:DB_PASSWORD="***"; '
                  "python database/audit_db.py --out audit-report.txt")
            return 2

        audit = LiveAudit(conn, driver, os.environ.get(
            "DB_NAME", "smart_food_supply_chain"))
        try:
            audit.start()
            audit.section("B.1 SERVER", audit.server)
            audit.section("B.2 ROW COUNTS (COUNT(*), authoritative)", audit.row_counts)
            audit.section("B.3 LIVE vs EXPORT (definitions, semantic)",
                          lambda: audit.compare_export(schema))
            audit.section("B.4 OBJECTS", audit.objects)
            audit.section("B.5 DATA PROFILE", audit.profile)
            audit.section("B.6 INTEGRITY - INVARIANTS", audit.invariants)
            audit.section("B.7 INTEGRITY - OBSERVATIONS", audit.observations)
            audit.section("B.8 QUERY PLANS", audit.plans)
            audit.section("B.9 POST-MIGRATION CHECKS", audit.post_migration)
            audit.section("B.10 INSPECTION GATE SELF-TEST", audit.gate_self_test)
            audit.section("B.11 DONOR IMPACT - PROPOSED QUERY PREVIEW",
                          audit.donor_impact_preview)

            code = audit.summary()
        finally:
            for closer in (conn.rollback, audit.cur.close, conn.close):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass

        if probes:
            hr("C. NEGATIVE PROBES (opt-in, *_dev only, rolled back)")
            return run_negative_probes()
        return code
    finally:
        sys.stdout = tee.stdout
        tee.close()


if __name__ == "__main__":
    raise SystemExit(main())
