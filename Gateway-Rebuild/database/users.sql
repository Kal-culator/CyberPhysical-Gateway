-- Run on the Mac in MySQL after the server has started once.
USE cyberphysical_v2;
SELECT * FROM gateway_users;
-- Rename ID 1 without changing its fingerprint template:
-- UPDATE gateway_users SET full_name='Your name' WHERE fingerprint_id=1;
-- After enrolling sensor ID 2 on the Pi, authorize it:
-- INSERT INTO gateway_users (fingerprint_id,full_name,authorized) VALUES (2,'Second user',TRUE);
-- Revoke access without deleting the sensor template:
-- UPDATE gateway_users SET authorized=FALSE WHERE fingerprint_id=2;
-- Remove an old mapping when deleting/reassigning a template:
-- DELETE FROM gateway_users WHERE fingerprint_id=2;
SELECT * FROM gateway_events ORDER BY event_id DESC LIMIT 20;
