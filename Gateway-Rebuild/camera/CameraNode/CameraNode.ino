// AI Thinker ESP32-CAM; Arduino ESP32 core 3.x. Camera uses Wi-Fi, no Pi GPIO wires.
#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "Secrets.h"

bool cameraReady=false;
unsigned long lastAttempt=0,lastReconnect=0;

bool initCamera() {
  camera_config_t c={};
  c.ledc_channel=LEDC_CHANNEL_0;c.ledc_timer=LEDC_TIMER_0;
  c.pin_d0=5;c.pin_d1=18;c.pin_d2=19;c.pin_d3=21;
  c.pin_d4=36;c.pin_d5=39;c.pin_d6=34;c.pin_d7=35;
  c.pin_xclk=0;c.pin_pclk=22;c.pin_vsync=25;c.pin_href=23;
  c.pin_sccb_sda=26;c.pin_sccb_scl=27;c.pin_pwdn=32;c.pin_reset=-1;
  c.xclk_freq_hz=20000000;c.pixel_format=PIXFORMAT_JPEG;
  c.frame_size=FRAMESIZE_VGA;c.jpeg_quality=12;c.fb_count=1;
  c.fb_location=psramFound()?CAMERA_FB_IN_PSRAM:CAMERA_FB_IN_DRAM;
  c.grab_mode=CAMERA_GRAB_WHEN_EMPTY;
  esp_err_t result=esp_camera_init(&c);
  if(result!=ESP_OK){Serial.printf("Camera init failed: 0x%x. Check ribbon and power.\n",result);return false;}
  return true;
}
void setup(){
  Serial.begin(115200);delay(300);
  cameraReady=initCamera();
  WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(true);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  Serial.println("Joining Wi-Fi (2.4 GHz)...");
}
void loop(){
  if(!cameraReady){delay(1000);return;}
  if(WiFi.status()!=WL_CONNECTED){
    if(millis()-lastReconnect>10000){lastReconnect=millis();WiFi.reconnect();Serial.println("Wi-Fi reconnecting...");}
    delay(100);return;
  }
  if(millis()-lastAttempt<3000){delay(20);return;}lastAttempt=millis();
  // Single-buffer mode may retain a frame while idle. Discard one and take a fresh one.
  camera_fb_t* old=esp_camera_fb_get();if(old)esp_camera_fb_return(old);
  camera_fb_t* fb=esp_camera_fb_get();
  if(!fb){Serial.println("Capture failed");delay(100);return;}
  HTTPClient http;WiFiClient client;
  http.setConnectTimeout(2500);http.setTimeout(4000);
  String url=String(SERVER_URL)+"/api/camera";
  if(http.begin(client,url)){
    http.addHeader("X-API-Key",API_KEY);http.addHeader("Content-Type","image/jpeg");
    int code=http.POST(fb->buf,fb->len);
    Serial.printf("Camera upload HTTP %d (%u bytes)\n",code,(unsigned)fb->len);
    if(code==401)Serial.println("API key mismatch: use same key as server/Pi.");
    http.end();
  }
  esp_camera_fb_return(fb);
}
