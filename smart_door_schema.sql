CREATE DATABASE IF NOT EXISTS smart_door_demo;
USE smart_door_demo;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    fingerprint_id INT NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    clearance_level VARCHAR(50) DEFAULT 'Standard User',
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS access_events (
    event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    fingerprint_id VARCHAR(50) DEFAULT 'UNKNOWN',
    pi_decision VARCHAR(50) NOT NULL,
    final_action VARCHAR(50) NOT NULL,
    event_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT IGNORE INTO users (fingerprint_id, full_name, clearance_level) VALUES 
(1, 'Yash', 'System Administrator'),
(2, 'Sadiq', 'Hardware Engineer');

CREATE OR REPLACE VIEW vw_live_threat_dashboard AS
SELECT 
    e.event_id AS 'Log_ID',
    DATE_FORMAT(e.event_time, '%M %d, %Y - %H:%i:%s') AS 'Timestamp',
    COALESCE(u.full_name, '⚠️ UNREGISTERED INTRUDER') AS 'Subject_Identity',
    COALESCE(u.clearance_level, 'NONE') AS 'Clearance',
    e.pi_decision AS 'Edge_Node_Decision',
    e.final_action AS 'Physical_Lock_Status'
FROM access_events e
LEFT JOIN users u ON e.fingerprint_id = u.fingerprint_id
ORDER BY e.event_time DESC;