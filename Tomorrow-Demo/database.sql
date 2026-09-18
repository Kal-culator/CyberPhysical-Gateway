CREATE DATABASE IF NOT EXISTS smart_door_demo
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE smart_door_demo;

CREATE TABLE IF NOT EXISTS users (
  user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fingerprint_id INT NOT NULL,
  user_name VARCHAR(100) NOT NULL,
  authorized BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_fingerprint (fingerprint_id)
);

DROP TABLE IF EXISTS access_events;

CREATE TABLE access_events (
  event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(80) NOT NULL,
  fingerprint_id INT NULL,
  confidence INT NOT NULL,
  pi_decision ENUM('GRANTED', 'REVIEW') NOT NULL,
  database_authorized BOOLEAN NOT NULL,
  telegram_decision ENUM('NOT_REQUIRED', 'YES', 'NO', 'TIMEOUT', 'ERROR') NOT NULL,
  final_action ENUM('OPEN', 'BUZZER') NOT NULL,
  user_id BIGINT UNSIGNED NULL,
  relay_channel TINYINT UNSIGNED NOT NULL,
  event_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (event_id),
  KEY idx_events_time (event_time),
  CONSTRAINT fk_events_user FOREIGN KEY (user_id) REFERENCES users (user_id)
);

INSERT INTO users (fingerprint_id, user_name, authorized)
VALUES (1, 'Demo User', TRUE)
ON DUPLICATE KEY UPDATE user_name = VALUES(user_name), authorized = VALUES(authorized);

SELECT fingerprint_id, user_name, authorized FROM users;
