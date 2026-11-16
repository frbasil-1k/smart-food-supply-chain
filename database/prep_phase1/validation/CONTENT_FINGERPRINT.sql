-- ============================================================================
-- CONTENT_FINGERPRINT.sql   —   exact data-preservation proof (review item R10)
-- READ-ONLY. Run TWICE: once immediately before the migration batch, once
-- after it. The two outputs must be identical, line for line.
--
-- Why not counts and sums: a count survives a swapped value, and a sum survives
-- two compensating errors. This hashes the actual content of every row of every
-- original table, deterministically, so any change of any value is visible.
--
-- METHOD
--   per row:  SHA2(CONCAT_WS(0x1f, IFNULL(HEX(col),'<NULL>'), ...), 256)
--   per table: SHA2 over the row hashes sorted ascending
--   HEX() makes every column type comparable and is ASCII-safe; IFNULL marks a
--   NULL distinctly, and '<NULL>' cannot be produced by HEX() (which emits only
--   0-9A-F), so a real value can never masquerade as a NULL marker.
--   Sorting the row hashes makes the table digest independent of row order and
--   of the storage engine's internal ordering.
--
-- IMPORTANT: the column list for `donation` and `delivery` is the ORIGINAL
-- pre-migration set. pickup_address/pickup_pincode/pickup_contact and
-- driver_user_id/scheduled_for are added by 003 and 004a, so hashing them would
-- change this fingerprint legitimately. Excluding them is what lets the same
-- file prove "the original 104 records are untouched" on both sides.
--
-- Verified baseline expectation: 104 rows total, and the fingerprints captured
-- pre-migration must match post-migration exactly.
-- ============================================================================

SET SESSION group_concat_max_len = 268435456;

SELECT table_name, n,
       fingerprint,
       concatenated_chars,
       64 * n                    AS expected_chars,
       (concatenated_chars = 64 * n) AS not_truncated
FROM (
    -- ------------------------------------------------------------------ 1/15
    SELECT 'organization' AS table_name, COUNT(*) AS n,
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256) AS fingerprint,
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR '')) AS concatenated_chars
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`organization_id`),   '<NULL>'),
                  IFNULL(HEX(`organization_name`), '<NULL>'),
                  IFNULL(HEX(`hq_address`),        '<NULL>'),
                  IFNULL(HEX(`hq_pincode`),        '<NULL>'),
                  IFNULL(HEX(`hq_contact_no`),     '<NULL>')), 256) AS h
              FROM `organization`) s
    UNION ALL
    -- ------------------------------------------------------------------ 2/15
    SELECT 'branch', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`branch_id`),                '<NULL>'),
                  IFNULL(HEX(`organization_id`),          '<NULL>'),
                  IFNULL(HEX(`branch_name`),              '<NULL>'),
                  IFNULL(HEX(`address`),                  '<NULL>'),
                  IFNULL(HEX(`pincode`),                  '<NULL>'),
                  IFNULL(HEX(`contact_no`),               '<NULL>'),
                  IFNULL(HEX(`established_date`),         '<NULL>'),
                  IFNULL(HEX(`regional_manager_user_id`), '<NULL>')), 256) AS h
              FROM `branch`) s
    UNION ALL
    -- ------------------------------------------------------------------ 3/15
    SELECT 'app_user', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`user_id`),           '<NULL>'),
                  IFNULL(HEX(`full_name`),         '<NULL>'),
                  IFNULL(HEX(`email`),             '<NULL>'),
                  IFNULL(HEX(`phone`),             '<NULL>'),
                  IFNULL(HEX(`user_role`),         '<NULL>'),
                  IFNULL(HEX(`account_status`),    '<NULL>'),
                  IFNULL(HEX(`primary_branch_id`), '<NULL>'),
                  IFNULL(HEX(`supervisor_user_id`),'<NULL>')), 256) AS h
              FROM `app_user`) s
    UNION ALL
    -- ------------------------------------------------------------------ 4/15
    SELECT 'route', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`route_id`),                 '<NULL>'),
                  IFNULL(HEX(`managing_branch_id`),       '<NULL>'),
                  IFNULL(HEX(`designated_driver_user_id`),'<NULL>'),
                  IFNULL(HEX(`coverage_area_id`),         '<NULL>'),
                  IFNULL(HEX(`route_type`),               '<NULL>'),
                  IFNULL(HEX(`route_status`),             '<NULL>')), 256) AS h
              FROM `route`) s
    UNION ALL
    -- ------------------------------------------------------------------ 5/15
    SELECT 'coverage_area', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`coverage_area_id`), '<NULL>'),
                  IFNULL(HEX(`area_name`),        '<NULL>'),
                  IFNULL(HEX(`city`),             '<NULL>'),
                  IFNULL(HEX(`pincode`),          '<NULL>')), 256) AS h
              FROM `coverage_area`) s
    UNION ALL
    -- ------------------------------------------------------------------ 6/15
    SELECT 'route_assignment', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`user_id`),       '<NULL>'),
                  IFNULL(HEX(`route_id`),      '<NULL>'),
                  IFNULL(HEX(`hours_per_week`),'<NULL>'),
                  IFNULL(HEX(`assigned_date`), '<NULL>')), 256) AS h
              FROM `route_assignment`) s
    UNION ALL
    -- ------------------------------------------------------------------ 7/15
    -- ORIGINAL columns only: the three pickup_* columns arrive in 003.
    SELECT 'donation', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`donation_id`),      '<NULL>'),
                  IFNULL(HEX(`donor_user_id`),    '<NULL>'),
                  IFNULL(HEX(`pickup_route_id`),  '<NULL>'),
                  IFNULL(HEX(`pickup_datetime`),  '<NULL>'),
                  IFNULL(HEX(`donation_status`),  '<NULL>'),
                  IFNULL(HEX(`urgency_level`),    '<NULL>')), 256) AS h
              FROM `donation`) s
    UNION ALL
    -- ------------------------------------------------------------------ 8/15
    SELECT 'food_category', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`category_id`),   '<NULL>'),
                  IFNULL(HEX(`category_name`), '<NULL>')), 256) AS h
              FROM `food_category`) s
    UNION ALL
    -- ------------------------------------------------------------------ 9/15
    SELECT 'donation_item', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`food_item_id`), '<NULL>'),
                  IFNULL(HEX(`donation_id`),  '<NULL>'),
                  IFNULL(HEX(`category_id`),  '<NULL>'),
                  IFNULL(HEX(`item_name`),    '<NULL>'),
                  IFNULL(HEX(`quantity_kg`),  '<NULL>'),
                  IFNULL(HEX(`prepared_at`),  '<NULL>'),
                  IFNULL(HEX(`best_before`),  '<NULL>')), 256) AS h
              FROM `donation_item`) s
    UNION ALL
    -- ----------------------------------------------------------------- 10/15
    SELECT 'inspection_log', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`inspection_id`),      '<NULL>'),
                  IFNULL(HEX(`donation_id`),        '<NULL>'),
                  IFNULL(HEX(`inspector_user_id`),  '<NULL>'),
                  IFNULL(HEX(`inspected_at`),       '<NULL>'),
                  IFNULL(HEX(`temperature_c`),      '<NULL>'),
                  IFNULL(HEX(`packaging_integrity`),'<NULL>'),
                  IFNULL(HEX(`safety_status`),      '<NULL>'),
                  IFNULL(HEX(`remarks`),            '<NULL>')), 256) AS h
              FROM `inspection_log`) s
    UNION ALL
    -- ----------------------------------------------------------------- 11/15
    SELECT 'dependent', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`driver_user_id`), '<NULL>'),
                  IFNULL(HEX(`dependent_no`),   '<NULL>'),
                  IFNULL(HEX(`full_name`),      '<NULL>'),
                  IFNULL(HEX(`relationship`),   '<NULL>'),
                  IFNULL(HEX(`date_of_birth`),  '<NULL>'),
                  IFNULL(HEX(`phone`),          '<NULL>')), 256) AS h
              FROM `dependent`) s
    UNION ALL
    -- ----------------------------------------------------------------- 12/15
    -- ORIGINAL columns only: driver_user_id and scheduled_for arrive in 004a.
    SELECT 'delivery', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`delivery_id`),         '<NULL>'),
                  IFNULL(HEX(`donation_id`),         '<NULL>'),
                  IFNULL(HEX(`route_id`),            '<NULL>'),
                  IFNULL(HEX(`recipient_branch_id`), '<NULL>'),
                  IFNULL(HEX(`delivered_at`),        '<NULL>'),
                  IFNULL(HEX(`delivery_status`),     '<NULL>')), 256) AS h
              FROM `delivery`) s
    UNION ALL
    -- ----------------------------------------------------------------- 13/15
    SELECT 'delivery_item', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`delivery_item_id`),     '<NULL>'),
                  IFNULL(HEX(`delivery_id`),          '<NULL>'),
                  IFNULL(HEX(`food_item_id`),         '<NULL>'),
                  IFNULL(HEX(`quantity_delivered_kg`),'<NULL>')), 256) AS h
              FROM `delivery_item`) s
    UNION ALL
    -- ----------------------------------------------------------------- 14/15
    SELECT 'spoilage_record', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`spoilage_id`),         '<NULL>'),
                  IFNULL(HEX(`food_item_id`),        '<NULL>'),
                  IFNULL(HEX(`reported_by_user_id`), '<NULL>'),
                  IFNULL(HEX(`quantity_spoiled_kg`), '<NULL>'),
                  IFNULL(HEX(`reported_at`),         '<NULL>'),
                  IFNULL(HEX(`reason`),              '<NULL>')), 256) AS h
              FROM `spoilage_record`) s
    UNION ALL
    -- ----------------------------------------------------------------- 15/15
    SELECT 'delivery_review', COUNT(*),
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256),
           CHAR_LENGTH(GROUP_CONCAT(h ORDER BY h SEPARATOR ''))
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`review_id`),       '<NULL>'),
                  IFNULL(HEX(`delivery_id`),     '<NULL>'),
                  IFNULL(HEX(`reviewer_user_id`),'<NULL>'),
                  IFNULL(HEX(`rating`),          '<NULL>'),
                  IFNULL(HEX(`quality_notes`),   '<NULL>'),
                  IFNULL(HEX(`review_date`),     '<NULL>')), 256) AS h
              FROM `delivery_review`) s
) t
ORDER BY table_name;

-- Each row must show not_truncated = 1. A 0 means group_concat_max_len was too
-- small: raise it and re-run, because a truncated digest is not a fingerprint.

-- ---------------------------------------------------------------------------
-- Single combined digest for a one-line comparison of the whole database
-- ---------------------------------------------------------------------------
SELECT SHA2(GROUP_CONCAT(fingerprint ORDER BY table_name SEPARATOR ''), 256)
         AS all_tables_fingerprint,
       SUM(n) AS total_rows
FROM (
    SELECT 'organization' AS table_name, COUNT(*) AS n,
           SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256) AS fingerprint
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`organization_id`),'<NULL>'), IFNULL(HEX(`organization_name`),'<NULL>'),
                  IFNULL(HEX(`hq_address`),'<NULL>'), IFNULL(HEX(`hq_pincode`),'<NULL>'),
                  IFNULL(HEX(`hq_contact_no`),'<NULL>')), 256) AS h FROM `organization`) s
    UNION ALL SELECT 'branch', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`branch_id`),'<NULL>'), IFNULL(HEX(`organization_id`),'<NULL>'),
                  IFNULL(HEX(`branch_name`),'<NULL>'), IFNULL(HEX(`address`),'<NULL>'),
                  IFNULL(HEX(`pincode`),'<NULL>'), IFNULL(HEX(`contact_no`),'<NULL>'),
                  IFNULL(HEX(`established_date`),'<NULL>'),
                  IFNULL(HEX(`regional_manager_user_id`),'<NULL>')), 256) AS h FROM `branch`) s
    UNION ALL SELECT 'app_user', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`user_id`),'<NULL>'), IFNULL(HEX(`full_name`),'<NULL>'),
                  IFNULL(HEX(`email`),'<NULL>'), IFNULL(HEX(`phone`),'<NULL>'),
                  IFNULL(HEX(`user_role`),'<NULL>'), IFNULL(HEX(`account_status`),'<NULL>'),
                  IFNULL(HEX(`primary_branch_id`),'<NULL>'),
                  IFNULL(HEX(`supervisor_user_id`),'<NULL>')), 256) AS h FROM `app_user`) s
    UNION ALL SELECT 'route', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`route_id`),'<NULL>'), IFNULL(HEX(`managing_branch_id`),'<NULL>'),
                  IFNULL(HEX(`designated_driver_user_id`),'<NULL>'),
                  IFNULL(HEX(`coverage_area_id`),'<NULL>'), IFNULL(HEX(`route_type`),'<NULL>'),
                  IFNULL(HEX(`route_status`),'<NULL>')), 256) AS h FROM `route`) s
    UNION ALL SELECT 'coverage_area', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`coverage_area_id`),'<NULL>'), IFNULL(HEX(`area_name`),'<NULL>'),
                  IFNULL(HEX(`city`),'<NULL>'), IFNULL(HEX(`pincode`),'<NULL>')), 256) AS h
              FROM `coverage_area`) s
    UNION ALL SELECT 'route_assignment', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`user_id`),'<NULL>'), IFNULL(HEX(`route_id`),'<NULL>'),
                  IFNULL(HEX(`hours_per_week`),'<NULL>'), IFNULL(HEX(`assigned_date`),'<NULL>')), 256) AS h
              FROM `route_assignment`) s
    UNION ALL SELECT 'donation', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`donation_id`),'<NULL>'), IFNULL(HEX(`donor_user_id`),'<NULL>'),
                  IFNULL(HEX(`pickup_route_id`),'<NULL>'), IFNULL(HEX(`pickup_datetime`),'<NULL>'),
                  IFNULL(HEX(`donation_status`),'<NULL>'), IFNULL(HEX(`urgency_level`),'<NULL>')), 256) AS h
              FROM `donation`) s
    UNION ALL SELECT 'food_category', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`category_id`),'<NULL>'), IFNULL(HEX(`category_name`),'<NULL>')), 256) AS h
              FROM `food_category`) s
    UNION ALL SELECT 'donation_item', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`food_item_id`),'<NULL>'), IFNULL(HEX(`donation_id`),'<NULL>'),
                  IFNULL(HEX(`category_id`),'<NULL>'), IFNULL(HEX(`item_name`),'<NULL>'),
                  IFNULL(HEX(`quantity_kg`),'<NULL>'), IFNULL(HEX(`prepared_at`),'<NULL>'),
                  IFNULL(HEX(`best_before`),'<NULL>')), 256) AS h FROM `donation_item`) s
    UNION ALL SELECT 'inspection_log', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`inspection_id`),'<NULL>'), IFNULL(HEX(`donation_id`),'<NULL>'),
                  IFNULL(HEX(`inspector_user_id`),'<NULL>'), IFNULL(HEX(`inspected_at`),'<NULL>'),
                  IFNULL(HEX(`temperature_c`),'<NULL>'), IFNULL(HEX(`packaging_integrity`),'<NULL>'),
                  IFNULL(HEX(`safety_status`),'<NULL>'), IFNULL(HEX(`remarks`),'<NULL>')), 256) AS h
              FROM `inspection_log`) s
    UNION ALL SELECT 'dependent', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`driver_user_id`),'<NULL>'), IFNULL(HEX(`dependent_no`),'<NULL>'),
                  IFNULL(HEX(`full_name`),'<NULL>'), IFNULL(HEX(`relationship`),'<NULL>'),
                  IFNULL(HEX(`date_of_birth`),'<NULL>'), IFNULL(HEX(`phone`),'<NULL>')), 256) AS h
              FROM `dependent`) s
    UNION ALL SELECT 'delivery', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`delivery_id`),'<NULL>'), IFNULL(HEX(`donation_id`),'<NULL>'),
                  IFNULL(HEX(`route_id`),'<NULL>'), IFNULL(HEX(`recipient_branch_id`),'<NULL>'),
                  IFNULL(HEX(`delivered_at`),'<NULL>'), IFNULL(HEX(`delivery_status`),'<NULL>')), 256) AS h
              FROM `delivery`) s
    UNION ALL SELECT 'delivery_item', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`delivery_item_id`),'<NULL>'), IFNULL(HEX(`delivery_id`),'<NULL>'),
                  IFNULL(HEX(`food_item_id`),'<NULL>'), IFNULL(HEX(`quantity_delivered_kg`),'<NULL>')), 256) AS h
              FROM `delivery_item`) s
    UNION ALL SELECT 'spoilage_record', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`spoilage_id`),'<NULL>'), IFNULL(HEX(`food_item_id`),'<NULL>'),
                  IFNULL(HEX(`reported_by_user_id`),'<NULL>'), IFNULL(HEX(`quantity_spoiled_kg`),'<NULL>'),
                  IFNULL(HEX(`reported_at`),'<NULL>'), IFNULL(HEX(`reason`),'<NULL>')), 256) AS h
              FROM `spoilage_record`) s
    UNION ALL SELECT 'delivery_review', COUNT(*), SHA2(GROUP_CONCAT(h ORDER BY h SEPARATOR ''), 256)
      FROM (SELECT SHA2(CONCAT_WS(0x1f,
                  IFNULL(HEX(`review_id`),'<NULL>'), IFNULL(HEX(`delivery_id`),'<NULL>'),
                  IFNULL(HEX(`reviewer_user_id`),'<NULL>'), IFNULL(HEX(`rating`),'<NULL>'),
                  IFNULL(HEX(`quality_notes`),'<NULL>'), IFNULL(HEX(`review_date`),'<NULL>')), 256) AS h
              FROM `delivery_review`) s
) u;
-- Expect a single fingerprint and total_rows = 104. Must be byte-identical
-- before and after the batch.

-- ============================================================================
-- POST-BATCH ASSERTIONS (R10) — run only after the whole batch
-- Each must return exactly the stated value. These assert the INTENDED change
-- set: nothing else in the database moved.
-- ============================================================================

-- A. Five reconstructed snapshots, exactly one per existing donation.
SELECT (SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed = 1) AS snapshots,
       (SELECT COUNT(DISTINCT donation_id) FROM donation_status_history
         WHERE is_reconstructed = 1)                                             AS donations_covered,
       (SELECT COUNT(*) FROM donation)                                           AS donations;
-- expect 5 / 5 / 5

-- B. The five existing pickup-address records remain NULL.
SELECT COUNT(*) AS null_pickup_address FROM donation WHERE pickup_address IS NULL;
SELECT COUNT(*) AS null_pickup_pincode FROM donation WHERE pickup_pincode IS NULL;
SELECT COUNT(*) AS null_pickup_contact FROM donation WHERE pickup_contact IS NULL;
-- expect 5 / 5 / 5

-- C. The five existing deliveries remain unattributed and unscheduled.
SELECT COUNT(*) AS null_driver FROM delivery WHERE driver_user_id IS NULL;
SELECT COUNT(*) AS null_schedule FROM delivery WHERE scheduled_for IS NULL;
-- expect 5 / 5

-- D. Original records untouched: rerun the fingerprint query above and require
--    byte-identical output to the pre-batch capture. Counts alone are not proof.
