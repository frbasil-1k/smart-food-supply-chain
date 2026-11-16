-- ============================================================================
-- 004a_delivery_attribution.sql   —   F4 (part 1 of 2): the columns
-- DRAFT — UNEXECUTED. Do not run outside the approved migration batch.
--
-- Structure only: two nullable columns, two indexes, one foreign key.
-- The behavioural guards are 004b, a separate file, so that a trigger mistake
-- cannot leave a partly-applied ALTER behind.
--
-- NO BACKFILL. Every existing DELIVERY row keeps driver_user_id = NULL and
-- scheduled_for = NULL. The route's designated driver is that route's current
-- designation; writing it into historical deliveries would fabricate the past.
--
-- PRECONDITION (require 0 rows):
--   SELECT column_name FROM information_schema.columns
--    WHERE table_schema = DATABASE() AND table_name = 'delivery'
--      AND column_name IN ('driver_user_id','scheduled_for');
-- ============================================================================

ALTER TABLE `delivery`
  ADD COLUMN `driver_user_id` INT NULL DEFAULT NULL
    COMMENT 'ACTUAL driver of this delivery; NULL = not recorded (all pre-F4 rows)'
    AFTER `route_id`,
  ADD COLUMN `scheduled_for` DATETIME NULL DEFAULT NULL
    COMMENT 'Planned delivery window; NULL = not scheduled/not recorded'
    AFTER `delivered_at`,
  ADD KEY `idx_delivery_driver_status` (`driver_user_id`, `delivery_status`),
  ADD KEY `idx_delivery_scheduled` (`scheduled_for`),
  ADD CONSTRAINT `fk_delivery_driver` FOREIGN KEY (`driver_user_id`)
    REFERENCES `app_user` (`user_id`);

-- Index rationale
--   idx_delivery_driver_status  driver screens filter "my deliveries, by
--                               status"; the actual-driver report groups by
--                               driver. Its leading column also satisfies the
--                               FK's index requirement.
--   idx_delivery_scheduled      manager "planned this week" date-range filter.
--
-- Deliberately absent: UNIQUE(donation_id, recipient_branch_id).
--   Two deliveries from one donation to the same branch are an approved
--   workflow. The allocation workspace warns; the database does not block.
--   V004 checks that no such unique index exists (and only that exact pair).
--
-- No CHECK on driver_user_id: NULL is a legal, meaningful value (legacy rows).
-- Role, status and immutability rules are in 004b and the service layer.
--
-- ---------------------------------------------------------------------------
-- Validation after applying (read-only)
-- ---------------------------------------------------------------------------
-- V004a-A  both columns exist, nullable, no default
-- V004a-B  fk_delivery_driver present -> app_user(user_id)
-- V004a-C  both indexes present
-- V004a-D  SELECT COUNT(*) FROM delivery WHERE driver_user_id IS NULL;  -- 5
-- V004a-E  SELECT COUNT(*) FROM delivery WHERE scheduled_for  IS NULL;  -- 5
-- V004a-F  no unique index on (donation_id, recipient_branch_id)        -- 0
-- V004a-G  no triggers named trg_delivery_driver_% yet                  -- 0
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- ALTER TABLE `delivery`
--   DROP FOREIGN KEY `fk_delivery_driver`,
--   DROP KEY `idx_delivery_scheduled`,
--   DROP KEY `idx_delivery_driver_status`,
--   DROP COLUMN `scheduled_for`,
--   DROP COLUMN `driver_user_id`;
-- Run 004b's rollback (drop the two triggers) first.
