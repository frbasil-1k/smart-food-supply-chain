#!/usr/bin/env python
"""SQL-layer test matrix for Phase 2 (TEST_MATRIX.md), run against the disposable
clone `smart_food_supply_chain_phase2_test_dev` only.

API-layer rows (F1-10..16, F2-07..11, F3-02..08, F4b-09..12, F5-14..17, F8-05..07)
are NOT run here: they need the service that Phase 3 builds. They are reported
DEFERRED, never PASSED.

Every case runs as its own mysql invocation so an expected error cannot poison a
later case. Nothing here touches smart_food_supply_chain or the _dev database:
the script hard-refuses any database name that is not the test clone.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

MYSQL = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
CNF = str(pathlib.Path.home() / ".sfc_phase2.cnf")
DB = "smart_food_supply_chain_phase2_test_dev"
OUT = pathlib.Path("reports/phase2/evidence/sql_test_results.txt")


def run(sql: str) -> subprocess.CompletedProcess:
    if not DB.endswith("_test_dev"):
        raise SystemExit("refusing: not a test clone")
    return subprocess.run(
        [MYSQL, f"--defaults-extra-file={CNF}", "--protocol=TCP", "-h", "127.0.0.1",
         "-P", "3306", "--batch", "--skip-column-names", DB, "-e", sql],
        capture_output=True, text=True)


def code_of(proc: subprocess.CompletedProcess) -> int | None:
    m = re.search(r"ERROR (\d+)", proc.stderr)
    return int(m.group(1)) if m else None


def value(sql: str) -> str:
    proc = run(sql)
    if proc.returncode != 0:
        return "QUERY-ERROR:" + proc.stderr.strip().splitlines()[0][:120]
    return proc.stdout.strip()


results: list[tuple[str, str, str, str]] = []  # id, description, expected, observed


def check_ok(cid: str, desc: str, sql: str) -> None:
    proc = run(sql)
    ok = proc.returncode == 0
    results.append((cid, desc, "accepted",
                    "accepted" if ok else f"ERROR {code_of(proc)}: "
                    f"{proc.stderr.strip().splitlines()[0][:90]}"))
    if not ok:
        print(f"  !! {cid} unexpected error: {proc.stderr.strip()[:160]}")


def check_error(cid: str, desc: str, sql: str, expect: int) -> None:
    proc = run(sql)
    got = code_of(proc)
    results.append((cid, desc, f"ERROR {expect}",
                    f"ERROR {got}" if got else "accepted (no error)"))
    if got != expect:
        print(f"  !! {cid} expected {expect}, got {got or 'success'}: "
              f"{(proc.stderr or proc.stdout).strip()[:160]}")


def check_value(cid: str, desc: str, sql: str, expect: str) -> None:
    got = value(sql)
    results.append((cid, desc, expect, got))
    if got != expect:
        print(f"  !! {cid} expected {expect!r}, got {got!r}")


# ---------------------------------------------------------------- discovery
driver_id = value("SELECT user_id FROM app_user WHERE user_role='DRIVER' AND account_status='ACTIVE' LIMIT 1;")
manager_id = value("SELECT user_id FROM app_user WHERE user_role='NGO_MANAGER' LIMIT 1;")
inspector_id = value("SELECT user_id FROM app_user WHERE user_role='SAFETY_INSPECTOR' LIMIT 1;")
donor2_id = value("SELECT donor_user_id FROM donation WHERE donation_id=2 LIMIT 1;")
item_with_children = value(
    "SELECT i.food_item_id FROM donation_item i "
    "JOIN (SELECT food_item_id, SUM(q) q FROM ("
    "  SELECT food_item_id, quantity_delivered_kg q FROM delivery_item "
    "  UNION ALL SELECT food_item_id, quantity_spoiled_kg q FROM spoilage_record"
    ") x GROUP BY food_item_id) c ON c.food_item_id=i.food_item_id ORDER BY c.q DESC LIMIT 1;")
committed = value(
    "SELECT COALESCE((SELECT SUM(quantity_delivered_kg) FROM delivery_item WHERE food_item_id=%s),0)"
    "+ COALESCE((SELECT SUM(quantity_spoiled_kg) FROM spoilage_record WHERE food_item_id=%s),0);"
    % (item_with_children, item_with_children))
item_donation = value(f"SELECT donation_id FROM donation_item WHERE food_item_id={item_with_children};")
other_donation = value(f"SELECT donation_id FROM donation WHERE donation_id <> {item_donation} LIMIT 1;")

print("discovery:")
print(f"  driver={driver_id} manager={manager_id} item={item_with_children} "
      f"committed={committed} donation={item_donation} other_donation={other_donation}")

# ------------------------------------------------------------------- F1 (user_credential)
check_value("F1-01", "credentials after migration", "SELECT COUNT(*) FROM user_credential;", "0")
check_ok("F1-02a", "first credential for user 15",
         "INSERT INTO user_credential (user_id, password_hash) VALUES (15,'scrypt:32768:8:1$s$d');")
check_error("F1-02b", "second credential for same user", 
            "INSERT INTO user_credential (user_id, password_hash) VALUES (15,'scrypt:x');", 1062)
check_error("F1-03", "credential for nonexistent user",
            "INSERT INTO user_credential (user_id, password_hash) VALUES (999999,'x');", 1452)
check_ok("F1-04", "plaintext hash accepted by SQL (AUD flags it)",
         "INSERT INTO user_credential (user_id, password_hash) VALUES (14,'plaintext123');")
check_error("F1-05", "locked_until with failed_attempts = 0",
            "INSERT INTO user_credential (user_id,password_hash,failed_attempts,locked_until) "
            "VALUES (13,'h',0,'2030-01-01 00:00:00');", 3819)
check_error("F1-06", "token hash without expiry",
            "INSERT INTO user_credential (user_id,password_hash,reset_token_hash) "
            "VALUES (12,'h',REPEAT('a',64));", 3819)
check_error("F1-07", "expiry without token hash",
            "INSERT INTO user_credential (user_id,password_hash,reset_expires_at) "
            "VALUES (11,'h','2030-01-01 00:00:00');", 3819)
check_ok("F1-08a", "token pair set together",
         "UPDATE user_credential SET reset_token_hash=REPEAT('b',64), "
         "reset_expires_at='2030-01-01 00:00:00' WHERE user_id=15;")
check_ok("F1-08b", "token pair cleared together",
         "UPDATE user_credential SET reset_token_hash=NULL, reset_expires_at=NULL WHERE user_id=15;")
# F1-09: the cascade can only be observed on a user no other table references,
# so find an unreferenced user rather than assuming one.
cascade_uid = None
for uid in range(1, 16):
    if uid in {driver_id, manager_id, inspector_id, donor2_id}:
        continue
    run(f"DELETE FROM user_credential WHERE user_id={uid};")
    run(f"INSERT INTO user_credential (user_id,password_hash) VALUES ({uid},'scrypt:c');")
    proc = run(f"DELETE FROM app_user WHERE user_id={uid};")
    if proc.returncode == 0:
        cascade_uid = uid
        break
    run(f"DELETE FROM user_credential WHERE user_id={uid};")
if cascade_uid is None:
    results.append(("F1-09", "deleting app_user cascades the credential row",
                    "accepted", "no unreferenced user available"))
else:
    results.append(("F1-09", f"deleting app_user {cascade_uid} cascades the credential row",
                    "accepted", "accepted"))
    check_value("F1-09b", "credential row removed with its user",
                f"SELECT COUNT(*) FROM user_credential WHERE user_id={cascade_uid};", "0")
check_value("F1-09c", "fk_credential_user declares ON DELETE CASCADE",
            "SELECT DELETE_RULE FROM information_schema.referential_constraints "
            "WHERE constraint_schema=DATABASE() AND constraint_name='fk_credential_user';", "CASCADE")

# --------------------------------------------------- F2a (history structure)
check_value("F2a-B", "history rows after 002b", "SELECT COUNT(*) FROM donation_status_history;", "5")
check_error("F2a-02", "UPDATE on append-only history",
            "UPDATE donation_status_history SET note='x' WHERE history_id=1;", 1644)
check_error("F2a-03", "DELETE on append-only history",
            "DELETE FROM donation_status_history WHERE history_id=1;", 1644)
check_error("F2a-04", "genuine row with NULL changed_at",
            "INSERT INTO donation_status_history (donation_id,to_status,changed_at,is_reconstructed) "
            f"VALUES ({item_donation},'APPROVED',NULL,0);", 3819)
check_error("F2a-05", "reconstructed row with changed_at",
            "INSERT INTO donation_status_history (donation_id,to_status,changed_at,is_reconstructed) "
            f"VALUES ({item_donation},'APPROVED','2026-01-01 00:00:00',1);", 3819)
check_error("F2a-06", "reconstructed row with an actor",
            "INSERT INTO donation_status_history (donation_id,to_status,changed_by_user_id,changed_at,is_reconstructed) "
            f"VALUES ({item_donation},'APPROVED',{driver_id},NULL,1);", 3819)
check_error("F2a-07", "from_status = to_status",
            "INSERT INTO donation_status_history (donation_id,from_status,to_status,changed_at,is_reconstructed) "
            f"VALUES ({item_donation},'APPROVED','APPROVED','2026-01-01 00:00:00',0);", 3819)
check_error("F2a-08", "second reconstructed row for one donation",
            "INSERT INTO donation_status_history (donation_id,to_status,changed_at,is_reconstructed) "
            f"VALUES ({item_donation},'APPROVED',NULL,1);", 1062)
check_ok("F2a-09a", "genuine row 1 for one donation",
         "INSERT INTO donation_status_history (donation_id,from_status,to_status,changed_by_user_id,changed_at,is_reconstructed) "
         f"VALUES ({item_donation},'APPROVED','PARTIALLY_DISTRIBUTED',{manager_id},'2026-01-02 00:00:00',0);")
check_ok("F2a-09b", "genuine row 2 for the same donation",
         "INSERT INTO donation_status_history (donation_id,from_status,to_status,changed_by_user_id,changed_at,is_reconstructed) "
         f"VALUES ({item_donation},'PARTIALLY_DISTRIBUTED','COMPLETED',{manager_id},'2026-01-03 00:00:00',0);")
check_error("F2a-10", "to_status outside the enum",
            "INSERT INTO donation_status_history (donation_id,to_status,changed_at,is_reconstructed) "
            f"VALUES ({item_donation},'BOGUS','2026-01-01 00:00:00',0);", 1265)

# ------------------------------------------------------ F2b (backfill results)
check_value("F2b-01", "reconstructed snapshots", "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1;", "5")
check_value("F2b-02", "donations with no history",
            "SELECT COUNT(*) FROM donation d LEFT JOIN donation_status_history h "
            "ON h.donation_id=d.donation_id WHERE h.history_id IS NULL;", "0")
check_value("F2b-03", "duplicate snapshots per donation",
            "SELECT COUNT(*) FROM (SELECT donation_id FROM donation_status_history "
            "WHERE is_reconstructed=1 GROUP BY donation_id HAVING COUNT(*)>1) x;", "0")
check_value("F2b-04", "every reconstructed row carries the approved note",
            "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1 "
            "AND note IS NOT NULL;", "5")
print("  reconstructed note text:", value(
    "SELECT DISTINCT note FROM donation_status_history WHERE is_reconstructed=1;"))
check_value("F2b-05", "no fabricated timestamps", 
            "SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed=1 AND changed_at IS NOT NULL;", "0")

# --------------------------------------------------- F3 (pickup columns, structure)
check_value("F3-01", "legacy pickup NULLs (address/pincode/contact)",
            "SELECT CONCAT(SUM(pickup_address IS NULL),'/',SUM(pickup_pincode IS NULL),'/',"
            "SUM(pickup_contact IS NULL)) FROM donation;", "5/5/5")
check_value("X-02", "new column collation",
            "SELECT DISTINCT TABLE_COLLATION FROM information_schema.columns c "
            "JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name "
            "WHERE c.table_schema=DATABASE() AND c.column_name IN "
            "('pickup_address','pickup_pincode','pickup_contact','driver_user_id','scheduled_for','temperature_c') "
            "AND t.table_type='BASE TABLE';", "utf8mb4_0900_ai_ci")

# ------------------------------------------------------------ F4a (structure)
check_value("F4a-01", "legacy driver/schedule NULLs",
            "SELECT CONCAT(SUM(driver_user_id IS NULL),'/',SUM(scheduled_for IS NULL)) FROM delivery;", "5/5")
check_error("F4a-02", "unknown driver id (the BEFORE INSERT trigger rejects the role first)",
            "INSERT INTO delivery (donation_id,route_id,recipient_branch_id,driver_user_id) "
            f"VALUES ({item_donation},1,1,999999);", 1644)
check_value("F4a-02b", "fk_delivery_driver exists and references app_user",
            "SELECT CONCAT(referenced_table_name,'.',"
            "(SELECT GROUP_CONCAT(k.referenced_column_name) FROM information_schema.key_column_usage k "
            " WHERE k.constraint_schema=DATABASE() AND k.constraint_name='fk_delivery_driver')) "
            "FROM information_schema.referential_constraints "
            "WHERE constraint_schema=DATABASE() AND constraint_name='fk_delivery_driver';", "app_user.user_id")
check_ok("F4a-03a", "two deliveries, same donation+branch (row 1)",
         f"INSERT INTO delivery (donation_id,route_id,recipient_branch_id) VALUES ({item_donation},1,1);")
check_ok("F4a-03b", "two deliveries, same donation+branch (row 2)",
         f"INSERT INTO delivery (donation_id,route_id,recipient_branch_id) VALUES ({item_donation},1,1);")
check_value("F4a-04", "no unique index on (donation_id, recipient_branch_id)",
            "SELECT COUNT(*) FROM information_schema.statistics s WHERE s.table_schema=DATABASE() "
            "AND s.table_name='delivery' AND s.non_unique=0 AND s.index_name<>'PRIMARY' "
            "AND (SELECT GROUP_CONCAT(column_name ORDER BY seq_in_index) FROM information_schema.statistics "
            "     WHERE table_schema=DATABASE() AND table_name='delivery' AND index_name=s.index_name)"
            " = 'donation_id,recipient_branch_id';", "0")

# ------------------------------------------------------------- F4b (triggers)
new_delivery = value(f"SELECT MAX(delivery_id) FROM delivery WHERE donation_id={item_donation};")
check_error("F4b-01", "assign a manager as driver",
            f"UPDATE delivery SET driver_user_id={manager_id} WHERE delivery_id={new_delivery};", 1644)
check_ok("F4b-02", "assign a real DRIVER",
         f"UPDATE delivery SET driver_user_id={driver_id} WHERE delivery_id={new_delivery};")
check_ok("F4b-03", "later unrelated UPDATE of the same row",
         f"UPDATE delivery SET scheduled_for='2027-02-01 09:00:00' WHERE delivery_id={new_delivery};")
check_ok("F4b-04a", "R3: driver's role later changed away from DRIVER",
         f"UPDATE app_user SET user_role='DONOR' WHERE user_id={driver_id};")
check_ok("F4b-04b", "R3: unrelated update still accepted",
         f"UPDATE delivery SET delivery_status='PLANNED' WHERE delivery_id={new_delivery};")
check_ok("F4b-04c", "restore the driver's role",
         f"UPDATE app_user SET user_role='DRIVER' WHERE user_id={driver_id};")
check_error("F4b-05", "change attribution on a DELIVERED row",
            f"UPDATE delivery SET driver_user_id={driver_id} "
            "WHERE delivery_id=1 AND delivery_status='DELIVERED';", 1644)
check_ok("F4b-06", "update another column of a legacy DELIVERED row",
         "UPDATE delivery SET scheduled_for=scheduled_for WHERE delivery_id=1;")
check_value("F4b-06b", "legacy driver still NULL after that update",
            "SELECT COUNT(*) FROM delivery WHERE delivery_id=1 AND driver_user_id IS NULL;", "1")
check_ok("F4b-07a", "clear the driver then attempt IN_TRANSIT",
         f"UPDATE delivery SET driver_user_id=NULL, delivery_status='PLANNED' WHERE delivery_id={new_delivery};")
check_error("F4b-07b", "IN_TRANSIT without a driver (real probe)",
            f"UPDATE delivery SET delivery_status='IN_TRANSIT' WHERE delivery_id={new_delivery};", 1644)
check_ok("F4b-08", "IN_TRANSIT with a valid driver",
         f"UPDATE delivery SET driver_user_id={driver_id}, delivery_status='IN_TRANSIT' WHERE delivery_id={new_delivery};")

# --------------------------------------------------------- F5 (item guard)
check_error("F5-04", "reduce below committed (delivered + spoiled)",
            f"UPDATE donation_item SET quantity_kg={float(committed) - 0.01:.2f} "
            f"WHERE food_item_id={item_with_children};", 1644)
check_ok("F5-03", "reduce to exactly the committed amount (inclusive boundary)",
         f"UPDATE donation_item SET quantity_kg={committed} WHERE food_item_id={item_with_children};")
check_ok("F5-01", "increase above donated",
         f"UPDATE donation_item SET quantity_kg={float(committed) + 50:.2f} "
         f"WHERE food_item_id={item_with_children};")
check_ok("F5-05", "unrelated column update on an item with children",
         f"UPDATE donation_item SET item_name=item_name WHERE food_item_id={item_with_children};")
check_error("F5-11", "re-parent an item that has allocations",
            f"UPDATE donation_item SET donation_id={other_donation} WHERE food_item_id={item_with_children};", 1644)
check_ok("F5-12a", "create an item with no children",
         f"INSERT INTO donation_item (donation_id,category_id,item_name,quantity_kg,best_before) "
         f"VALUES ({item_donation},(SELECT MIN(category_id) FROM food_category),'TEST-NOCHILD',50.00,'2027-01-01');")
nochild = value("SELECT food_item_id FROM donation_item WHERE item_name='TEST-NOCHILD' ORDER BY food_item_id DESC LIMIT 1;")
check_ok("F5-06", "reduce an item with no children",
         f"UPDATE donation_item SET quantity_kg=10.00 WHERE food_item_id={nochild};")
check_error("F5-07", "reduce to zero",
            f"UPDATE donation_item SET quantity_kg=0 WHERE food_item_id={nochild};", 3819)
check_ok("F5-12b", "re-parent an item with no allocations",
         f"UPDATE donation_item SET donation_id={other_donation} WHERE food_item_id={nochild};")

# ------------------------------------------------------- F8 (temperature CHECK)
check_ok("F8-01", "NULL temperature",
         f"INSERT INTO inspection_log (donation_id,inspector_user_id,inspected_at,packaging_integrity,safety_status) "
         f"VALUES ({item_donation},{inspector_id},'2026-01-01 10:00:00','INTACT','PASSED');")
check_ok("F8-02a", "lower bound -50.00",
         f"INSERT INTO inspection_log (donation_id,inspector_user_id,inspected_at,temperature_c,packaging_integrity,safety_status) "
         f"VALUES ({item_donation},{inspector_id},'2026-01-01 10:00:00',-50.00,'INTACT','NEEDS_REVIEW');")
check_ok("F8-02b", "upper bound 150.00",
         f"INSERT INTO inspection_log (donation_id,inspector_user_id,inspected_at,temperature_c,packaging_integrity,safety_status) "
         f"VALUES ({item_donation},{inspector_id},'2026-01-01 10:00:00',150.00,'INTACT','NEEDS_REVIEW');")
check_error("F8-03a", "just below the lower bound (-50.01)",
            f"INSERT INTO inspection_log (donation_id,inspector_user_id,inspected_at,temperature_c,packaging_integrity,safety_status) "
            f"VALUES ({item_donation},{inspector_id},'2026-01-01 10:00:00',-50.01,'INTACT','NEEDS_REVIEW');", 3819)
check_error("F8-03b", "just above the upper bound (150.01)",
            f"INSERT INTO inspection_log (donation_id,inspector_user_id,inspected_at,temperature_c,packaging_integrity,safety_status) "
            f"VALUES ({item_donation},{inspector_id},'2026-01-01 10:00:00',150.01,'INTACT','NEEDS_REVIEW');", 3819)
check_ok("F8-04", "plausible 3.40 accepted (plausibility is not safety)",
         f"INSERT INTO inspection_log (donation_id,inspector_user_id,inspected_at,temperature_c,packaging_integrity,safety_status) "
         f"VALUES ({item_donation},{inspector_id},'2026-01-01 10:00:00',3.40,'INTACT','PASSED');")

# ------------------------------------------------------------------- output
passed = 0
print()
print(f"{'ID':10} {'expected':16} {'observed':40} result")
for cid, desc, exp, obs in results:
    ok = exp == obs or (exp.startswith("ERROR") and obs == exp)
    passed += ok
    print(f"{cid:10} {exp:16} {obs[:40]:40} {'PASS' if ok else 'FAIL'}  {desc}")

total = len(results)
print(f"\n{passed}/{total} SQL-layer cases matched their expectation.")

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as fh:
    fh.write(f"Phase 2 SQL-layer test matrix on {DB}\n")
    fh.write(f"generated: {pathlib.Path('.').resolve()}\n\n")
    fh.write(f"{'ID':10}\t{'expected':16}\t{'observed':40}\tresult\tdescription\n")
    for cid, desc, exp, obs in results:
        ok = exp == obs or (exp.startswith("ERROR") and obs == exp)
        fh.write(f"{cid:10}\t{exp:16}\t{obs[:60]:60}\t{'PASS' if ok else 'FAIL'}\t{desc}\n")
    fh.write(f"\n{passed}/{total} matched.\n")

sys.exit(0 if passed == total else 1)
