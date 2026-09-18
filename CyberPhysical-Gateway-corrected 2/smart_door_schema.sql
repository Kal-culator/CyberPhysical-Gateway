CREATE DATABASE IF NOT EXISTS smart_door_security;
USE smart_door_security;

-- 1. Registered Users
CREATE TABLE users (
    user_id INT PRIMARY KEY,
    user_name VARCHAR(100) NOT NULL,
    fingerprint_id INT UNIQUE NOT NULL,
    rfid_token VARCHAR(255) UNIQUE NOT NULL,
    is_authorized BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Access Attempts
CREATE TABLE access_attempts (
    attempt_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    fingerprint_id INT NULL,
    rfid_token VARCHAR(255) NULL,
    access_status ENUM('AUTHORIZED', 'DENIED', 'TAMPER') NOT NULL,
    failure_count INT DEFAULT 0,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE SET NULL
);

-- 3. Door Unlock Events
CREATE TABLE door_unlock_events (
    unlock_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    attempt_id BIGINT NULL,
    unlock_command VARCHAR(50) DEFAULT 'UNLOCK_DOOR',
    unlock_source ENUM('AUTHORIZED_MATCH', 'OVERRIDE') NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE SET NULL,

    FOREIGN KEY (attempt_id)
        REFERENCES access_attempts(attempt_id)
        ON DELETE SET NULL
);

-- 4. Failed Attempts / Tamper Events
CREATE TABLE tamper_events (
    tamper_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    fingerprint_id INT NULL,
    rfid_token VARCHAR(255) NULL,
    failure_count INT NOT NULL,
    tamper_type VARCHAR(100) NOT NULL,
    camera_blinded BOOLEAN DEFAULT FALSE,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE SET NULL
);

-- 5. Captured Webcam Snapshots
CREATE TABLE security_snapshots (
    snapshot_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tamper_id BIGINT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    luminance_value DECIMAL(10,2) NULL,
    camera_blinded BOOLEAN DEFAULT FALSE,
    telegram_sent BOOLEAN DEFAULT FALSE,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tamper_id)
        REFERENCES tamper_events(tamper_id)
        ON DELETE CASCADE
);

-- 6. Telegram Override Requests
CREATE TABLE override_requests (
    override_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tamper_id BIGINT NOT NULL,
    snapshot_id BIGINT NULL,
    telegram_message_id VARCHAR(100) NULL,
    override_status ENUM('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')
        DEFAULT 'PENDING',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP NULL,

    FOREIGN KEY (tamper_id)
        REFERENCES tamper_events(tamper_id)
        ON DELETE CASCADE,

    FOREIGN KEY (snapshot_id)
        REFERENCES security_snapshots(snapshot_id)
        ON DELETE SET NULL
);

-- 7. ESP32 Devices
CREATE TABLE esp32_devices (
    device_id INT AUTO_INCREMENT PRIMARY KEY,
    device_name VARCHAR(100) NOT NULL,
    device_mac VARCHAR(50) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    device_status ENUM('ONLINE', 'OFFLINE') DEFAULT 'OFFLINE',
    last_seen TIMESTAMP NULL
);

-- 8. Door / Lock Status
CREATE TABLE door_status (
    status_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id INT NOT NULL,
    door_state ENUM('LOCKED', 'UNLOCKED') DEFAULT 'LOCKED',
    relay_state BOOLEAN DEFAULT FALSE,
    gpio_state BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id)
        REFERENCES esp32_devices(device_id)
        ON DELETE CASCADE
);

-- 9. System Commands
CREATE TABLE system_commands (
    command_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id INT NOT NULL,
    command VARCHAR(50) NOT NULL,
    command_status ENUM('SENT', 'RECEIVED', 'EXECUTED', 'FAILED')
        DEFAULT 'SENT',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP NULL,

    FOREIGN KEY (device_id)
        REFERENCES esp32_devices(device_id)
        ON DELETE CASCADE
);

-- Sample Registered User
INSERT INTO users
(user_id, user_name, fingerprint_id, rfid_token)
VALUES
(4, 'User 04', 4, 'RFID_TOKEN_04');

-- Sample ESP32 Device
INSERT INTO esp32_devices
(device_name, device_mac, ip_address)
VALUES
('Door ESP32', 'AA:BB:CC:DD:EE:FF', '192.168.1.100');