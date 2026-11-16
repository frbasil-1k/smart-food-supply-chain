-- ============================================================================
-- 002b_backfill_donation_history.sql   —   F2 (part 2 of 2): legacy snapshots
-- DRAFT — UNEXECUTED. Do not run outside the approved migration batch.
--
-- Inserts exactly one reconstructed snapshot per existing donation. No
-- timestamps, no actors, no invented previous states.
--
-- Requires 002a. This is a DML-only file, so it is repeatable and recoverable;
-- it contains no DDL and no statement that fails when the work is already done.
--
-- PRECONDITION (require table exists and 0 reconstructed rows):
--   SELECT COUNT(*) FROM donation_status_history WHERE is_reconstructed = 1;
-- ============================================================================

INSERT INTO `donation_status_history`
      (`donation_id`, `from_status`, `to_status`, `changed_by_user_id`,
       `changed_at`, `is_reconstructed`, `note`)
SELECT d.`donation_id`,
       NULL,
       d.`donation_status`,
       NULL,
       NULL,
       1,
       'State observed when history tracking began; earlier transitions were not recorded'
  FROM `donation` d
  LEFT JOIN `donation_status_history` h
         ON h.`donation_id` = d.`donation_id`
        AND h.`is_reconstructed` = 1
 WHERE h.`history_id` IS NULL;

-- Expected: 5 rows inserted on the verified baseline
-- (4 COMPLETED, 1 APPROVED).

-- ---------------------------------------------------------------------------
-- Why this is safe to repeat
-- ---------------------------------------------------------------------------
-- 1. `WHERE h.history_id IS NULL` skips donations that already have a snapshot.
-- 2. `uq_dsh_one_reconstructed` (002a) is the structural backstop: even if the
--    WHERE clause were defeated by a concurrent run, the second insert of the
--    same donation fails with 1062 instead of creating a duplicate.
-- 3. The statement is a single INSERT ... SELECT, which InnoDB applies
--    atomically: it either inserts all 5 rows or none. A "half backfill" is not
--    a state this statement can produce.
-- 4. Re-running it after a successful run affects 0 rows and changes nothing.
--
-- ---------------------------------------------------------------------------
-- RECOVERY PROCEDURE (R1)
-- ---------------------------------------------------------------------------
-- Read the actual result before doing anything else:
--
--   SELECT COUNT(*) AS snapshots,
--          COUNT(DISTINCT donation_id) AS donations_covered
--     FROM donation_status_history WHERE is_reconstructed = 1;
--
-- Case A — file never ran (0 rows):
--   Run it. Nothing to undo.
--
-- Case B — it ran, 5 rows, 5 donations (the expected state):
--   Nothing to do. Do not re-run for reassurance; V002b-A already proves it.
--
-- Case C — 0 rows for some donations that exist (a partial state):
--   Impossible from one statement, but possible if a previous batch was killed
--   between CHECK and COMMIT. Simply re-run 002b; the LEFT JOIN skips what is
--   already there.
--
-- Case D — a wrong snapshot exists (e.g. it captured a status that has since
--   changed, or the note text is wrong). Because 002a makes the table
--   append-only, you cannot fix it with UPDATE/DELETE — by design. The
--   controlled repair, performed by a DBA inside the maintenance window and
--   recorded in the migration ledger as a data correction, is:
--     1. DROP TRIGGER trg_dsh_block_delete;          -- temporarily
--     2. DELETE FROM donation_status_history
--         WHERE is_reconstructed = 1 AND donation_id IN (...);
--     3. CREATE TRIGGER trg_dsh_block_delete ... (exactly as in 002a)
--     4. re-run 002b
--   Delete ONLY is_reconstructed = 1 rows. A genuine transition is a fact and
--   must never be removed to tidy a backfill.
--
-- Case E — donation table changed before the backfill (a donation was created
--   between 002a and 002b). Re-running picks it up automatically, so the
--   correct sequence is simply: run 002a, run 002b, then verify the counts match
--   `SELECT COUNT(*) FROM donation`.
--
-- ---------------------------------------------------------------------------
-- Validation after applying (read-only)
-- ---------------------------------------------------------------------------
-- V002b-A  snapshots = 5, donations_covered = 5, and both equal
--          SELECT COUNT(*) FROM donation
-- V002b-B  reconstructed rows carrying a timestamp           -- expect 0
-- V002b-C  reconstructed rows carrying an actor              -- expect 0
-- V002b-D  donations with no history at all                  -- expect 0
-- V002b-E  snapshot status distribution                      -- COMPLETED 4, APPROVED 1
-- V002b-F  re-run 002b: 0 rows affected, still 5 total
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- Covered by 002a's rollback (DROP TABLE). Rolling back only the data would
-- require the trigger surgery in Case D; do not do it without a reason.
