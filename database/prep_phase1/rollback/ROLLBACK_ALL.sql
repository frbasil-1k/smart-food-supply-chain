-- ============================================================================
-- ROLLBACK_ALL.sql   —   reverse of the revised batch
-- DRAFT — UNEXECUTED.
--
-- MySQL commits implicitly around DDL: there is no "ROLLBACK the migration".
-- This file is a sequence of compensating statements, run deliberately one step
-- at a time, in this order:
--
--   007 -> 006 -> 005 -> 004b -> 004a -> 003 -> 002b -> 002a -> 001
--
-- Back up BEFORE rolling back too. Data created after go-live is lost by the
-- destructive steps, which are marked DESTRUCTIVE below.
--
-- PARTIAL-FAILURE RECOVERY (review item R11)
-- A migration that failed midway is NOT fixed by running this file from the top:
-- most steps would fail on objects that do not exist. Diagnose first, then use
-- the matching recovery path from RUNNER_DESIGN.md §4. The rule everywhere:
-- inspect information_schema, decide, then either finish or undo that ONE
-- migration. Never blindly re-run DDL.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- STEP 1 (007) — donor-impact view. Reversible, no data.
-- ---------------------------------------------------------------------------
DROP VIEW `vw_donor_impact`;


-- ---------------------------------------------------------------------------
-- STEP 2 (006) — temperature plausibility CHECK. Reversible, no data.
-- ---------------------------------------------------------------------------
ALTER TABLE `inspection_log`
  DROP CHECK `chk_temperature_range`;


-- ---------------------------------------------------------------------------
-- STEP 3 (005) — donation-item update guard. Reversible, no data.
-- ---------------------------------------------------------------------------
DROP TRIGGER `trg_donation_item_update_guard`;


-- ---------------------------------------------------------------------------
-- STEP 4 (004b) — delivery driver triggers. Reversible, no data.
-- Before 004a's columns, so nothing references a disappearing column.
-- ---------------------------------------------------------------------------
DROP TRIGGER `trg_delivery_driver_update`;
DROP TRIGGER `trg_delivery_driver_insert`;


-- ---------------------------------------------------------------------------
-- STEP 5 (004a) — delivery attribution columns. DESTRUCTIVE once recorded.
-- ---------------------------------------------------------------------------
ALTER TABLE `delivery`
  DROP FOREIGN KEY `fk_delivery_driver`,
  DROP KEY `idx_delivery_scheduled`,
  DROP KEY `idx_delivery_driver_status`,
  DROP COLUMN `scheduled_for`,
  DROP COLUMN `driver_user_id`;
-- Want to undo only the triggers and keep the columns? Stop after STEP 4.


-- ---------------------------------------------------------------------------
-- STEP 6 (003) — donation pickup columns. DESTRUCTIVE once entered.
-- ---------------------------------------------------------------------------
ALTER TABLE `donation`
  DROP COLUMN `pickup_contact`,
  DROP COLUMN `pickup_pincode`,
  DROP COLUMN `pickup_address`;


-- ---------------------------------------------------------------------------
-- STEP 7 (002b) — the backfill rows.
-- Normally NOT needed: 002a's rollback drops the whole table. This step exists
-- for the case where the history table must be kept but the snapshots were
-- wrong. It requires temporarily removing the append-only guard.
-- ---------------------------------------------------------------------------
-- DROP TRIGGER `trg_dsh_block_delete`;
-- DELETE FROM donation_status_history WHERE is_reconstructed = 1;
-- CREATE TRIGGER `trg_dsh_block_delete`
--   BEFORE DELETE ON `donation_status_history` FOR EACH ROW
--   BEGIN
--     SIGNAL SQLSTATE '45000'
--       SET MESSAGE_TEXT = 'donation_status_history is append-only: DELETE is not permitted.';
--   END;
-- Delete is_reconstructed = 1 rows ONLY. A genuine transition is a fact.


-- ---------------------------------------------------------------------------
-- STEP 8 (002a) — the history table. DESTRUCTIVE once genuine transitions exist.
-- Export first if there is any doubt:
--   SELECT * FROM donation_status_history
--     INTO OUTFILE 'C:/backup/donation_status_history_YYYYMMDD.csv'
--     FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n';
-- ---------------------------------------------------------------------------
DROP TRIGGER `trg_dsh_block_delete`;
DROP TRIGGER `trg_dsh_block_update`;
DROP TABLE `donation_status_history`;


-- ---------------------------------------------------------------------------
-- STEP 9 (001) — credentials. DESTRUCTIVE: every hash is lost and every user
-- must be re-invited.
-- ---------------------------------------------------------------------------
-- SELECT user_id, password_hash, must_change_password, created_at
--   FROM user_credential
--    INTO OUTFILE 'C:/backup/user_credential_YYYYMMDD.csv'
--    FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n';
DROP TABLE `user_credential`;


-- ---------------------------------------------------------------------------
-- POST-ROLLBACK VERIFICATION
-- ---------------------------------------------------------------------------
-- 1. 000_preflight.sql: P3 must be 0 for all objects, P4 and P5 must return no
--    rows, P7 must still total 104 with the same per-table counts.
-- 2. validation/CONTENT_FINGERPRINT.sql must match the PRE-migration capture
--    exactly — including the combined digest. That proves the data came back,
--    not just the counts.
-- 3. python database/audit_db.py (default baseline database/schema.sql): exit 0.
--    After a COMPLETE rollback the live schema is again byte-compatible with the
--    frozen pre-migration export, so the default baseline is the correct one.
-- 4. Record the rollback in the ledger, never as "applied". See
--    RUNNER_DESIGN.md §3 (state transition to `rolled_back`).


-- ---------------------------------------------------------------------------
-- WHEN NOT TO ROLL BACK
-- ---------------------------------------------------------------------------
-- Roll back a STRUCTURAL mistake (wrong type, bad constraint, trigger that
-- blocks legitimate work) before data depends on it.
-- Do NOT roll back to "tidy up" after the application has been running: the
-- additive objects are inert when unused, while the drops destroy real records.
-- Use a forward-fix migration in that case.
