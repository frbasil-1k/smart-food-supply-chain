-- ============================================================================
-- VALIDATION_ALL.sql   —   per-migration verification
-- READ-ONLY except the negative probes, which are DEV-ONLY and commented out.
--
-- WORKFLOW (review item R8): run the block for ONE migration immediately after
-- that migration, and save its output with the ledger entry. The full structural
-- and semantic audit is run ONCE against the final post-migration baseline after
-- the whole batch — see MIGRATION_PLAN.md §7 and RUNNER_DESIGN.md §6. Per-stage
-- baselines are not provided because each one would freeze a schema that never
-- exists outside a maintenance window.
-- ============================================================================


-- ===========================================================================
-- V000 — batch-level invariants (run after every migration)
-- ===========================================================================
SELECT 'organization' AS t, COUNT(*) AS n FROM organization
UNION ALL SELECT 'branch',           COUNT(*) FROM branch
UNION ALL SELECT 'app_user',         COUNT(*) FROM app_user
UNION ALL SELECT 'route',            COUNT(*) FROM route
UNION ALL SELECT 'coverage_area',    COUNT(*) FROM coverage_area
UNION ALL SELECT 'route_assignment', COUNT(*) FROM route_assignment
UNION ALL SELECT 'donation',         COUNT(*) FROM donation
UNION ALL SELECT 'food_category',    COUNT(*) FROM food_category
UNION ALL SELECT 'donation_item',    COUNT(*) FROM donation_item
UNION ALL SELECT 'inspection_log',   COUNT(*) FROM inspection_log
UNION ALL SELECT 'dependent',        COUNT(*) FROM dependent
UNION ALL SELECT 'delivery',         COUNT(*) FROM delivery
UNION ALL SELECT 'delivery_item',    COUNT(*) FROM delivery_item
UNION ALL SELECT 'spoilage_record',  COUNT(*) FROM spoilage_record
UNION ALL SELECT 'delivery_review',  COUNT(*) FROM delivery_review;
-- Expect the baseline distributions; total 104. Exact content proof lives in
-- validation/CONTENT_FINGERPRINT.sql — counts alone are not proof (R10).


-- ===========================================================================
-- V001 — USER_CREDENTIAL
-- ===========================================================================
SELECT COUNT(*) AS columns_present FROM information_schema.columns
 WHERE table_schema = DATABASE() AND table_name = 'user_credential';
-- expect 11

SELECT constraint_name, constraint_type FROM information_schema.table_constraints
 WHERE table_schema = DATABASE() AND table_name = 'user_credential'
 ORDER BY constraint_type, constraint_name;
-- expect PRIMARY KEY, UNIQUE uq_cred_reset_token, FOREIGN KEY fk_credential_user,
--        CHECK chk_cred_lock_consistency, CHECK chk_cred_token_pairing

SELECT COUNT(*) AS credential_rows FROM user_credential;            -- 0
SELECT COUNT(*) AS users_without_credential
  FROM app_user u LEFT JOIN user_credential c USING (user_id)
 WHERE c.user_id IS NULL;                                           -- 15
SELECT COUNT(*) AS non_scrypt_hashes FROM user_credential
 WHERE password_hash NOT LIKE 'scrypt:%';                           -- 0
SELECT COUNT(*) AS incoherent_locks FROM user_credential
 WHERE locked_until IS NOT NULL AND failed_attempts = 0;            -- 0
SELECT COUNT(*) AS unpaired_tokens FROM user_credential
 WHERE (reset_token_hash IS NULL) <> (reset_expires_at IS NULL);    -- 0

-- V001-E (DEV ONLY) token pairing; both expect 3819.
-- INSERT INTO user_credential (user_id, password_hash, reset_token_hash)
-- VALUES (1, REPEAT('x',60), REPEAT('a',64));
-- INSERT INTO user_credential (user_id, password_hash, reset_expires_at)
-- VALUES (2, REPEAT('x',60), NOW() + INTERVAL 1 DAY);
-- V001-F (DEV ONLY) FK; expects 1452.
-- INSERT INTO user_credential (user_id, password_hash)
-- VALUES (999999, REPEAT('x',60));


-- ===========================================================================
-- V002a — DONATION_STATUS_HISTORY (structure + append-only)
-- ===========================================================================
SELECT COUNT(*) AS columns_present FROM information_schema.columns
 WHERE table_schema = DATABASE() AND table_name = 'donation_status_history';
-- expect 9 (8 declared + the generated reconstructed_donation_id)

SELECT column_name, extra, generation_expression
  FROM information_schema.columns
 WHERE table_schema = DATABASE() AND table_name = 'donation_status_history'
   AND column_name = 'reconstructed_donation_id';
-- expect extra='STORED GENERATED', expression IF(`is_reconstructed` = 1,...)

SELECT index_name, non_unique,
       GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols
  FROM information_schema.statistics
 WHERE table_schema = DATABASE() AND table_name = 'donation_status_history'
 GROUP BY index_name, non_unique;
-- expect uq_dsh_one_reconstructed unique on (reconstructed_donation_id)

SELECT constraint_name, enforced FROM information_schema.table_constraints
 WHERE table_schema = DATABASE() AND table_name = 'donation_status_history'
   AND constraint_type = 'CHECK';
-- expect 3, all ENFORCED

SELECT trigger_name, action_timing, event_manipulation
  FROM information_schema.triggers
 WHERE trigger_schema = DATABASE() AND trigger_name LIKE 'trg_dsh_%'
 ORDER BY trigger_name;
-- expect trg_dsh_block_delete (BEFORE DELETE), trg_dsh_block_update (BEFORE UPDATE)

SELECT COUNT(*) AS rows_now FROM donation_status_history;           -- 0

-- V002a-E (DEV ONLY) append-only proof. Seed one genuine row, then:
--   UPDATE donation_status_history SET note = 'x';                  -- 1644
--   DELETE FROM donation_status_history;                            -- 1644
--   UPDATE donation_status_history SET to_status = 'COMPLETED';     -- 1644


-- ===========================================================================
-- V002b — legacy backfill
-- ===========================================================================
SELECT COUNT(*) AS snapshots FROM donation_status_history WHERE is_reconstructed = 1;
-- 5

SELECT COUNT(*) AS donations_without_history
  FROM donation d
 WHERE NOT EXISTS (SELECT 1 FROM donation_status_history h
                    WHERE h.donation_id = d.donation_id);           -- 0

SELECT COUNT(*) AS duplicate_reconstructed_snapshots
  FROM (SELECT donation_id FROM donation_status_history
         WHERE is_reconstructed = 1
         GROUP BY donation_id HAVING COUNT(*) > 1) x;               -- 0

SELECT COUNT(*) AS fabricated_legacy_timestamps
  FROM donation_status_history
 WHERE is_reconstructed = 1 AND changed_at IS NOT NULL;             -- 0
SELECT COUNT(*) AS legacy_snapshots_with_actor
  FROM donation_status_history
 WHERE is_reconstructed = 1 AND changed_by_user_id IS NOT NULL;      -- 0
SELECT COUNT(*) AS genuine_rows_without_timestamp
  FROM donation_status_history
 WHERE is_reconstructed = 0 AND changed_at IS NULL;                 -- 0

SELECT to_status, COUNT(*) AS snapshots
  FROM donation_status_history WHERE is_reconstructed = 1
 GROUP BY to_status;                    -- COMPLETED 4, APPROVED 1

SELECT COUNT(*) AS empty_note FROM donation_status_history
 WHERE is_reconstructed = 1
   AND (note IS NULL OR note NOT LIKE 'State observed when history tracking began%');
-- 0

-- V002b-F (DEV ONLY) idempotence: re-run 002b, then
-- expect "0 rows affected" and the totals above unchanged.


-- ===========================================================================
-- V003 — DONATION pickup columns
-- ===========================================================================
SELECT column_name, column_type, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = DATABASE() AND table_name = 'donation'
   AND column_name IN ('pickup_address','pickup_pincode','pickup_contact')
 ORDER BY ordinal_position;
-- varchar(255)/varchar(10)/varchar(15), all YES, all NULL

SELECT COUNT(*) AS null_address FROM donation WHERE pickup_address IS NULL;  -- 5
SELECT COUNT(*) AS null_pincode FROM donation WHERE pickup_pincode IS NULL;  -- 5
SELECT COUNT(*) AS null_contact FROM donation WHERE pickup_contact IS NULL;  -- 5

-- Post-go-live format observations (never hard failures; see MIGRATION_PLAN §4)
SELECT COUNT(*) AS pincode_suspects FROM donation
 WHERE pickup_pincode IS NOT NULL AND pickup_pincode NOT REGEXP '^[1-9][0-9]{5}$';
SELECT COUNT(*) AS contact_suspects FROM donation
 WHERE pickup_contact IS NOT NULL AND pickup_contact NOT REGEXP '^\\+91[6-9][0-9]{9}$';


-- ===========================================================================
-- V004a — delivery attribution structure
-- ===========================================================================
SELECT column_name, column_type, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = DATABASE() AND table_name = 'delivery'
   AND column_name IN ('driver_user_id','scheduled_for')
 ORDER BY ordinal_position;
-- int / datetime, both nullable, no default

SELECT COUNT(*) AS null_driver FROM delivery WHERE driver_user_id IS NULL;   -- 5
SELECT COUNT(*) AS null_schedule FROM delivery WHERE scheduled_for IS NULL;  -- 5

SELECT constraint_name, referenced_table_name, referenced_column_name
  FROM information_schema.key_column_usage
 WHERE table_schema = DATABASE() AND table_name = 'delivery'
   AND constraint_name = 'fk_delivery_driver';

SELECT index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols
  FROM information_schema.statistics
 WHERE table_schema = DATABASE() AND table_name = 'delivery'
   AND index_name IN ('idx_delivery_driver_status','idx_delivery_scheduled')
 GROUP BY index_name;

-- R9: only a unique index EXACTLY on (donation_id, recipient_branch_id) is
-- prohibited. Any other legitimate unique index must not fail this test, so the
-- check is on the exact column set, not on "any non-primary unique index".
SELECT index_name,
       GROUP_CONCAT(column_name ORDER BY seq_in_index) AS index_columns
  FROM information_schema.statistics
 WHERE table_schema = DATABASE() AND table_name = 'delivery'
   AND non_unique = 0
 GROUP BY index_name
HAVING index_columns IN ('donation_id,recipient_branch_id',
                         'recipient_branch_id,donation_id');
-- expect 0 rows (no such constraint exists, and none was added)

-- For transparency: every unique index that DOES exist on delivery.
SELECT index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS index_columns
  FROM information_schema.statistics
 WHERE table_schema = DATABASE() AND table_name = 'delivery' AND non_unique = 0
 GROUP BY index_name;
-- expect only PRIMARY (delivery_id)


-- ===========================================================================
-- V004b — delivery driver triggers
-- ===========================================================================
SELECT trigger_name, action_timing, event_manipulation
  FROM information_schema.triggers
 WHERE trigger_schema = DATABASE()
   AND trigger_name IN ('trg_delivery_driver_insert','trg_delivery_driver_update')
 ORDER BY trigger_name;
-- expect BEFORE INSERT and BEFORE UPDATE on delivery

SELECT COUNT(*) AS driver_with_wrong_role
  FROM delivery d JOIN app_user u ON u.user_id = d.driver_user_id
 WHERE u.user_role <> 'DRIVER';                                     -- 0

SELECT COUNT(*) AS transit_without_driver
  FROM delivery WHERE delivery_status = 'IN_TRANSIT' AND driver_user_id IS NULL;
-- 0 (no IN_TRANSIT rows exist in the baseline; must stay 0 after go-live)

-- R3 scenario (DEV ONLY), the exact behaviour this revision fixed:
--   1. assign a DRIVER to a PLANNED delivery                        -- succeeds
--   2. UPDATE app_user SET user_role='DONOR' WHERE user_id=<that>;   -- succeeds
--   3. UPDATE delivery SET scheduled_for = NOW() WHERE ...;          -- SUCCEEDS
--      (no revalidation of an unchanged attribution)
--   4. UPDATE delivery SET driver_user_id = <someone else>           -- 1644
-- R3 immutability (DEV ONLY):
--   UPDATE delivery SET driver_user_id = <id> WHERE delivery_status='DELIVERED';
--                                                                    -- 1644
-- R3 transit gate (DEV ONLY):
--   UPDATE delivery SET delivery_status='IN_TRANSIT', driver_user_id=NULL;
--                                                                    -- 1644


-- ===========================================================================
-- V005 — DONATION_ITEM update guard (quantity + re-parenting)
-- ===========================================================================
SELECT trigger_name, action_timing, event_manipulation
  FROM information_schema.triggers
 WHERE trigger_schema = DATABASE()
   AND trigger_name = 'trg_donation_item_update_guard';             -- BEFORE UPDATE

SELECT COUNT(*) AS over_allocated_items FROM donation_item di
 WHERE di.quantity_kg <
       COALESCE((SELECT SUM(quantity_delivered_kg) FROM delivery_item
                  WHERE food_item_id = di.food_item_id), 0) +
       COALESCE((SELECT SUM(quantity_spoiled_kg) FROM spoilage_record
                  WHERE food_item_id = di.food_item_id), 0);         -- 0

SELECT COUNT(*) AS cross_donation_items FROM delivery_item di
  JOIN delivery d      ON d.delivery_id = di.delivery_id
  JOIN donation_item i ON i.food_item_id = di.food_item_id
 WHERE d.donation_id <> i.donation_id;                              -- 0

-- V005-G (DEV ONLY) re-parent an allocated item; expect 1644.
-- UPDATE donation_item SET donation_id = <other donation>
--  WHERE food_item_id = <item with delivery_item rows>;
-- V005-H (DEV ONLY) re-parent an unallocated item; expect success.


-- ===========================================================================
-- V006 — temperature plausibility CHECK
-- ===========================================================================
SELECT tc.constraint_name, tc.enforced, cc.check_clause
  FROM information_schema.table_constraints tc
  JOIN information_schema.check_constraints cc
    ON cc.constraint_schema = tc.constraint_schema
   AND cc.constraint_name   = tc.constraint_name
 WHERE tc.table_schema = DATABASE() AND tc.constraint_name = 'chk_temperature_range';
-- ENFORCED=YES, -50/150 clause

SELECT COUNT(*) AS out_of_band FROM inspection_log
 WHERE temperature_c IS NOT NULL AND (temperature_c < -50 OR temperature_c > 150);
-- 0
SELECT COUNT(*) AS null_readings FROM inspection_log WHERE temperature_c IS NULL;
-- unchanged from preflight; NULL must stay legal


-- ===========================================================================
-- V007 — vw_donor_impact
-- ===========================================================================
SELECT table_name, security_type, definer
  FROM information_schema.views
 WHERE table_schema = DATABASE() AND table_name = 'vw_donor_impact';
-- expect security_type = 'INVOKER'; definer must NOT be root (R12)

SELECT COUNT(*) AS original_views_present FROM information_schema.views
 WHERE table_schema = DATABASE()
   AND table_name IN ('vw_donor_sustainability','vw_driver_performance');  -- 2

SELECT COUNT(*) AS negative_balance FROM vw_donor_impact
 WHERE undistributed_balance_kg < 0;                                -- 0
SELECT COUNT(*) AS delivered_exceeds_donated FROM vw_donor_impact
 WHERE delivered_kg > total_donated_kg;                             -- 0
SELECT COUNT(*) AS donor_rows FROM vw_donor_impact;                 -- 4

SELECT donor_name, total_donated_kg, delivered_kg, spoiled_kg,
       undistributed_balance_kg
  FROM vw_donor_impact ORDER BY delivered_kg DESC;
-- REVIEW GATE: read this before relying on the view.
