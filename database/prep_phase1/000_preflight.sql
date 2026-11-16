-- ============================================================================
-- 000_preflight.sql  —  READ-ONLY PRE-FLIGHT
-- Phase 1 revision draft. Safe to run repeatedly: every statement is a SELECT
-- against information_schema or a COUNT(*) over the existing tables.
-- No DDL, no DML, no locks beyond normal reads.
--
-- Run IMMEDIATELY BEFORE the migration batch and save the output next to the
-- backup. Compare with the same output captured afterwards: only the intended
-- differences may appear. For the exact-content proof (not just counts), run
-- validation/CONTENT_FINGERPRINT.sql before the batch and after it.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- P1. Server and session environment
-- ---------------------------------------------------------------------------
SELECT VERSION()                        AS server_version,
       @@sql_mode                       AS sql_mode,
       @@default_storage_engine         AS default_engine,
       @@character_set_server           AS charset,
       @@collation_server               AS collation,
       @@lower_case_table_names         AS lower_case_table_names;

-- Expect: 8.0.46, InnoDB, utf8mb4, utf8mb4_0900_ai_ci.
-- STRICT_TRANS_TABLES must be present: the CHECK/ENUM protections rely on it.

SELECT DATABASE() AS current_database;

-- ---------------------------------------------------------------------------
-- P2. Nothing else is mid-write
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS open_innodb_transactions FROM information_schema.innodb_trx;
-- Expect 0. A concurrent DDL/DML can block ALTER TABLE.

-- ---------------------------------------------------------------------------
-- P3. Migration-state guard: new objects must not exist yet
-- ---------------------------------------------------------------------------
SELECT '002a donation_status_history' AS object_name, COUNT(*) AS existing
  FROM information_schema.tables
 WHERE table_schema = DATABASE() AND table_name = 'donation_status_history'
UNION ALL
SELECT '001 user_credential', COUNT(*)
  FROM information_schema.tables
 WHERE table_schema = DATABASE() AND table_name = 'user_credential'
UNION ALL
SELECT '007 vw_donor_impact', COUNT(*)
  FROM information_schema.views
 WHERE table_schema = DATABASE() AND table_name = 'vw_donor_impact';
-- Every row must be 0. Otherwise the migration was applied (or partly applied)
-- and must be investigated before anything else runs.

-- ---------------------------------------------------------------------------
-- P4. New columns must not exist yet (003, 004a)
-- ---------------------------------------------------------------------------
SELECT table_name, column_name
  FROM information_schema.columns
 WHERE table_schema = DATABASE()
   AND (   (table_name = 'donation' AND column_name IN
            ('pickup_address','pickup_pincode','pickup_contact'))
        OR (table_name = 'delivery'  AND column_name IN
            ('driver_user_id','scheduled_for')))
 ORDER BY table_name, column_name;
-- Expect zero rows.

-- ---------------------------------------------------------------------------
-- P5. Trigger and constraint name collisions
-- ---------------------------------------------------------------------------
SELECT trigger_name, event_object_table, action_timing, event_manipulation
  FROM information_schema.triggers
 WHERE trigger_schema = DATABASE()
   AND trigger_name IN ('trg_dsh_block_update', 'trg_dsh_block_delete',
                        'trg_delivery_driver_insert', 'trg_delivery_driver_update',
                        'trg_donation_item_update_guard');
-- Expect zero rows.

SELECT constraint_name, table_name
  FROM information_schema.table_constraints
 WHERE table_schema = DATABASE()
   AND constraint_name IN ('chk_temperature_range',
                           'chk_cred_token_pairing',
                           'chk_cred_lock_consistency',
                           'chk_dsh_time_semantics');
-- Expect zero rows.

-- ---------------------------------------------------------------------------
-- P6. Existing CHECK constraints (the new ones must complement, not duplicate)
-- ---------------------------------------------------------------------------
SELECT tc.table_name, tc.constraint_name, tc.enforced, cc.check_clause
  FROM information_schema.table_constraints tc
  JOIN information_schema.check_constraints cc
    ON cc.constraint_schema = tc.constraint_schema
   AND cc.constraint_name   = tc.constraint_name
 WHERE tc.table_schema = DATABASE()
   AND tc.constraint_type = 'CHECK'
 ORDER BY tc.table_name, tc.constraint_name;
-- Expect 6 rows, all ENFORCED=YES:
--   chk_delivery_quantity, chk_donation_quantity, chk_food_dates,
--   chk_review_rating, chk_route_hours, chk_spoilage_quantity

-- ---------------------------------------------------------------------------
-- P7. Row-count fingerprint (counts only — the exact proof is
--     validation/CONTENT_FINGERPRINT.sql, which must be captured here too)
-- ---------------------------------------------------------------------------
SELECT 'organization'          AS table_name, COUNT(*) AS rows_now FROM organization
UNION ALL SELECT 'branch',              COUNT(*) FROM branch
UNION ALL SELECT 'app_user',            COUNT(*) FROM app_user
UNION ALL SELECT 'route',               COUNT(*) FROM route
UNION ALL SELECT 'coverage_area',       COUNT(*) FROM coverage_area
UNION ALL SELECT 'route_assignment',    COUNT(*) FROM route_assignment
UNION ALL SELECT 'donation',            COUNT(*) FROM donation
UNION ALL SELECT 'food_category',       COUNT(*) FROM food_category
UNION ALL SELECT 'donation_item',       COUNT(*) FROM donation_item
UNION ALL SELECT 'inspection_log',      COUNT(*) FROM inspection_log
UNION ALL SELECT 'dependent',           COUNT(*) FROM dependent
UNION ALL SELECT 'delivery',            COUNT(*) FROM delivery
UNION ALL SELECT 'delivery_item',       COUNT(*) FROM delivery_item
UNION ALL SELECT 'spoilage_record',     COUNT(*) FROM spoilage_record
UNION ALL SELECT 'delivery_review',     COUNT(*) FROM delivery_review;

-- Verified baseline: organization 3 | branch 5 | app_user 15 | route 5 |
-- coverage_area 5 | route_assignment 8 | donation 5 | food_category 8 |
-- donation_item 13 | inspection_log 5 | dependent 6 | delivery 5 |
-- delivery_item 15 | spoilage_record 1 | delivery_review 5  → TOTAL 104

-- ---------------------------------------------------------------------------
-- P8. F8 pre-check — the CHECK validates EXISTING rows when it is added
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS readings_outside_plausibility_band
  FROM inspection_log
 WHERE temperature_c IS NOT NULL
   AND (temperature_c < -50 OR temperature_c > 150);
-- MUST be 0 before 006. Non-zero means 006 aborts (3819): review those readings,
-- do not widen the band to make the migration pass.

-- ---------------------------------------------------------------------------
-- P9. F2 pre-check — what the reconstructed snapshots will capture
-- ---------------------------------------------------------------------------
SELECT donation_status, COUNT(*) AS donations
  FROM donation GROUP BY donation_status ORDER BY donation_status;
-- Expected: COMPLETED 4, APPROVED 1 (5 snapshots in 002b).

-- ---------------------------------------------------------------------------
-- P10. F2/F4 pre-checks — the exact legacy NULL populations
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS donations_that_will_have_null_pickup FROM donation;
-- Expect 5: every existing donation keeps pickup_address/pincode/contact NULL.

SELECT COUNT(*)                           AS deliveries_that_will_have_no_driver,
       SUM(delivery_status = 'DELIVERED') AS of_which_delivered
  FROM delivery;
-- Expect 5 / 5.

-- ---------------------------------------------------------------------------
-- P11. F5 pre-check — no item may already violate the quantity invariant
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS over_allocated_items FROM donation_item di
 WHERE di.quantity_kg <
       COALESCE((SELECT SUM(quantity_delivered_kg) FROM delivery_item
                  WHERE food_item_id = di.food_item_id), 0) +
       COALESCE((SELECT SUM(quantity_spoiled_kg) FROM spoilage_record
                  WHERE food_item_id = di.food_item_id), 0);
-- Expect 0.

-- ---------------------------------------------------------------------------
-- P12. F5 pre-check — no item may already be cross-donation allocated
--      (the condition 005 will forbid from now on)
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS cross_donation_items FROM delivery_item di
  JOIN delivery d        ON d.delivery_id = di.delivery_id
  JOIN donation_item i   ON i.food_item_id = di.food_item_id
 WHERE d.donation_id <> i.donation_id;
-- Expect 0. A non-zero value is an existing integrity defect to review BEFORE
-- adding the guard, not something the guard can repair.
