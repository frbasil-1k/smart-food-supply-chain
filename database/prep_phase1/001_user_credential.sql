-- ============================================================================
-- 001_user_credential.sql   —   F1: authentication table
-- DRAFT — UNEXECUTED. Do not run outside the approved migration batch.
--
-- Creates exactly one new table, 11 columns. APP_USER is not modified.
-- Nothing is inserted: existing users get NO credential row.
--
-- PRECONDITION (run and require 0 rows):
--   SELECT table_name FROM information_schema.tables
--    WHERE table_schema = DATABASE() AND table_name = 'user_credential';
-- ============================================================================

CREATE TABLE `user_credential` (
  `user_id`              INT              NOT NULL
                         COMMENT 'One credential row per APP_USER; PK enforces uniqueness',
  `password_hash`        VARCHAR(255)     NOT NULL
                         COMMENT 'v1 algorithm: Werkzeug scrypt (scrypt:N:r:p$salt$digest)',
  `must_change_password` TINYINT(1)       NOT NULL DEFAULT 1
                         COMMENT '1 until the user sets their own password',
  `failed_attempts`      TINYINT UNSIGNED NOT NULL DEFAULT 0
                         COMMENT 'Consecutive failures; reset to 0 on success',
  `locked_until`         DATETIME         NULL DEFAULT NULL
                         COMMENT 'Temporary lock expiry; NULL = not locked',
  `last_login_at`        DATETIME         NULL DEFAULT NULL,
  `password_changed_at`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reset_token_hash`     CHAR(64)         NULL DEFAULT NULL
                         COMMENT 'SHA-256 hex of a single-use activation/reset token',
  `reset_expires_at`     DATETIME         NULL DEFAULT NULL,
  `created_at`           DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`           DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_cred_reset_token` (`reset_token_hash`),
  CONSTRAINT `fk_credential_user` FOREIGN KEY (`user_id`)
    REFERENCES `app_user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `chk_cred_lock_consistency`
    CHECK (`locked_until` IS NULL OR `failed_attempts` > 0),
  CONSTRAINT `chk_cred_token_pairing`
    CHECK ((`reset_token_hash` IS NULL AND `reset_expires_at` IS NULL)
        OR (`reset_token_hash` IS NOT NULL AND `reset_expires_at` IS NOT NULL))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Authentication material, deliberately separate from APP_USER profile data';

-- ---------------------------------------------------------------------------
-- Password-hashing policy — v1 is SCrypt, stated plainly (review item R5)
-- ---------------------------------------------------------------------------
-- Algorithm for this release: Werkzeug `generate_password_hash`, default method
-- `scrypt` (format `scrypt:32768:8:1$<salt>$<hex digest>`, 255-character column
-- is ample). This is the only algorithm the backend issues and the only one the
-- audit accepts: its `cred_non_scrypt_hash` invariant counts rows whose hash does
-- not start with `scrypt:`, and that invariant must stay at 0.
--
-- Argon2 is NOT supported in v1 — not by the backend, not by the audit script.
-- No documentation, UI text or comment in this package should imply otherwise.
-- Moving to Argon2 later is a deliberate, reviewable change: the audit invariant
-- is relaxed in the same commit that teaches the backend to verify both formats,
-- and existing hashes are re-hashed on next successful login.
--
-- For that reason there is deliberately NO `CHECK (password_hash LIKE 'scrypt:%')`
-- in this table. The format is policy, not structure: pinning it in the schema
-- would make the future algorithm change a live ALTER plus a data rewrite, while
-- the audit already fails loudly if a non-scrypt hash appears.
--
-- ---------------------------------------------------------------------------
-- Design notes
-- ---------------------------------------------------------------------------
-- PK user_id            "One credential record per user", structurally. A second
--                       INSERT for the same user fails with 1062.
-- FK ON DELETE CASCADE  A deleted user's credential must not survive. The app
--                       never deletes users (it sets account_status), so this is
--                       a safety net, not a workflow.
-- uq_cred_reset_token   Tokens are looked up on activation/reset. UNIQUE also
--                       prevents two live tokens sharing a hash. MySQL allows
--                       many NULLs in a unique index, so idle rows are fine.
-- chk_cred_lock_consistency  A lock must have been earned by a failure. It is
--                       one-way: an admin may clear locked_until while leaving
--                       the counter, so it cannot trap an account.
-- chk_cred_token_pairing  A half-written reset (hash with no expiry, or an
--                       expiry with no token) is unstorable. It catches the two
--                       service bugs that would otherwise produce an
--                       un-expiring token or an unusable deadline. Column count
--                       stays 11.
--
-- ---------------------------------------------------------------------------
-- Existing users: NOTHING IS INSERTED HERE
-- ---------------------------------------------------------------------------
-- The 15 existing APP_USER rows receive no credential. Their logins fail with
-- the same generic message as a wrong password (no user enumeration) until a
-- manager issues an activation token:
--   1. manager POST /api/v1/users/{id}/credential-invite
--   2. server writes reset_token_hash = sha256(token), reset_expires_at = now+24h
--      (both fields together — enforced by chk_cred_token_pairing) and returns
--      the raw token once, out of band
--   3. user POST /api/v1/auth/activate {token, new_password}
--   4. server verifies hash, expiry and single use; writes password_hash with
--      Werkzeug scrypt, must_change_password = 0, clears BOTH token fields
-- No password or hash is invented for anyone, and no shared default exists.
--
-- Lockout policy (approved, unchanged by this revision)
--   5 consecutive failures -> locked_until = now + 15 minutes
--   repeated lockouts double 15 -> 30 -> 60 minutes, capped at 60
--   success resets failed_attempts = 0 AND locked_until = NULL (required by
--     chk_cred_lock_consistency)
--   per-IP throttling runs in addition to per-account lockout, so an attacker
--     cannot cheaply lock every account from one address
--   the audit observation cred_locked_out reports currently locked accounts,
--     which is how a mass-lockout attempt becomes visible
--
-- ---------------------------------------------------------------------------
-- Validation after applying (read-only)
-- ---------------------------------------------------------------------------
-- V001-A  table exists with 11 columns, 1 unique index, 2 CHECKs
-- V001-B  SELECT COUNT(*) FROM user_credential;                        -- 0
-- V001-C  users without a credential                                  -- 15
-- V001-D  FK rejects an unknown user                                  -- 1452
-- V001-E  token pairing (dev DB): hash without expiry, and expiry without
--         token, both rejected                                       -- 3819
-- V001-F  lock consistency (dev DB): locked_until with failed_attempts = 0
--                                                                    -- 3819
--
-- ---------------------------------------------------------------------------
-- Rollback
-- ---------------------------------------------------------------------------
-- DROP TABLE `user_credential`;
-- Nothing references it. Destroys all hashes: after rollback every user must be
-- re-invited. Once users have set passwords, treat rollback as data loss and
-- prefer a forward fix.
