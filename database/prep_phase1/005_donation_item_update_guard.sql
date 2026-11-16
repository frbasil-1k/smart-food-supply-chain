-- ============================================================================
-- 005_donation_item_update_guard.sql   —   F5: allocation integrity on UPDATE
-- DRAFT — UNEXECUTED. Do not run outside the approved migration batch.
--
-- One BEFORE UPDATE trigger on DONATION_ITEM covering two independent attacks:
--   A. reducing quantity_kg below what is already delivered + spoiled;
--   B. re-parenting the item to a different donation while deliveries or
--      spoilage rows reference it (review item R6).
-- No column change, no data change.
--
-- PRECONDITION (require 0 rows):
--   SELECT trigger_name FROM information_schema.triggers
--    WHERE trigger_schema = DATABASE()
--      AND trigger_name = 'trg_donation_item_update_guard';
--   -- and no item already violating the quantity invariant:
--   SELECT COUNT(*) FROM donation_item di
--    WHERE di.quantity_kg < COALESCE((SELECT SUM(quantity_delivered_kg)
--            FROM delivery_item WHERE food_item_id = di.food_item_id),0)
--                          + COALESCE((SELECT SUM(quantity_spoiled_kg)
--            FROM spoilage_record WHERE food_item_id = di.food_item_id),0);
-- ============================================================================

DELIMITER ;;

CREATE TRIGGER `trg_donation_item_update_guard`
BEFORE UPDATE ON `donation_item`
FOR EACH ROW
BEGIN
  -- DECIMAL(20,2): SUM() over decimal(8,2) widens the result; a narrow local
  -- would raise "Data truncated" (1264) on a large total and turn a valid
  -- update into a confusing failure.
  DECLARE v_delivered DECIMAL(20,2);
  DECLARE v_spoiled   DECIMAL(20,2);

  -- -------------------------------------------------------------------------
  -- B. Re-parenting. Moving an item to another donation silently invalidates
  -- every existing allocation: delivery_item rows would claim items from a
  -- donation their delivery is not part of, and spoilage would be charged to
  -- the wrong donor. The FK cannot catch it (the item id never changes) and the
  -- audit invariant delivery_item_same_donation only detects it after the fact.
  -- -------------------------------------------------------------------------
  IF NOT (NEW.`donation_id` <=> OLD.`donation_id`) THEN
    IF EXISTS (SELECT 1 FROM `delivery_item`
                WHERE `food_item_id` = OLD.`food_item_id`)
       OR EXISTS (SELECT 1 FROM `spoilage_record`
                   WHERE `food_item_id` = OLD.`food_item_id`) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Cannot move a donation item to another donation while delivery or spoilage records reference it.';
    END IF;
  END IF;

  -- -------------------------------------------------------------------------
  -- A. Shrinking the denominator. Only a reduction can break the invariant;
  -- increases and no-op updates are untouched, so unrelated edits never fail
  -- because of pre-existing data.
  -- -------------------------------------------------------------------------
  IF NEW.`quantity_kg` < OLD.`quantity_kg` THEN

    -- Two scalar subqueries, not two JOINs: joining both child tables would
    -- multiply rows and under-count the protected total.
    SELECT COALESCE(SUM(`quantity_delivered_kg`), 0)
      INTO v_delivered
      FROM `delivery_item`
     WHERE `food_item_id` = OLD.`food_item_id`;

    SELECT COALESCE(SUM(`quantity_spoiled_kg`), 0)
      INTO v_spoiled
      FROM `spoilage_record`
     WHERE `food_item_id` = OLD.`food_item_id`;

    -- COALESCE handles items with no deliveries and no spoilage: 0 + 0, so any
    -- positive new quantity passes.
    IF NEW.`quantity_kg` < v_delivered + v_spoiled THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Reduced quantity is below the quantity already delivered plus spoiled.';
    END IF;
  END IF;
END;;

DELIMITER ;

-- ---------------------------------------------------------------------------
-- Interaction with the existing protections (complement, never replace)
-- ---------------------------------------------------------------------------
-- Existing, unchanged:
--   trg_delivery_item_insert/_update   numerator: item belongs to the delivery's
--                                     donation, and delivered + spoiled + new
--                                     <= donated.
--   trg_spoilage_quantity_insert/_update  numerator, from the spoilage side.
--   chk_donation_quantity, chk_delivery_quantity, chk_spoilage_quantity
--                                     reject non-positive quantities.
--   FK delivery_item.food_item_id / spoilage_record.food_item_id (RESTRICT)
--                                     block deleting an allocated item.
-- New here: the two paths the schema left open — lowering quantity_kg after
-- allocation, and moving an allocated item to another donation. Nothing above
-- is modified, weakened or replaced.
--
-- Deliberate scope limit: re-parenting an item with NO delivery and NO spoilage
-- rows is allowed. There is nothing to corrupt, and blocking it would prevent a
-- legitimate data-entry correction.
--
-- ---------------------------------------------------------------------------
-- Concurrency and lock order (review item R6)
-- ---------------------------------------------------------------------------
-- A trigger reads a consistent snapshot; it does not lock child rows. Worse, in
-- REPEATABLE READ a plain SELECT inside a transaction reads the snapshot taken
-- at the transaction's first read, so a long-running allocation transaction can
-- compute its remaining quantity from stale data and pass a check that is no
-- longer true.
--
-- The rule for every write path that consumes or changes an item's quantity —
-- allocation (delivery_item insert), spoilage recording, and quantity edits:
--
--   BEGIN;
--     SELECT quantity_kg FROM donation_item
--      WHERE food_item_id = :id FOR UPDATE;   -- CURRENT read + row lock, FIRST
--     -- ... only now read delivered/spoiled totals ...
--     INSERT INTO delivery_item (...) ;        -- or UPDATE donation_item
--   COMMIT;
--
-- `FOR UPDATE` is a locking read: it re-reads the latest committed row (not the
-- transaction snapshot) and blocks any concurrent writer of the same row, so the
-- three paths serialise on one row, in one order, before any child rows are
-- examined. The trigger stays the last line of defence for anything that
-- bypasses the protocol — it rejects the impossible row rather than storing it.
--
-- Residual risk, stated plainly: a path that skips the lock can still
-- oversubscribe inside a narrow window. The alloc_le_donated invariant detects
-- the result. This is strictly narrower than the pre-migration schema, where no
-- UPDATE was guarded at all.
--
-- ---------------------------------------------------------------------------
-- Backend obligation (R6)
-- ---------------------------------------------------------------------------
-- The API must reject re-parenting with a clear, non-500 error *before* the
-- trigger fires:
--   PATCH /api/v1/donation-items/{id} with a different donation_id
--     -> 409 Conflict
--        {"error": "item_has_allocations",
--         "detail": "This item already has deliveries or spoilage recorded and
--                    cannot be moved to another donation."}
-- The trigger is the backstop for any path that forgets; the 409 is the user
-- experience. Both are tested (F5-14, F5-15).
--
-- ---------------------------------------------------------------------------
-- Validation after applying (read-only; negatives dev-only)
-- ---------------------------------------------------------------------------
-- V005-A  trigger exists, BEFORE UPDATE, on donation_item
-- V005-B  increase passes                    UPDATE ... quantity_kg + 1
-- V005-C  reduction to exactly delivered+spoiled passes
-- V005-D  reduction below delivered+spoiled  -- 1644
-- V005-E  item with no children: reduction passes
-- V005-F  item with no children: quantity 0  -- 3819 from chk_donation_quantity
-- V005-G  re-parent WITH children            -- 1644
-- V005-H  re-parent WITHOUT children         -- succeeds
-- V005-I  unrelated update on an allocated item (item_name) -- succeeds
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- DROP TRIGGER `trg_donation_item_update_guard`;
-- Complete and safe: no data is created or altered by this object.
