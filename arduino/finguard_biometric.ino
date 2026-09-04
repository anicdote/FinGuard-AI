/* FinGuard AI biometric controller for Arduino Uno.
 * USB serial protocol at 115200 baud. Fingerprints are matched locally; no
 * fingerprint image or template data crosses USB.
 */
#include <Adafruit_Fingerprint.h>
#include <Adafruit_NeoPixel.h>
#include <LiquidCrystal_I2C.h>
#include <SoftwareSerial.h>

constexpr uint8_t FINGER_RX_PIN = 2;
constexpr uint8_t FINGER_TX_PIN = 3;
constexpr uint8_t RING_PIN = 6;
constexpr uint8_t BUZZER_PIN = 7;
constexpr uint8_t RING_PIXELS = 12;
constexpr unsigned long VERIFY_TIMEOUT_MS = 30000;

SoftwareSerial fingerprintSerial(FINGER_RX_PIN, FINGER_TX_PIN);
Adafruit_Fingerprint finger(&fingerprintSerial);
LiquidCrystal_I2C lcd(0x27, 16, 2);
Adafruit_NeoPixel ring(RING_PIXELS, RING_PIN, NEO_GRB + NEO_KHZ800);
bool sensorReady = false;

void show(const char* line1, const char* line2 = "") { lcd.clear(); lcd.setCursor(0,0); lcd.print(line1); lcd.setCursor(0,1); lcd.print(line2); }
void ringColor(uint32_t color) { for (uint8_t i=0;i<RING_PIXELS;i++) ring.setPixelColor(i,color); ring.show(); }
void beep(uint16_t duration, uint16_t frequency=2200) { tone(BUZZER_PIN,frequency,duration); delay(duration+25); }
void requestedSignal() { beep(70,1800); }
void successSignal() { beep(90,2400); delay(40); beep(120,3000); }
void failureSignal() { beep(120,550); delay(55); beep(180,450); }
void idleState() { ringColor(ring.Color(0,12,35)); show("FINGUARD AI","READY"); }
void reply(const String& message) { Serial.println(message); }

uint32_t colorForName(const String& name) {
  if(name=="RED") return ring.Color(120,0,0); if(name=="ORANGE") return ring.Color(100,45,0);
  if(name=="YELLOW") return ring.Color(90,80,0); if(name=="GREEN") return ring.Color(0,80,10);
  if(name=="BLUE") return ring.Color(0,20,80); return ring.Color(0,12,35);
}
void handleDisplay(const String& command) {
  String rest=command.substring(8); int sp=rest.indexOf(' '); String requestId=sp<0?rest:rest.substring(0,sp);
  String payload=sp<0?"":rest.substring(sp+1); int first=payload.indexOf('|'); int second=first<0?-1:payload.indexOf('|',first+1);
  String line1=first<0?payload:payload.substring(0,first); String line2=first<0?"":(second<0?payload.substring(first+1):payload.substring(first+1,second));
  String color=second<0?"":payload.substring(second+1); show(line1.c_str(),line2.c_str()); ringColor(colorForName(color)); reply("DISPLAY_OK "+requestId);
}
bool waitForFinger(unsigned long timeoutMs) {
  unsigned long started=millis(); while(millis()-started<timeoutMs) { uint8_t result=finger.getImage(); if(result==FINGERPRINT_OK) return true; if(result==FINGERPRINT_NOFINGER) { delay(75); continue; } return false; } return false;
}
void failVerify(const String& requestId, const String& result) { ringColor(ring.Color(80,0,0)); show("ACCESS DENIED","TRY AGAIN"); failureSignal(); reply(result+" "+requestId); delay(1000); idleState(); }
void handleVerify(const String& requestId,uint16_t expectedId,const String& mode) {
  if(!sensorReady) { reply("HARDWARE_ERROR "+requestId); return; }
  ringColor(ring.Color(80,55,0)); if(mode=="STR") show("STR AUTH","PLACE FINGER"); else show("PLACE FINGER","VERIFY ACCESS"); requestedSignal(); reply("FINGER_REQUIRED "+requestId);
  if(!waitForFinger(VERIFY_TIMEOUT_MS)) { failVerify(requestId,"TIMEOUT"); return; }
  ringColor(ring.Color(0,20,80)); show("VERIFYING...","PLEASE WAIT"); reply("VERIFYING "+requestId);
  if(finger.image2Tz()!=FINGERPRINT_OK || finger.fingerFastSearch()!=FINGERPRINT_OK || finger.fingerID!=expectedId) { failVerify(requestId,"FINGER_FAILED"); return; }
  ringColor(ring.Color(0,80,10)); if(mode=="STR") show("STR APPROVED","AUTHORIZED"); else show("ACCESS GRANTED","WELCOME"); successSignal(); reply("FINGER_SUCCESS "+requestId+" "+String(finger.fingerID)); delay(1200); idleState();
}
void enrollmentFailed(const String& requestId) { ringColor(ring.Color(80,0,0)); show("ENROLL FAILED","TRY AGAIN"); failureSignal(); reply("ENROLL_FAILED "+requestId); delay(1000); idleState(); }
void handleEnroll(const String& requestId,uint16_t templateId) {
  if(!sensorReady) { reply("HARDWARE_ERROR "+requestId); return; }
  ringColor(ring.Color(0,20,80)); show("ENROLL FINGER","PLACE FINGER"); reply("FINGER_REQUIRED "+requestId);
  if(!waitForFinger(VERIFY_TIMEOUT_MS)||finger.image2Tz(1)!=FINGERPRINT_OK) { enrollmentFailed(requestId); return; }
  show("REMOVE FINGER",""); delay(1800); show("PLACE AGAIN","SAME FINGER");
  if(!waitForFinger(VERIFY_TIMEOUT_MS)||finger.image2Tz(2)!=FINGERPRINT_OK||finger.createModel()!=FINGERPRINT_OK||finger.storeModel(templateId)!=FINGERPRINT_OK) { enrollmentFailed(requestId); return; }
  ringColor(ring.Color(0,80,10)); show("ENROLL SUCCESS","TEMPLATE SAVED"); successSignal(); reply("ENROLL_SUCCESS "+requestId+" "+String(templateId)); delay(1200); idleState();
}
void handleCommand(String command) {
  command.trim(); if(command=="PING") { reply(sensorReady?"PONG":"HARDWARE_ERROR PING"); return; } if(command.startsWith("DISPLAY ")) { handleDisplay(command); return; }
  int first=command.indexOf(' '); if(first<0) { reply("HARDWARE_ERROR UNKNOWN"); return; } String verb=command.substring(0,first); String rest=command.substring(first+1); int second=rest.indexOf(' '); if(second<0) { reply("HARDWARE_ERROR UNKNOWN"); return; }
  String requestId=rest.substring(0,second); rest=rest.substring(second+1); int third=rest.indexOf(' '); String idValue=third<0?rest:rest.substring(0,third); uint16_t templateId=(uint16_t)idValue.toInt(); if(templateId==0) { reply("HARDWARE_ERROR "+requestId); return; }
  if(verb=="VERIFY"&&third>=0) handleVerify(requestId,templateId,rest.substring(third+1)); else if(verb=="ENROLL") handleEnroll(requestId,templateId); else reply("HARDWARE_ERROR "+requestId);
}
void setup() { pinMode(BUZZER_PIN,OUTPUT); Serial.begin(115200); fingerprintSerial.begin(57600); ring.begin(); ring.show(); lcd.init(); lcd.backlight(); show("FINGUARD AI","STARTING..."); finger.begin(57600); sensorReady=finger.verifyPassword(); if(!sensorReady) { ringColor(ring.Color(80,0,0)); show("SENSOR ERROR","CHECK WIRING"); } else idleState(); Serial.println("BOOT_READY"); }
void loop() { if(Serial.available()) handleCommand(Serial.readStringUntil('\n')); }
