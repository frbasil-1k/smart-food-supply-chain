
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `app_user` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `full_name` varchar(100) NOT NULL,
  `email` varchar(150) NOT NULL,
  `phone` varchar(15) NOT NULL,
  `user_role` enum('DONOR','NGO_MANAGER','DRIVER','SAFETY_INSPECTOR') NOT NULL,
  `account_status` enum('ACTIVE','INACTIVE','SUSPENDED') DEFAULT 'ACTIVE',
  `primary_branch_id` int DEFAULT NULL,
  `supervisor_user_id` int DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `email` (`email`),
  KEY `supervisor_user_id` (`supervisor_user_id`),
  KEY `fk_user_branch` (`primary_branch_id`),
  CONSTRAINT `app_user_ibfk_1` FOREIGN KEY (`supervisor_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `fk_user_branch` FOREIGN KEY (`primary_branch_id`) REFERENCES `branch` (`branch_id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `branch` (
  `branch_id` int NOT NULL AUTO_INCREMENT,
  `organization_id` int NOT NULL,
  `branch_name` varchar(150) NOT NULL,
  `address` varchar(255) NOT NULL,
  `pincode` varchar(10) NOT NULL,
  `contact_no` varchar(15) NOT NULL,
  `established_date` date NOT NULL,
  `regional_manager_user_id` int DEFAULT NULL,
  PRIMARY KEY (`branch_id`),
  KEY `organization_id` (`organization_id`),
  KEY `regional_manager_user_id` (`regional_manager_user_id`),
  CONSTRAINT `branch_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`organization_id`),
  CONSTRAINT `branch_ibfk_2` FOREIGN KEY (`regional_manager_user_id`) REFERENCES `app_user` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_branch_manager_insert` BEFORE INSERT ON `branch` FOR EACH ROW BEGIN
    IF NEW.regional_manager_user_id IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM APP_USER
            WHERE user_id = NEW.regional_manager_user_id
              AND user_role = 'NGO_MANAGER'
       ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Regional manager must have NGO_MANAGER role.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_branch_manager_update` BEFORE UPDATE ON `branch` FOR EACH ROW BEGIN
    IF NEW.regional_manager_user_id IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM APP_USER
            WHERE user_id = NEW.regional_manager_user_id
              AND user_role = 'NGO_MANAGER'
       ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Regional manager must have NGO_MANAGER role.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `coverage_area` (
  `coverage_area_id` int NOT NULL AUTO_INCREMENT,
  `area_name` varchar(100) NOT NULL,
  `city` varchar(100) NOT NULL,
  `pincode` varchar(10) NOT NULL,
  PRIMARY KEY (`coverage_area_id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `delivery` (
  `delivery_id` int NOT NULL AUTO_INCREMENT,
  `donation_id` int NOT NULL,
  `route_id` int NOT NULL,
  `driver_user_id` int DEFAULT NULL COMMENT 'ACTUAL driver of this delivery; NULL = not recorded (all pre-F4 rows)',
  `recipient_branch_id` int NOT NULL,
  `delivered_at` datetime DEFAULT NULL,
  `scheduled_for` datetime DEFAULT NULL COMMENT 'Planned delivery window; NULL = not scheduled/not recorded',
  `delivery_status` enum('PLANNED','IN_TRANSIT','DELIVERED','FAILED','CANCELLED') DEFAULT 'PLANNED',
  PRIMARY KEY (`delivery_id`),
  KEY `donation_id` (`donation_id`),
  KEY `route_id` (`route_id`),
  KEY `recipient_branch_id` (`recipient_branch_id`),
  KEY `idx_delivery_driver_status` (`driver_user_id`,`delivery_status`),
  KEY `idx_delivery_scheduled` (`scheduled_for`),
  CONSTRAINT `delivery_ibfk_1` FOREIGN KEY (`donation_id`) REFERENCES `donation` (`donation_id`),
  CONSTRAINT `delivery_ibfk_2` FOREIGN KEY (`route_id`) REFERENCES `route` (`route_id`),
  CONSTRAINT `delivery_ibfk_3` FOREIGN KEY (`recipient_branch_id`) REFERENCES `branch` (`branch_id`),
  CONSTRAINT `fk_delivery_driver` FOREIGN KEY (`driver_user_id`) REFERENCES `app_user` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_delivery_inspection_insert` BEFORE INSERT ON `delivery` FOR EACH ROW BEGIN
    DECLARE latest_status VARCHAR(20);

    IF NEW.delivery_status IN ('IN_TRANSIT', 'DELIVERED') THEN

        SET latest_status = (
            SELECT safety_status
            FROM INSPECTION_LOG
            WHERE donation_id = NEW.donation_id
            ORDER BY inspected_at DESC, inspection_id DESC
            LIMIT 1
        );

        IF latest_status IS NULL OR latest_status <> 'PASSED' THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT =
            'Delivery blocked: latest food inspection has not passed.';
        END IF;

    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`sfc_migrator`@`localhost`*/ /*!50003 TRIGGER `trg_delivery_driver_insert` BEFORE INSERT ON `delivery` FOR EACH ROW BEGIN
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
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_delivery_inspection_update` BEFORE UPDATE ON `delivery` FOR EACH ROW BEGIN
    DECLARE latest_status VARCHAR(20);

    IF NEW.delivery_status IN ('IN_TRANSIT', 'DELIVERED') THEN

        SET latest_status = (
            SELECT safety_status
            FROM INSPECTION_LOG
            WHERE donation_id = NEW.donation_id
            ORDER BY inspected_at DESC, inspection_id DESC
            LIMIT 1
        );

        IF latest_status IS NULL OR latest_status <> 'PASSED' THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT =
            'Delivery blocked: latest food inspection has not passed.';
        END IF;

    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`sfc_migrator`@`localhost`*/ /*!50003 TRIGGER `trg_delivery_driver_update` BEFORE UPDATE ON `delivery` FOR EACH ROW BEGIN
  
  
  IF OLD.`delivery_status` = 'DELIVERED'
     AND NOT (NEW.`driver_user_id` <=> OLD.`driver_user_id`) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Driver attribution is immutable once the delivery is DELIVERED.';
  END IF;

  
  
  
  
  IF NEW.`driver_user_id` IS NOT NULL
     AND NOT (NEW.`driver_user_id` <=> OLD.`driver_user_id`)
     AND NOT EXISTS (SELECT 1 FROM `app_user`
                      WHERE `user_id` = NEW.`driver_user_id`
                        AND `user_role` = 'DRIVER') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Delivery driver must have DRIVER role.';
  END IF;

  
  IF NEW.`delivery_status` = 'IN_TRANSIT' AND NEW.`driver_user_id` IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A delivery cannot enter IN_TRANSIT without an attributed driver.';
  END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `delivery_item` (
  `delivery_item_id` int NOT NULL AUTO_INCREMENT,
  `delivery_id` int NOT NULL,
  `food_item_id` int NOT NULL,
  `quantity_delivered_kg` decimal(8,2) NOT NULL,
  PRIMARY KEY (`delivery_item_id`),
  UNIQUE KEY `delivery_id` (`delivery_id`,`food_item_id`),
  KEY `food_item_id` (`food_item_id`),
  CONSTRAINT `delivery_item_ibfk_1` FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`),
  CONSTRAINT `delivery_item_ibfk_2` FOREIGN KEY (`food_item_id`) REFERENCES `donation_item` (`food_item_id`),
  CONSTRAINT `chk_delivery_quantity` CHECK ((`quantity_delivered_kg` > 0))
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_delivery_item_insert` BEFORE INSERT ON `delivery_item` FOR EACH ROW BEGIN
    DECLARE v_delivery_donation INT;
    DECLARE v_item_donation INT;
    DECLARE v_donated_qty DECIMAL(8,2);
    DECLARE v_delivered_qty DECIMAL(10,2);
    DECLARE v_spoiled_qty DECIMAL(10,2);

    SELECT donation_id
    INTO v_delivery_donation
    FROM DELIVERY
    WHERE delivery_id = NEW.delivery_id;

    SELECT donation_id, quantity_kg
    INTO v_item_donation, v_donated_qty
    FROM DONATION_ITEM
    WHERE food_item_id = NEW.food_item_id;

    IF v_delivery_donation <> v_item_donation THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Food item does not belong to this delivery donation.';
    END IF;

    SELECT COALESCE(SUM(quantity_delivered_kg), 0)
    INTO v_delivered_qty
    FROM DELIVERY_ITEM
    WHERE food_item_id = NEW.food_item_id;

    SELECT COALESCE(SUM(quantity_spoiled_kg), 0)
    INTO v_spoiled_qty
    FROM SPOILAGE_RECORD
    WHERE food_item_id = NEW.food_item_id;

    IF v_delivered_qty + v_spoiled_qty +
       NEW.quantity_delivered_kg > v_donated_qty THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Total allocated quantity exceeds available donated quantity.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_delivery_item_update` BEFORE UPDATE ON `delivery_item` FOR EACH ROW BEGIN
    DECLARE v_delivery_donation INT;
    DECLARE v_item_donation INT;
    DECLARE v_donated_qty DECIMAL(8,2);
    DECLARE v_delivered_qty DECIMAL(10,2);
    DECLARE v_spoiled_qty DECIMAL(10,2);

    SELECT donation_id
    INTO v_delivery_donation
    FROM DELIVERY
    WHERE delivery_id = NEW.delivery_id;

    SELECT donation_id, quantity_kg
    INTO v_item_donation, v_donated_qty
    FROM DONATION_ITEM
    WHERE food_item_id = NEW.food_item_id;

    IF v_delivery_donation <> v_item_donation THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Food item does not belong to this delivery donation.';
    END IF;

    SELECT COALESCE(SUM(quantity_delivered_kg), 0)
    INTO v_delivered_qty
    FROM DELIVERY_ITEM
    WHERE food_item_id = NEW.food_item_id
      AND delivery_item_id <> OLD.delivery_item_id;

    SELECT COALESCE(SUM(quantity_spoiled_kg), 0)
    INTO v_spoiled_qty
    FROM SPOILAGE_RECORD
    WHERE food_item_id = NEW.food_item_id;

    IF v_delivered_qty + v_spoiled_qty +
       NEW.quantity_delivered_kg > v_donated_qty THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Total allocated quantity exceeds available donated quantity.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `delivery_review` (
  `review_id` int NOT NULL AUTO_INCREMENT,
  `delivery_id` int NOT NULL,
  `reviewer_user_id` int NOT NULL,
  `rating` tinyint NOT NULL,
  `quality_notes` text,
  `review_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`review_id`),
  UNIQUE KEY `delivery_id` (`delivery_id`),
  KEY `reviewer_user_id` (`reviewer_user_id`),
  CONSTRAINT `delivery_review_ibfk_1` FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`),
  CONSTRAINT `delivery_review_ibfk_2` FOREIGN KEY (`reviewer_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `chk_review_rating` CHECK ((`rating` between 1 and 5))
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_review_manager_insert` BEFORE INSERT ON `delivery_review` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM DELIVERY d
        JOIN BRANCH b
            ON d.recipient_branch_id = b.branch_id
        JOIN APP_USER u
            ON b.regional_manager_user_id = u.user_id
        WHERE d.delivery_id = NEW.delivery_id
          AND u.user_id = NEW.reviewer_user_id
          AND u.user_role = 'NGO_MANAGER'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Only the receiving branch manager can review this delivery.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_review_manager_update` BEFORE UPDATE ON `delivery_review` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM DELIVERY d
        JOIN BRANCH b
            ON d.recipient_branch_id = b.branch_id
        JOIN APP_USER u
            ON b.regional_manager_user_id = u.user_id
        WHERE d.delivery_id = NEW.delivery_id
          AND u.user_id = NEW.reviewer_user_id
          AND u.user_role = 'NGO_MANAGER'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Reviewer must be the receiving branch manager.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dependent` (
  `driver_user_id` int NOT NULL,
  `dependent_no` int NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `relationship` varchar(50) NOT NULL,
  `date_of_birth` date DEFAULT NULL,
  `phone` varchar(15) DEFAULT NULL,
  PRIMARY KEY (`driver_user_id`,`dependent_no`),
  CONSTRAINT `dependent_ibfk_1` FOREIGN KEY (`driver_user_id`) REFERENCES `app_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `donation` (
  `donation_id` int NOT NULL AUTO_INCREMENT,
  `donor_user_id` int NOT NULL,
  `pickup_route_id` int DEFAULT NULL,
  `pickup_datetime` datetime NOT NULL,
  `pickup_address` varchar(255) DEFAULT NULL COMMENT 'Free-form pickup address; NULL = not recorded (legacy)',
  `pickup_pincode` varchar(10) DEFAULT NULL COMMENT 'Indian PIN, stored normalised as 6 digits; NULL = not recorded',
  `pickup_contact` varchar(15) DEFAULT NULL COMMENT 'Pickup contact, stored normalised as +91XXXXXXXXXX; NULL = not recorded',
  `donation_status` enum('PENDING','SCHEDULED','COLLECTED','APPROVED','REJECTED','PARTIALLY_DISTRIBUTED','COMPLETED','CANCELLED') DEFAULT 'PENDING',
  `urgency_level` enum('LOW','NORMAL','HIGH') DEFAULT 'NORMAL',
  PRIMARY KEY (`donation_id`),
  KEY `donor_user_id` (`donor_user_id`),
  KEY `pickup_route_id` (`pickup_route_id`),
  CONSTRAINT `donation_ibfk_1` FOREIGN KEY (`donor_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `donation_ibfk_2` FOREIGN KEY (`pickup_route_id`) REFERENCES `route` (`route_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_donation_donor_insert` BEFORE INSERT ON `donation` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM APP_USER
        WHERE user_id = NEW.donor_user_id
          AND user_role = 'DONOR'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Only users with DONOR role can register donations.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_donation_donor_update` BEFORE UPDATE ON `donation` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM APP_USER
        WHERE user_id = NEW.donor_user_id
          AND user_role = 'DONOR'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Donation must belong to a user with DONOR role.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `donation_item` (
  `food_item_id` int NOT NULL AUTO_INCREMENT,
  `donation_id` int NOT NULL,
  `category_id` int NOT NULL,
  `item_name` varchar(150) NOT NULL,
  `quantity_kg` decimal(8,2) NOT NULL,
  `prepared_at` datetime DEFAULT NULL,
  `best_before` datetime NOT NULL,
  PRIMARY KEY (`food_item_id`),
  KEY `donation_id` (`donation_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `donation_item_ibfk_1` FOREIGN KEY (`donation_id`) REFERENCES `donation` (`donation_id`),
  CONSTRAINT `donation_item_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `food_category` (`category_id`),
  CONSTRAINT `chk_donation_quantity` CHECK ((`quantity_kg` > 0)),
  CONSTRAINT `chk_food_dates` CHECK (((`prepared_at` is null) or (`best_before` > `prepared_at`)))
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`sfc_migrator`@`localhost`*/ /*!50003 TRIGGER `trg_donation_item_update_guard` BEFORE UPDATE ON `donation_item` FOR EACH ROW BEGIN
  
  
  
  DECLARE v_delivered DECIMAL(20,2);
  DECLARE v_spoiled   DECIMAL(20,2);

  
  
  
  
  
  
  
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

  
  
  
  
  
  IF NEW.`quantity_kg` < OLD.`quantity_kg` THEN

    
    
    SELECT COALESCE(SUM(`quantity_delivered_kg`), 0)
      INTO v_delivered
      FROM `delivery_item`
     WHERE `food_item_id` = OLD.`food_item_id`;

    SELECT COALESCE(SUM(`quantity_spoiled_kg`), 0)
      INTO v_spoiled
      FROM `spoilage_record`
     WHERE `food_item_id` = OLD.`food_item_id`;

    
    
    IF NEW.`quantity_kg` < v_delivered + v_spoiled THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
          'Reduced quantity is below the quantity already delivered plus spoiled.';
    END IF;
  END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `donation_status_history` (
  `history_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `donation_id` int NOT NULL,
  `from_status` enum('PENDING','SCHEDULED','COLLECTED','APPROVED','REJECTED','PARTIALLY_DISTRIBUTED','COMPLETED','CANCELLED') DEFAULT NULL COMMENT 'NULL = no previous state on record (creation, or legacy snapshot)',
  `to_status` enum('PENDING','SCHEDULED','COLLECTED','APPROVED','REJECTED','PARTIALLY_DISTRIBUTED','COMPLETED','CANCELLED') NOT NULL,
  `changed_by_user_id` int DEFAULT NULL COMMENT 'Actor of a genuine transition; NULL for legacy snapshots',
  `changed_at` datetime DEFAULT NULL COMMENT 'Real event time. NULL only for reconstructed rows.',
  `is_reconstructed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '1 = state observed when tracking began, not a real transition',
  `note` varchar(255) DEFAULT NULL,
  `reconstructed_donation_id` int GENERATED ALWAYS AS (if((`is_reconstructed` = 1),`donation_id`,NULL)) STORED COMMENT 'Structural guarantee: at most ONE reconstructed row per donation',
  PRIMARY KEY (`history_id`),
  UNIQUE KEY `uq_dsh_one_reconstructed` (`reconstructed_donation_id`),
  KEY `idx_dsh_donation_time` (`donation_id`,`changed_at`,`history_id`),
  KEY `fk_dsh_user` (`changed_by_user_id`),
  CONSTRAINT `fk_dsh_donation` FOREIGN KEY (`donation_id`) REFERENCES `donation` (`donation_id`),
  CONSTRAINT `fk_dsh_user` FOREIGN KEY (`changed_by_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `chk_dsh_distinct_status` CHECK (((`from_status` is null) or (`from_status` <> `to_status`))),
  CONSTRAINT `chk_dsh_reconstructed_no_actor` CHECK (((`is_reconstructed` = 0) or (`changed_by_user_id` is null))),
  CONSTRAINT `chk_dsh_time_semantics` CHECK ((((`is_reconstructed` = 0) and (`changed_at` is not null)) or ((`is_reconstructed` = 1) and (`changed_at` is null))))
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Append-only donation status transitions; legacy rows are reconstructed';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`sfc_migrator`@`localhost`*/ /*!50003 TRIGGER `trg_dsh_block_update` BEFORE UPDATE ON `donation_status_history` FOR EACH ROW BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'donation_status_history is append-only: UPDATE is not permitted.';
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`sfc_migrator`@`localhost`*/ /*!50003 TRIGGER `trg_dsh_block_delete` BEFORE DELETE ON `donation_status_history` FOR EACH ROW BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'donation_status_history is append-only: DELETE is not permitted.';
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `food_category` (
  `category_id` int NOT NULL AUTO_INCREMENT,
  `category_name` varchar(100) NOT NULL,
  PRIMARY KEY (`category_id`),
  UNIQUE KEY `category_name` (`category_name`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspection_log` (
  `inspection_id` int NOT NULL AUTO_INCREMENT,
  `donation_id` int NOT NULL,
  `inspector_user_id` int NOT NULL,
  `inspected_at` datetime NOT NULL,
  `temperature_c` decimal(5,2) DEFAULT NULL,
  `packaging_integrity` enum('INTACT','DAMAGED','NOT_APPLICABLE') NOT NULL,
  `safety_status` enum('PASSED','FAILED','NEEDS_REVIEW') NOT NULL,
  `remarks` text,
  PRIMARY KEY (`inspection_id`),
  KEY `donation_id` (`donation_id`),
  KEY `inspector_user_id` (`inspector_user_id`),
  CONSTRAINT `inspection_log_ibfk_1` FOREIGN KEY (`donation_id`) REFERENCES `donation` (`donation_id`),
  CONSTRAINT `inspection_log_ibfk_2` FOREIGN KEY (`inspector_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `chk_temperature_range` CHECK (((`temperature_c` is null) or ((`temperature_c` >= -(50)) and (`temperature_c` <= 150))))
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_inspector_insert` BEFORE INSERT ON `inspection_log` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM APP_USER
        WHERE user_id = NEW.inspector_user_id
          AND user_role = 'SAFETY_INSPECTOR'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Only safety inspectors can perform inspections.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_inspector_update` BEFORE UPDATE ON `inspection_log` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM APP_USER
        WHERE user_id = NEW.inspector_user_id
          AND user_role = 'SAFETY_INSPECTOR'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Inspector must have SAFETY_INSPECTOR role.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `organization` (
  `organization_id` int NOT NULL AUTO_INCREMENT,
  `organization_name` varchar(150) NOT NULL,
  `hq_address` varchar(255) NOT NULL,
  `hq_pincode` varchar(10) NOT NULL,
  `hq_contact_no` varchar(15) NOT NULL,
  PRIMARY KEY (`organization_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `route` (
  `route_id` int NOT NULL AUTO_INCREMENT,
  `managing_branch_id` int NOT NULL,
  `designated_driver_user_id` int NOT NULL,
  `coverage_area_id` int NOT NULL,
  `route_type` enum('PICKUP','DISTRIBUTION','MIXED') NOT NULL,
  `route_status` enum('ACTIVE','INACTIVE') DEFAULT 'ACTIVE',
  PRIMARY KEY (`route_id`),
  KEY `managing_branch_id` (`managing_branch_id`),
  KEY `designated_driver_user_id` (`designated_driver_user_id`),
  KEY `coverage_area_id` (`coverage_area_id`),
  CONSTRAINT `route_ibfk_1` FOREIGN KEY (`managing_branch_id`) REFERENCES `branch` (`branch_id`),
  CONSTRAINT `route_ibfk_2` FOREIGN KEY (`designated_driver_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `route_ibfk_3` FOREIGN KEY (`coverage_area_id`) REFERENCES `coverage_area` (`coverage_area_id`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_route_driver_insert` BEFORE INSERT ON `route` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM APP_USER
        WHERE user_id = NEW.designated_driver_user_id
          AND user_role = 'DRIVER'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Only users with DRIVER role can be assigned to routes.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_route_driver_update` BEFORE UPDATE ON `route` FOR EACH ROW BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM APP_USER
        WHERE user_id = NEW.designated_driver_user_id
          AND user_role = 'DRIVER'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Designated driver must have DRIVER role.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `route_assignment` (
  `user_id` int NOT NULL,
  `route_id` int NOT NULL,
  `hours_per_week` decimal(5,2) NOT NULL,
  `assigned_date` date NOT NULL,
  PRIMARY KEY (`user_id`,`route_id`),
  KEY `route_id` (`route_id`),
  CONSTRAINT `route_assignment_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `route_assignment_ibfk_2` FOREIGN KEY (`route_id`) REFERENCES `route` (`route_id`),
  CONSTRAINT `chk_route_hours` CHECK (((`hours_per_week` > 0) and (`hours_per_week` <= 168)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `schema_migrations` (
  `version` varchar(20) NOT NULL,
  `name` varchar(120) NOT NULL,
  `checksum` char(64) NOT NULL,
  `state` enum('started','applied','failed','rolled_back') NOT NULL DEFAULT 'started',
  `started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `applied_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `duration_ms` int unsigned DEFAULT NULL,
  `note` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `spoilage_record` (
  `spoilage_id` int NOT NULL AUTO_INCREMENT,
  `food_item_id` int NOT NULL,
  `reported_by_user_id` int NOT NULL,
  `quantity_spoiled_kg` decimal(8,2) NOT NULL,
  `reported_at` datetime NOT NULL,
  `reason` varchar(255) NOT NULL,
  PRIMARY KEY (`spoilage_id`),
  KEY `food_item_id` (`food_item_id`),
  KEY `reported_by_user_id` (`reported_by_user_id`),
  CONSTRAINT `spoilage_record_ibfk_1` FOREIGN KEY (`food_item_id`) REFERENCES `donation_item` (`food_item_id`),
  CONSTRAINT `spoilage_record_ibfk_2` FOREIGN KEY (`reported_by_user_id`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `chk_spoilage_quantity` CHECK ((`quantity_spoiled_kg` > 0))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_spoilage_quantity_insert` BEFORE INSERT ON `spoilage_record` FOR EACH ROW BEGIN
    DECLARE v_donated_qty DECIMAL(8,2);
    DECLARE v_delivered_qty DECIMAL(10,2);
    DECLARE v_spoiled_qty DECIMAL(10,2);

    SELECT quantity_kg
    INTO v_donated_qty
    FROM DONATION_ITEM
    WHERE food_item_id = NEW.food_item_id;

    SELECT COALESCE(SUM(quantity_delivered_kg), 0)
    INTO v_delivered_qty
    FROM DELIVERY_ITEM
    WHERE food_item_id = NEW.food_item_id;

    SELECT COALESCE(SUM(quantity_spoiled_kg), 0)
    INTO v_spoiled_qty
    FROM SPOILAGE_RECORD
    WHERE food_item_id = NEW.food_item_id;

    IF v_delivered_qty + v_spoiled_qty +
       NEW.quantity_spoiled_kg > v_donated_qty THEN

        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Spoiled quantity exceeds the available donated quantity.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_spoilage_quantity_update` BEFORE UPDATE ON `spoilage_record` FOR EACH ROW BEGIN
    DECLARE v_donated_qty DECIMAL(8,2);
    DECLARE v_delivered_qty DECIMAL(10,2);
    DECLARE v_spoiled_qty DECIMAL(10,2);

    SELECT quantity_kg
    INTO v_donated_qty
    FROM DONATION_ITEM
    WHERE food_item_id = NEW.food_item_id;

    SELECT COALESCE(SUM(quantity_delivered_kg), 0)
    INTO v_delivered_qty
    FROM DELIVERY_ITEM
    WHERE food_item_id = NEW.food_item_id;

    SELECT COALESCE(SUM(quantity_spoiled_kg), 0)
    INTO v_spoiled_qty
    FROM SPOILAGE_RECORD
    WHERE food_item_id = NEW.food_item_id
      AND spoilage_id <> OLD.spoilage_id;

    IF v_delivered_qty + v_spoiled_qty +
       NEW.quantity_spoiled_kg > v_donated_qty THEN

        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
        'Spoiled quantity exceeds the available donated quantity.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_credential` (
  `user_id` int NOT NULL COMMENT 'One credential row per APP_USER; PK enforces uniqueness',
  `password_hash` varchar(255) NOT NULL COMMENT 'v1 algorithm: Werkzeug scrypt (scrypt:N:r:p$salt$digest)',
  `must_change_password` tinyint(1) NOT NULL DEFAULT '1' COMMENT '1 until the user sets their own password',
  `failed_attempts` tinyint unsigned NOT NULL DEFAULT '0' COMMENT 'Consecutive failures; reset to 0 on success',
  `locked_until` datetime DEFAULT NULL COMMENT 'Temporary lock expiry; NULL = not locked',
  `last_login_at` datetime DEFAULT NULL,
  `password_changed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reset_token_hash` char(64) DEFAULT NULL COMMENT 'SHA-256 hex of a single-use activation/reset token',
  `reset_expires_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_cred_reset_token` (`reset_token_hash`),
  CONSTRAINT `fk_credential_user` FOREIGN KEY (`user_id`) REFERENCES `app_user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `chk_cred_lock_consistency` CHECK (((`locked_until` is null) or (`failed_attempts` > 0))),
  CONSTRAINT `chk_cred_token_pairing` CHECK ((((`reset_token_hash` is null) and (`reset_expires_at` is null)) or ((`reset_token_hash` is not null) and (`reset_expires_at` is not null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Authentication material, deliberately separate from APP_USER profile data';
/*!40101 SET character_set_client = @saved_cs_client */;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `vw_donor_impact` AS SELECT 
 1 AS `donor_id`,
 1 AS `donor_name`,
 1 AS `total_donations`,
 1 AS `total_donated_kg`,
 1 AS `delivered_kg`,
 1 AS `spoiled_kg`,
 1 AS `undistributed_balance_kg`*/;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `vw_donor_sustainability` AS SELECT 
 1 AS `donor_id`,
 1 AS `donor_name`,
 1 AS `total_donations`,
 1 AS `total_donated_kg`,
 1 AS `total_distributed_kg`,
 1 AS `total_spoiled_kg`*/;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `vw_driver_performance` AS SELECT 
 1 AS `driver_id`,
 1 AS `driver_name`,
 1 AS `assigned_routes`,
 1 AS `completed_deliveries`,
 1 AS `delivered_quantity_kg`*/;
SET character_set_client = @saved_cs_client;
/*!50001 DROP VIEW IF EXISTS `vw_donor_impact`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`sfc_migrator`@`localhost` SQL SECURITY INVOKER */
/*!50001 VIEW `vw_donor_impact` AS select `u`.`user_id` AS `donor_id`,`u`.`full_name` AS `donor_name`,coalesce(`h`.`total_donations`,0) AS `total_donations`,coalesce(`h`.`total_donated_kg`,0) AS `total_donated_kg`,coalesce(`dv`.`delivered_kg`,0) AS `delivered_kg`,coalesce(`sp`.`spoiled_kg`,0) AS `spoiled_kg`,((coalesce(`h`.`total_donated_kg`,0) - coalesce(`dv`.`delivered_kg`,0)) - coalesce(`sp`.`spoiled_kg`,0)) AS `undistributed_balance_kg` from (((`app_user` `u` left join (select `d`.`donor_user_id` AS `donor_user_id`,count(distinct `d`.`donation_id`) AS `total_donations`,sum(`i`.`quantity_kg`) AS `total_donated_kg` from (`donation` `d` left join `donation_item` `i` on((`i`.`donation_id` = `d`.`donation_id`))) where (`d`.`donation_status` <> 'CANCELLED') group by `d`.`donor_user_id`) `h` on((`h`.`donor_user_id` = `u`.`user_id`))) left join (select `d`.`donor_user_id` AS `donor_user_id`,sum(`di`.`quantity_delivered_kg`) AS `delivered_kg` from ((`donation` `d` join `delivery` `d2` on((`d2`.`donation_id` = `d`.`donation_id`))) join `delivery_item` `di` on((`di`.`delivery_id` = `d2`.`delivery_id`))) where ((`d2`.`delivery_status` = 'DELIVERED') and (`d`.`donation_status` <> 'CANCELLED')) group by `d`.`donor_user_id`) `dv` on((`dv`.`donor_user_id` = `u`.`user_id`))) left join (select `d`.`donor_user_id` AS `donor_user_id`,sum(`s`.`quantity_spoiled_kg`) AS `spoiled_kg` from ((`donation` `d` join `donation_item` `i2` on((`i2`.`donation_id` = `d`.`donation_id`))) join `spoilage_record` `s` on((`s`.`food_item_id` = `i2`.`food_item_id`))) where (`d`.`donation_status` <> 'CANCELLED') group by `d`.`donor_user_id`) `sp` on((`sp`.`donor_user_id` = `u`.`user_id`))) where (`u`.`user_role` = 'DONOR') */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP VIEW IF EXISTS `vw_donor_sustainability`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `vw_donor_sustainability` AS select `u`.`user_id` AS `donor_id`,`u`.`full_name` AS `donor_name`,coalesce(`ds`.`total_donations`,0) AS `total_donations`,coalesce(`ds`.`total_donated_kg`,0) AS `total_donated_kg`,coalesce(`dd`.`total_distributed_kg`,0) AS `total_distributed_kg`,coalesce(`sp`.`total_spoiled_kg`,0) AS `total_spoiled_kg` from (((`app_user` `u` left join (select `d`.`donor_user_id` AS `donor_user_id`,count(distinct `d`.`donation_id`) AS `total_donations`,sum(`di`.`quantity_kg`) AS `total_donated_kg` from (`donation` `d` left join `donation_item` `di` on((`d`.`donation_id` = `di`.`donation_id`))) group by `d`.`donor_user_id`) `ds` on((`u`.`user_id` = `ds`.`donor_user_id`))) left join (select `d`.`donor_user_id` AS `donor_user_id`,sum(`di`.`quantity_delivered_kg`) AS `total_distributed_kg` from ((`donation` `d` join `delivery` `de` on((`d`.`donation_id` = `de`.`donation_id`))) join `delivery_item` `di` on((`de`.`delivery_id` = `di`.`delivery_id`))) group by `d`.`donor_user_id`) `dd` on((`u`.`user_id` = `dd`.`donor_user_id`))) left join (select `d`.`donor_user_id` AS `donor_user_id`,sum(`s`.`quantity_spoiled_kg`) AS `total_spoiled_kg` from ((`donation` `d` join `donation_item` `di` on((`d`.`donation_id` = `di`.`donation_id`))) join `spoilage_record` `s` on((`di`.`food_item_id` = `s`.`food_item_id`))) group by `d`.`donor_user_id`) `sp` on((`u`.`user_id` = `sp`.`donor_user_id`))) where (`u`.`user_role` = 'DONOR') */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP VIEW IF EXISTS `vw_driver_performance`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `vw_driver_performance` AS select `u`.`user_id` AS `driver_id`,`u`.`full_name` AS `driver_name`,count(distinct `r`.`route_id`) AS `assigned_routes`,count(distinct (case when (`d`.`delivery_status` = 'DELIVERED') then `d`.`delivery_id` end)) AS `completed_deliveries`,coalesce(sum((case when (`d`.`delivery_status` = 'DELIVERED') then `di`.`quantity_delivered_kg` else 0 end)),0) AS `delivered_quantity_kg` from (((`app_user` `u` left join `route` `r` on((`u`.`user_id` = `r`.`designated_driver_user_id`))) left join `delivery` `d` on((`r`.`route_id` = `d`.`route_id`))) left join `delivery_item` `di` on((`d`.`delivery_id` = `di`.`delivery_id`))) where (`u`.`user_role` = 'DRIVER') group by `u`.`user_id`,`u`.`full_name` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

