-- Run once as your existing MySQL administrator. Does not modify smart_door_demo.
CREATE DATABASE IF NOT EXISTS cyberphysical_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- The server creates its versioned tables and seeds ID 1 on first start.
-- Optional dedicated user. Replace the password below before running these lines:
-- CREATE USER 'gateway'@'localhost' IDENTIFIED BY 'REPLACE_WITH_YOUR_PASSWORD';
-- GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON cyberphysical_v2.* TO 'gateway'@'localhost';
