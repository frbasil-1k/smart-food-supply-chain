-- 007 review gate — run against the PRE-MIGRATION copy (sfc_restore_verify).
-- This is the SELECT form of vw_donor_impact, unchanged in logic, plus the three
-- assertions the gate requires. Read-only.

-- G1: the numbers the view would return, per donor
SELECT v.*,
       (v.delivered_kg > v.total_donated_kg)        AS violates_delivered_le_donated,
       (v.undistributed_balance_kg < 0)             AS violates_non_negative
  FROM (
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
     WHERE u.`user_role` = 'DONOR'
  ) v
 ORDER BY v.donor_id;

-- G2: aggregate gate assertions (both must be 0)
SELECT COUNT(*)                                  AS donor_rows,
       SUM(v.delivered_kg > v.total_donated_kg)   AS over_delivered_rows,
       SUM(v.undistributed_balance_kg < 0)        AS negative_balance_rows
  FROM (
    SELECT u.`user_id` AS `donor_id`,
           COALESCE(h.`total_donated_kg`, 0)              AS `total_donated_kg`,
           COALESCE(dv.`delivered_kg`, 0)                 AS `delivered_kg`,
           COALESCE(h.`total_donated_kg`, 0)
             - COALESCE(dv.`delivered_kg`, 0)
             - COALESCE(sp.`spoiled_kg`, 0)               AS `undistributed_balance_kg`
      FROM `app_user` u
      LEFT JOIN (SELECT d.`donor_user_id`, SUM(i.`quantity_kg`) AS `total_donated_kg`
                   FROM `donation` d
                   LEFT JOIN `donation_item` i ON i.`donation_id` = d.`donation_id`
                  WHERE d.`donation_status` <> 'CANCELLED'
                  GROUP BY d.`donor_user_id`) h      ON h.`donor_user_id`  = u.`user_id`
      LEFT JOIN (SELECT d.`donor_user_id`, SUM(di.`quantity_delivered_kg`) AS `delivered_kg`
                   FROM `donation` d
                   JOIN `delivery` d2      ON d2.`donation_id` = d.`donation_id`
                   JOIN `delivery_item` di ON di.`delivery_id` = d2.`delivery_id`
                  WHERE d2.`delivery_status` = 'DELIVERED'
                    AND d.`donation_status`  <> 'CANCELLED'
                  GROUP BY d.`donor_user_id`) dv     ON dv.`donor_user_id` = u.`user_id`
      LEFT JOIN (SELECT d.`donor_user_id`, SUM(s.`quantity_spoiled_kg`) AS `spoiled_kg`
                   FROM `donation` d
                   JOIN `donation_item`  i2 ON i2.`donation_id`  = d.`donation_id`
                   JOIN `spoilage_record` s ON s.`food_item_id`   = i2.`food_item_id`
                  WHERE d.`donation_status` <> 'CANCELLED'
                  GROUP BY d.`donor_user_id`) sp     ON sp.`donor_user_id` = u.`user_id`
     WHERE u.`user_role` = 'DONOR'
  ) v;

-- G3: delivery statuses actually present (only DELIVERED should count as delivered)
SELECT delivery_status, COUNT(*) AS deliveries FROM delivery GROUP BY delivery_status;

-- G4: every delivery_item belongs to which delivery status (shows whether any
-- allocation is NOT delivered and therefore correctly excluded)
SELECT d2.delivery_status, COUNT(*) AS items, SUM(di.quantity_delivered_kg) AS kg
  FROM delivery_item di JOIN delivery d2 ON d2.delivery_id = di.delivery_id
 GROUP BY d2.delivery_status;

-- G5: the pre-existing view, for the difference explanation
SELECT * FROM vw_donor_sustainability;

-- G6: spoilage records (spoilage is a loss, subtracted only for the balance)
SELECT COUNT(*) AS spoilage_rows, SUM(quantity_spoiled_kg) AS spoiled_kg FROM spoilage_record;
