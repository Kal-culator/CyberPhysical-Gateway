#include <WiFi.h>
#include "esp_camera.h"

// --- UPDATED CONFIGURATION ---
const char* ssid = "YOUR_WIFI_SSID";     // Type your exact hotspot name here
const char* password = "YOUR_WIFI_PASSWORD"; // Type your hotspot password here

// 🚨 DEMO DAY WARNING: iPhones change this IP depending on what connects first!
// Yash MUST verify this IP on his Mac using 'ipconfig getifaddr en0' on Demo Day.
const char* serverIP = "172.20.10.3";    
const int serverPort = 8081;             

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  // 🛠️ FIX 1: Zero-initialized to prevent memory crashes
  camera_config_t config = {};
  
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  
  // 🛠️ FIX 2: Core 3.x compatibility (Changed 'sscb' to 'sccb')
  // NOTE: If Arduino throws an error here, change the 'c' back to an 's'!
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // 🛠️ FIX 3 & 4: Fast Resolution & No Ghost Photos
  // Bypassed PSRAM to force SVGA so Telegram alerts send instantly.
  config.frame_size = FRAMESIZE_SVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.grab_mode = CAMERA_GRAB_LATEST; // Forces a brand new photo every time

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
}

void captureAndSend() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  }

  WiFiClient client;
  if (client.connect(serverIP, serverPort)) {
    Serial.println("Connected to Hub. Sending image buffer...");
    client.write(fb->buf, fb->len);
    client.stop();
    Serial.println("Image sent successfully.");
  } else {
    // Suppressed printing so it doesn't spam the Serial monitor
  }
  esp_camera_fb_return(fb);
}

void loop() {
  // 🛠️ FIX 5: The Drop-Off Death Fix
  // Automatically reconnects to your hotspot if the connection glitches
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Wi-Fi lost! Reconnecting...");
    WiFi.disconnect();
    WiFi.reconnect();
    delay(2000);
    return; 
  }

  captureAndSend();
  delay(1500); // 1.5 second rapid-polling
}