-- ============================================================================
-- 004b_delivery_driver_triggers.sql   —   F4 (part 2 of 2): the guards
-- DRAFT — UNEXECUTED. Do not run outside the approved migration batch.
--
-- Two BEFORE triggers. Corrected semantics (review item R3):
--   1. The driver's role is validated only when attribution is NEWLY SET or
--      CHANGED — never on unrelated updates.
--   2. Attribution becomes immutable once the delivery is DELIVERED.
--   3. A delivery cannot enter IN_TRANSIT without an attributed driver.
--
-- Requires 004a.
--
-- PRECONDITION (require 0 rows):
--   SELECT trigger_name FROM information_schema.triggers
--    WHERE trigger_schema = DATABASE()
--      AND trigger_name IN ('trg_delivery_driver_insert','trg_delivery_driver_update');
--   SELECT COUNT(*) FROM delivery WHERE driver_user_id IS NOT NULL;   -- expect 0
-- ============================================================================

DELIMITER ;;

-- ---------------------------------------------------------------------------
-- INSERT: role must be DRIVER; IN_TRANSIT must carry a driver
-- ---------------------------------------------------------------------------
CREATE TRIGGER `trg_delivery_driver_insert`
BEFORE INSERT ON `delivery`
FOR EACH ROW
BEGIN
  IF NEW.`delivery_status` = 'IN_TRANSIT' AND NEW.`driver_user_id` IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A delivery cannot enter IN_TRANSIT without an attributed driver.';
  END IF;

  IF NEW.`driver_user_id` IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM `app_user`
                      WHERE `user_id` = NEW.`driver_user_id`
                        AND `user_role` = 'DRIVER') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Delivery driver must have DRIVER role.';
  END IF;
END;;

-- ---------------------------------------------------------------------------
-- UPDATE: role checked only on change; frozen after DELIVERED; transit gate
-- ---------------------------------------------------------------------------
CREATE TRIGGER `trg_delivery_driver_update`
BEFORE UPDATE ON `delivery`
FOR EACH ROW
BEGIN
  -- (2) Immutability. NULL-safe: an unchanged NULL stays legal, so the five
  -- legacy DELIVERED rows can still be updated in other columns.
  IF OLD.`delivery_status` = 'DELIVERED'
     AND NOT (NEW.`driver_user_id` <=> OLD.`driver_user_id`) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Driver attribution is immutable once the delivery is DELIVERED.';
  END IF;

  -- (1) Role validated ONLY when the attribution is newly set or changed.
  -- A driver may legitimately leave the DRIVER role after their work is done;
  -- their DELIVERED history must remain valid, and an unrelated update must not
  -- re-litigate it.
  IF NEW.`driver_user_id` IS NOT NULL
     AND NOT (NEW.`driver_user_id` <=> OLD.`driver_user_id`)
     AND NOT EXISTS (SELECT 1 FROM `app_user`
                      WHERE `user_id` = NEW.`driver_user_id`
                        AND `user_role` = 'DRIVER') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Delivery driver must have DRIVER role.';
  END IF;

  -- (3) A delivery in transit must know who is driving it.
  IF NEW.`delivery_status` = 'IN_TRANSIT' AND NEW.`driver_user_id` IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A delivery cannot enter IN_TRANSIT without an attributed driver.';
  END IF;
END;;

DELIMITER ;

-- ---------------------------------------------------------------------------
-- What changed from the first draft, and why
-- ---------------------------------------------------------------------------
-- Old behaviour: every UPDATE re-checked the current holder's DRIVER role. That
-- contradicted the approved historical rule — a driver who legitimately moves to
-- another role would make their DELIVERED rows impossible to touch, and would
-- have amounted to re-validating history against a present-day fact. Role is now
-- a *write-time* condition on assignment, not a standing requirement.
--
-- Account status (ACTIVE) is still NOT checked here. It changes over time and a
-- database gate would make a suspended driver's rows un-repairable. It belongs
-- in the assignment service: a non-ACTIVE account is rejected with 422.
--
-- Immutability applies from DELIVERED, exactly as approved. Between assignment
-- (PLANNED) and DELIVERED, IN_TRANSIT driver changes remain possible at the
-- database level because no correction workflow exists yet and an operational
-- swap (breakdown, handover) must not become impossible. The service restricts
-- it: the IN_TRANSIT -> DELIVERED transition must carry the same driver, and
-- that is covered by test F4-11b.
--
-- NO correction workflow is implemented (review item R3). There is no
-- attribution-history table to record who corrected what, when, and why, and the
-- general audit log (F6) is deferred. Silently permitting an override would be
-- worse than forbidding it. If corrections are needed later, the design is a
-- separate migration with its own table:
--     delivery_driver_correction(correction_id, delivery_id, old_driver_user_id,
--       new_driver_user_id, corrected_by_user_id, corrected_at, reason)
--     + one trigger that allows a change on a DELIVERED row ONLY when the actor
--       is a manager and the reason is recorded. Not built in this phase.
--
-- Trigger order with the existing gates: MySQL fires BEFORE triggers in creation
-- order, so trg_delivery_inspection_insert/_update run first (they predate this
-- migration). Their condition only covers NEW.delivery_status IN
-- ('IN_TRANSIT','DELIVERED'), and ours cover attribution; the conditions are
-- independent, so order does not change the outcome. All five existing
-- deliveries are DELIVERED and their donations' latest inspections are PASSED,
-- so both gates are satisfied for the legacy rows.
--
-- ---------------------------------------------------------------------------
-- Validation after applying (read-only, negatives dev-only)
-- ---------------------------------------------------------------------------
-- V004b-A  two triggers exist, BEFORE INSERT / BEFORE UPDATE on delivery
-- V004b-B  unchanged historical attribution survives an unrelated update:
--          UPDATE delivery SET delivery_status = 'DELIVERED' WHERE delivery_id = 1;
--          -- succeeds, driver_user_id stays NULL
-- V004b-C  role gate on assignment: assign a manager          -- 1644
-- V004b-D  role gate only on change: assign a driver, then
--          UPDATE delivery SET scheduled_for = ... ;          -- succeeds
-- V004b-E  historical driver rights removed: assign a DRIVER at PLANNED, set
--          their role to DONOR in the dev DB, then UPDATE another column
--          -- succeeds (no revalidation). This is the exact R3 scenario.
-- V004b-F  immutability: set a driver on a DELIVERED row       -- 1644
-- V004b-G  transit gate: NEW IN_TRANSIT with NULL driver       -- 1644
-- V004b-H  legacy intact: 5 rows still NULL in both columns
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- DROP TRIGGER `trg_delivery_driver_update`;
-- DROP TRIGGER `trg_delivery_driver_insert`;
-- Complete: triggers hold no data. 004a's rollback then removes the columns.
