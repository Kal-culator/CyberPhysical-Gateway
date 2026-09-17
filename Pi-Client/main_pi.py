import time
import socket
import serial
import json
import adafruit_fingerprint
import RPi.GPIO as GPIO

SERVER_IP = "YOUR_LAPTOP_IP"  # We will change this to Kaamil's hotspot IP later
PORT = 8080

# MAtch this to the breadboard pin ive put samlple numbers
RELAY_PIN = 17    # Pin connected to Deadbolt Relay
BUZZER_PIN = 27   # Pin connected to Buzzer
PIR_PIN = 22      # Pin connected to PIR Motion Sensor

# Setup GPIO Board
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(PIR_PIN, GPIO.IN)

# Ensure deadbolt is locked and buzzer is off initially
GPIO.output(RELAY_PIN, GPIO.LOW)
GPIO.output(BUZZER_PIN, GPIO.LOW)

# --- FINGERPRINT SETUP (Pins 8 & 10) ---
uart = serial.Serial("/dev/serial0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

def send_to_server(message):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((SERVER_IP, PORT))
            s.sendall((message + "\n").encode())
            print(f"Sent to Gateway: {message}")
    except Exception as e:
        print(f"Connection error (Server might be off): {e}")

print("Cyber-Physical System Armed. Waiting for motion...")

try:
    while True:
        if GPIO.input(PIR_PIN):
            print("Motion Detected! Scanning fingerprint...")
            
            if finger.read_image() == adafruit_fingerprint.OK:
                if finger.image_2_tz() == adafruit_fingerprint.OK:
                    if finger.finger_search() == adafruit_fingerprint.OK:
                        
                        print(f"Authorized! ID #{finger.finger_id}")
                        
                        payload = json.dumps({"sensor": "fingerprint", "uid": finger.finger_id, "action": "unlock"})
                        send_to_server(payload)
                        
                        GPIO.output(RELAY_PIN, GPIO.HIGH)
                        time.sleep(5) 
                        GPIO.output(RELAY_PIN, GPIO.LOW) # Lock it back
                        
                    else:
                        
                        print("Unauthorized Fingerprint! Intruder Alert!")
                        
                        send_to_server("TAMPER")
                        
                        GPIO.output(BUZZER_PIN, GPIO.HIGH)
                        time.sleep(3)
                        GPIO.output(BUZZER_PIN, GPIO.LOW)
                        
        time.sleep(0.1) 

except KeyboardInterrupt:
    print("Shutting down...")
    GPIO.cleanup()