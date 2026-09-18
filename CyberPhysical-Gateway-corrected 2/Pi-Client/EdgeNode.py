import socket
import time
import json

# Change server Ip to correct IP 
SERVER_IP = "X.X.X.X" 
PORT = 8080

def start_client():
    while True:
        try:
            print(f"Attempting to connect to {SERVER_IP}:{PORT}...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((SERVER_IP, PORT))
            print("Successfully connected to Java Hub!")

            while True:
                payload = {
                    "sensor": "AS608_Fingerprint",
                    "uid": 4,
                    "action": "access_request"
                }
                
                message = json.dumps(payload) + "\n"
                
                client_socket.sendall(message.encode('utf-8'))
                print(f"Sent Payload: {message.strip()}")
                
                time.sleep(5)
                
        except ConnectionRefusedError:
            print("Connection refused. Is the Java server running? Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"Connection dropped: {e}. Reconnecting...")
            time.sleep(5)

if __name__ == "__main__":
    start_client()