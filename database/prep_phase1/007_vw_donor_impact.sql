-- ============================================================================
-- 007_vw_donor_impact.sql   —   corrected donor impact reporting
-- DRAFT — UNEXECUTED **AND REVIEW-GATED**.
--
-- Do not apply until the numbers it returns have been read on a restored copy
-- of the database (restore procedure: README.md §5, RUNNER_DESIGN.md §7).
--
-- `vw_donor_sustainability` is PRESERVED UNCHANGED. This file only adds a view.
--
-- PRECONDITION (require 0 rows):
--   SELECT table_name FROM information_schema.views
--    WHERE table_schema = DATABASE() AND table_name = 'vw_donor_impact';
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Security model (review item R12): SQL SECURITY INVOKER
-- ---------------------------------------------------------------------------
-- The two existing views are DEFINER=`root`@`localhost`, which means every query
-- runs with root's privileges and the application account needs only SELECT on
-- the view. That works, but it is an accidental privilege escalation: whoever
-- can select the view reads every base table through root, and the behaviour
-- silently depends on a root account existing with those grants.
--
-- This view is INVOKER instead: it runs with the caller's privileges, so the
-- report can only ever show data the caller could already read directly. No
-- definer account, no hidden escalation, and no dependency on root surviving a
-- deployment or a password change. The cost is that the app account needs SELECT
-- on the six base tables — which it needs anyway to write them.
--
-- Required grants (documented in RUNNER_DESIGN.md §5b): the app account holds a
-- database-wide `GRANT SELECT ... ON smart_food_supply_chain.*`, which already
-- covers this view and the six base tables it reads. Because the view is
-- INVOKER, no separate view grant and no definer account are needed - the caller
-- simply has to be able to read the base tables directly, and it can.
-- The existing DEFINER=root views are left as they are in this phase; replacing
-- them is a separate, reviewed change (open question 10).
-- ---------------------------------------------------------------------------

CREATE ALGORITHM=UNDEFINED SQL SECURITY INVOKER VIEW `vw_donor_impact` AS
SELECT u.`user_id`                                    AS `donor_id`,
       u.`full_name`                                  AS `donor_name`,
       COALESCE(h.`total_donations`, 0)               AS `total_donations`,
       COALESCE(h.`total_donated_kg`, 0)              AS `total_donated_kg`,
       COALESCE(dv.`delivered_kg`, 0)                 AS `delivered_kg`,
       COALESCE(sp.`spoiled_kg`, 0)                   AS `spoiled_kg`,
       COALESCE(h.`total_donated_kg`, 0)
         - COALESCE(dv.`delivered_kg`, 0)
         - COALESCE(sp.`spoiled_kg`, 0)               AS `undistributed_balance_kg`
  FROM `app_user` u
  LEFT JOIN (SELECT d.`donor_user_id`,
                    COUNT(DISTINCT d.`donation_id`)   AS `total_donations`,
                    SUM(i.`quantity_kg`)              AS `total_donated_kg`
               FROM `donation` d
               LEFT JOIN `donation_item` i ON i.`donation_id` = d.`donation_id`
              WHERE d.`donation_status` <> 'CANCELLED'
              GROUP BY d.`donor_user_id`) h      ON h.`donor_user_id`  = u.`user_id`
  LEFT JOIN (SELECT d.`donor_user_id`,
                    SUM(di.`quantity_delivered_kg`)   AS `delivered_kg`
               FROM `donation` d
               JOIN `delivery` d2      ON d2.`donation_id` = d.`donation_id`
               JOIN `delivery_item` di ON di.`delivery_id` = d2.`delivery_id`
              WHERE d2.`delivery_status` = 'DELIVERED'
                AND d.`donation_status`  <> 'CANCELLED'
              GROUP BY d.`donor_user_id`) dv     ON dv.`donor_user_id` = u.`user_id`
  LEFT JOIN (SELECT d.`donor_user_id`,
                    SUM(s.`quantity_spoiled_kg`)      AS `spoiled_kg`
               FROM `donation` d
               JOIN `donation_item`  i2 ON i2.`donation_id`  = d.`donation_id`
               JOIN `spoilage_record` s ON s.`food_item_id`   = i2.`food_item_id`
              WHERE d.`donation_status` <> 'CANCELLED'
              GROUP BY d.`donor_user_id`) sp     ON sp.`donor_user_id` = u.`user_id`
 WHERE u.`user_role` = 'DONOR';

-- ---------------------------------------------------------------------------
-- Why each piece exists
-- ---------------------------------------------------------------------------
-- CANCELLED excluded from all THREE aggregates, so the balance is never
--   computed from inconsistent denominators. (Nothing is cancelled today:
--   4 COMPLETED + 1 APPROVED. This is a guarantee, not a visible change.)
-- delivered_kg counts only delivery_status = 'DELIVERED'. The existing view
--   sums every delivery_item regardless of status, so PLANNED, IN_TRANSIT,
--   FAILED and CANCELLED allocations all read as "distributed" there.
-- spoiled_kg is its own column: spoilage is a loss, never impact, and is
--   subtracted only to produce the balance.
-- undistributed_balance_kg is an ACCOUNTING BALANCE, not physical stock. The
--   food may be in transit, awaiting inspection, or gone without either a
--   delivery or a spoilage entry. UI label must be "undistributed balance";
--   "on hand", "remaining stock" and "available" are prohibited.
-- Pre-aggregated subqueries keep the three metrics independent: with plain
--   joins, one donation with 3 items and 2 deliveries would double-count items.
--
-- ---------------------------------------------------------------------------
-- Review gate (before applying)
-- ---------------------------------------------------------------------------
-- 1. Restore the pre-migration dump into sfc_restore_verify (README §5) and run
--    the SELECT form of this view there.
-- 2. Per donor: delivered_kg <= total_donated_kg, and balance >= 0.
-- 3. Explain every difference against vw_donor_sustainability (each should be
--    an un-DELIVERED allocation).
-- 4. Only then apply.
--
-- ---------------------------------------------------------------------------
-- Validation after applying
-- ---------------------------------------------------------------------------
-- V007-A  view exists, SECURITY_TYPE = 'INVOKER'                          -- 1
-- V007-B  vw_donor_sustainability still present and unchanged              -- 1
-- V007-C  vw_driver_performance still present and unchanged                -- 1
-- V007-D  negative balances                                               -- 0
-- V007-E  delivered_kg > total_donated_kg                                 -- 0
-- V007-F  one row per DONOR account                                       -- 4
-- V007-G  no DEFINER account recorded for this view ('root' must not appear)
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- DROP VIEW `vw_donor_impact`;
-- Fully reversible; no data is touched.
