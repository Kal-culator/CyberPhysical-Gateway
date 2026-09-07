#include <WiFi.h>

const char* ssid = "YOUR_HOTSPOT_NAME";
const char* password = "YOUR_HOTSPOT_PASSWORD";
const char* serverName = "YOUR_LAPTOP_IP_ADDRESS";
const int serverPort = 8080;

WiFiClient client;

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
}

void loop() {
  if (client.connect(serverName, serverPort)) {
    Serial.println("Connected to Java Server!");
    
    String payload = "TEST_SCAN_ID_04";
    client.println(payload);
    
    Serial.println("Payload sent: " + payload);
    client.stop(); 
  } else {
    Serial.println("Connection to Java Server failed.");
  }
  
  delay(5000); 
}