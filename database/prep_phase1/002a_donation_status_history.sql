-- ============================================================================
-- 002a_donation_status_history.sql   —   F2 (part 1 of 2): the history table
-- DRAFT — UNEXECUTED. Do not run outside the approved migration batch.
--
-- Creates the table, its constraints, its exactly-one-snapshot guarantee and
-- its append-only guards. Inserts NOTHING — the legacy backfill is 002b, a
-- separate file, because MySQL DDL commits independently: if this file
-- succeeded and the backfill failed inside the same file, the file could not be
-- rerun (CREATE TABLE would fail with 1050) and the batch would be stuck.
--
-- PRECONDITION (require 0 rows):
--   SELECT table_name FROM information_schema.tables
--    WHERE table_schema = DATABASE() AND table_name = 'donation_status_history';
--   SELECT trigger_name FROM information_schema.triggers
--    WHERE trigger_schema = DATABASE() AND trigger_name LIKE 'trg_dsh_%';
-- ============================================================================

CREATE TABLE `donation_status_history` (
  `history_id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `donation_id`        INT             NOT NULL,
  `from_status`        ENUM('PENDING','SCHEDULED','COLLECTED','APPROVED',
                            'REJECTED','PARTIALLY_DISTRIBUTED','COMPLETED',
                            'CANCELLED') NULL DEFAULT NULL
                       COMMENT 'NULL = no previous state on record (creation, or legacy snapshot)',
  `to_status`          ENUM('PENDING','SCHEDULED','COLLECTED','APPROVED',
                            'REJECTED','PARTIALLY_DISTRIBUTED','COMPLETED',
                            'CANCELLED') NOT NULL,
  `changed_by_user_id` INT             NULL DEFAULT NULL
                       COMMENT 'Actor of a genuine transition; NULL for legacy snapshots',
  `changed_at`         DATETIME        NULL DEFAULT NULL
                       COMMENT 'Real event time. NULL only for reconstructed rows.',
  `is_reconstructed`   TINYINT(1)      NOT NULL DEFAULT 0
                       COMMENT '1 = state observed when tracking began, not a real transition',
  `note`               VARCHAR(255)    NULL DEFAULT NULL,
  `reconstructed_donation_id` INT
       GENERATED ALWAYS AS (IF(`is_reconstructed` = 1, `donation_id`, NULL)) STORED
       COMMENT 'Structural guarantee: at most ONE reconstructed row per donation',
  PRIMARY KEY (`history_id`),
  UNIQUE KEY `uq_dsh_one_reconstructed` (`reconstructed_donation_id`),
  KEY `idx_dsh_donation_time` (`donation_id`, `changed_at`, `history_id`),
  KEY `fk_dsh_user` (`changed_by_user_id`),
  CONSTRAINT `fk_dsh_donation` FOREIGN KEY (`donation_id`)
    REFERENCES `donation` (`donation_id`),
  CONSTRAINT `fk_dsh_user` FOREIGN KEY (`changed_by_user_id`)
    REFERENCES `app_user` (`user_id`),
  CONSTRAINT `chk_dsh_time_semantics` CHECK (
       (`is_reconstructed` = 0 AND `changed_at` IS NOT NULL)
    OR (`is_reconstructed` = 1 AND `changed_at` IS NULL)
  ),
  CONSTRAINT `chk_dsh_distinct_status` CHECK (
       `from_status` IS NULL OR `from_status` <> `to_status`
  ),
  CONSTRAINT `chk_dsh_reconstructed_no_actor` CHECK (
       `is_reconstructed` = 0 OR `changed_by_user_id` IS NULL
  )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Append-only donation status transitions; legacy rows are reconstructed';

-- ---------------------------------------------------------------------------
-- Append-only, enforced (R4)
-- ---------------------------------------------------------------------------
-- The table is described as append-only, so the database must mean it. These
-- two triggers reject every UPDATE and every DELETE with SQLSTATE 45000.
-- Insert remains the only legal write, which is all the application needs.
--
-- Why triggers rather than only a least-privilege account: the account grants
-- are part of the deployment, and a grant mistake is silent, while a trigger
-- fails loudly. The intended app-account grants are the second layer and are
-- specified in RUNNER_DESIGN.md §5b:
--     GRANT SELECT, INSERT ON smart_food_supply_chain.* TO 'sfc_app'@'localhost';
--     GRANT UPDATE ON smart_food_supply_chain.donation TO 'sfc_app'@'localhost';
--     -- ...and 11 more one-table UPDATE grants, plus 3 one-table DELETE grants.
--     -- MySQL takes exactly ONE privilege level per GRANT: each table needs its own
--     -- statement; listing several tables after ON is a 1064 syntax error.
--     -- This table appears in NEITHER list: no UPDATE, no DELETE, no DROP.
-- Note the shape: the baseline grant never includes UPDATE/DELETE, so there is
-- none to revoke. MySQL privileges are additive, and a table-level REVOKE cannot
-- carve an exception out of a database-wide GRANT (RUNNER_DESIGN.md §5c).
-- Both layers are documented so neither is mistaken for the whole story.
--
-- Known limits, stated rather than papered over:
--   * TRUNCATE bypasses row triggers. The app account must not have DROP
--     (TRUNCATE requires it), and the audit detects an empty history table.
--   * A privileged account can DROP the triggers. Nothing in the database can
--     prevent that; it is detected by the audit's structural comparison, which
--     expects exactly these two triggers.
DELIMITER ;;

CREATE TRIGGER `trg_dsh_block_update`
BEFORE UPDATE ON `donation_status_history`
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'donation_status_history is append-only: UPDATE is not permitted.';
END;;

CREATE TRIGGER `trg_dsh_block_delete`
BEFORE DELETE ON `donation_status_history`
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'donation_status_history is append-only: DELETE is not permitted.';
END;;

DELIMITER ;

-- ---------------------------------------------------------------------------
-- Column and constraint notes
-- ---------------------------------------------------------------------------
-- reconstructed_donation_id  A stored generated column: the donation id when
--   the row is reconstructed, NULL otherwise. The UNIQUE key on it makes "at
--   most one reconstructed snapshot per donation" a database guarantee, not a
--   convention. Genuine rows are all NULL, and MySQL allows unlimited NULLs in
--   a unique index, so any number of real transitions per donation is legal.
--   The real cost: it is one extra column on a new table, invisible to the API
--   because the service never selects it.
-- chk_dsh_time_semantics     A reconstructed row cannot carry a timestamp, and a
--   genuine row cannot lack one. Fabricating history becomes impossible.
-- chk_dsh_reconstructed_no_actor  A legacy snapshot cannot be attributed to a
--   person who did not act.
-- chk_dsh_distinct_status    No pointless PENDING -> PENDING rows.
--
-- ENUM instead of VARCHAR: invalid values are rejected by the server. The cost
-- is that adding a donation status requires altering two tables in one
-- migration; that is documented in MIGRATION_PLAN.md §4 rather than hidden.
--
-- ---------------------------------------------------------------------------
-- Validation after applying (read-only)
-- ---------------------------------------------------------------------------
-- V002a-A  11 columns including the generated one; 1 unique index; 3 CHECKs; 2 FKs
-- V002a-B  generated column is STORED and the expression is the expected IF()
-- V002a-C  two triggers exist, BEFORE UPDATE and BEFORE DELETE
-- V002a-D  SELECT COUNT(*) FROM donation_status_history;              -- expect 0
-- V002a-E  append-only proof (dev DB only):
--          INSERT a valid genuine row, then UPDATE it      -- expect 1644
--          DELETE it                                       -- expect 1644
--          UPDATE donation_status_history SET note = 'x';  -- expect 1644
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- DROP TRIGGER `trg_dsh_block_delete`;
-- DROP TRIGGER `trg_dsh_block_update`;
-- DROP TABLE `donation_status_history`;
-- Drops the triggers first so the table can be dropped/re-created cleanly and
-- so no trigger is left orphaned if the batch is abandoned mid-way.
