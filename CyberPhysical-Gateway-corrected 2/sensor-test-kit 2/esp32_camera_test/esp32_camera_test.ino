// AI-Thinker ESP32-CAM + OV2640. Arduino-ESP32 3.x.
// No LCD/relay/sensor GPIOs are controlled by this sketch.
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"
#include "secrets.h"

WebServer server(80);
bool ready = false;

void capture() {
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) {
    server.send(503, "text/plain", "Camera capture failed");
    return;
  }
  if (frame->format != PIXFORMAT_JPEG) {
    esp_camera_fb_return(frame);
    server.send(500, "text/plain", "Expected JPEG frame");
    return;
  }
  server.sendHeader("Cache-Control", "no-store");
  server.setContentLength(frame->len);
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  client.setTimeout(3000);
  size_t sent = 0;
  unsigned long started = millis();
  while (sent < frame->len && client.connected() && millis() - started < 3000) {
    size_t left = frame->len - sent;
    size_t chunk = left > 1460 ? 1460 : left;
    size_t count = client.write(frame->buf + sent, chunk);
    if (count == 0) break;
    sent += count;
  }
  bool incomplete = sent != frame->len;
  esp_camera_fb_return(frame);  // Always return the frame, including failed writes.
  if (incomplete) client.stop();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  // AI-Thinker camera wiring. Do not reuse these pins for other sensors.
  c.pin_d0 = 5;   c.pin_d1 = 18; c.pin_d2 = 19; c.pin_d3 = 21;
  c.pin_d4 = 36;  c.pin_d5 = 39; c.pin_d6 = 34; c.pin_d7 = 35;
  c.pin_xclk = 0; c.pin_pclk = 22;
  c.pin_vsync = 25; c.pin_href = 23;
  c.pin_sccb_sda = 26; c.pin_sccb_scl = 27;
  c.pin_pwdn = 32; c.pin_reset = -1;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = psramFound() ? FRAMESIZE_VGA : FRAMESIZE_QVGA;
  c.jpeg_quality = 12;
  c.fb_count = psramFound() ? 2 : 1;
  c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  c.grab_mode = psramFound() ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;

  esp_err_t error = esp_camera_init(&c);
  if (error != ESP_OK) {
    Serial.printf("Camera init FAILED: 0x%x. Check camera ribbon and power.\n", error);
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 30000) {
    delay(250);
    Serial.print('.');
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWi-Fi failed. Check 2.4 GHz credentials and reset the board.");
    return;
  }
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", R"HTML(
<!doctype html><html lang="en"><meta name="viewport" content="width=device-width">
<title>ESP32 camera test</title><h1>ESP32-CAM test</h1>
<p>Press Capture to obtain a new image.</p>
<button onclick="document.getElementById('photo').src='/capture?t='+Date.now()">Capture</button>
<p><img id="photo" src="/capture" alt="Camera frame" style="max-width:100%"></p>
</html>)HTML");
  });
  server.on("/capture", HTTP_GET, capture);
  server.on("/health", HTTP_GET, []() {
    server.send(200, "application/json", "{\"camera_initialized\":true,\"psram\":" +
                String(psramFound() ? "true" : "false") + "}");
  });
  server.begin();
  ready = true;
  Serial.print("\nCamera ready: http://");
  Serial.println(WiFi.localIP());
  Serial.println("Use that address for camera_url in the Pi config.json.");
}

void loop() {
  if (ready) server.handleClient();
  delay(2);
}
