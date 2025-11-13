/*
  ESP32 + A7670C — AT commands, sensor POST, pump PATCH
  AP portal to configure/save URLs
  Sends data every 2 minutes
  (Fixed UART conflicts — GSM and Modbus on separate serial ports)
*/

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <HardwareSerial.h>
#include <ModbusMaster.h>

// -------------------- PIN DEFINITIONS --------------------
#define MODBUS_RX 16      // RS485 RO -> ESP32 RX2
#define MODBUS_TX 17      // RS485 DI <- ESP32 TX2
#define DE_RE_PIN 4       // RS485 DE+RE control
#define PUMP_PIN 5        // Pump status input pin
#define MODEM_RX 26       // A7670C TX -> ESP RX
#define MODEM_TX 27       // A7670C RX <- ESP TX

// -------------------- OBJECTS --------------------
HardwareSerial SerialAT(1);     // GSM Modem (A7670C)
HardwareSerial ModbusSerial(2); // RS485 Modbus sensor
WebServer server(80);
Preferences prefs;
ModbusMaster node;

// -------------------- CONFIG --------------------
const char *apSsid = "wisewatt";
const char *apPass = "admin@123";

String apn = "airtelgprs.com";

String sensorUrl = "http://example.com/sensor";
String pumpUrl   = "http://example.com/pump";

const unsigned long SEND_INTERVAL = 120000UL; // 2 minutes
unsigned long lastSendMillis = 0;
volatile bool configSaved = false;

// -------------------- HELPERS --------------------
String normalizeUrl(const String &in) {
  String s = in;
  s.trim();
  if (s.length() == 0) return "";
  if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://" + s;
  return s;
}

void sendAT(const String &cmd, unsigned long timeout = 2000) {
  Serial.print("> "); Serial.println(cmd);
  SerialAT.println(cmd);
  unsigned long start = millis();
  while (millis() - start < timeout) {
    while (SerialAT.available()) Serial.write(SerialAT.read());
    server.handleClient();
  }
}

void flushSerialATShort() {
  delay(100);
  while (SerialAT.available()) Serial.write(SerialAT.read());
}

// -------------------- WEB UI --------------------
void handleRoot() {
  String html =
    "<!doctype html><html lang='en'>"
    "<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
    "<title>ESP32 URL Config</title><style>"
    "body{font-family:Arial,sans-serif;background:#f4f6f8;}"
    ".container{max-width:480px;margin:50px auto;background:#fff;padding:30px;border-radius:10px;box-shadow:0 4px 10px rgba(0,0,0,0.1);}"
    "h2{text-align:center;color:#333;}"
    "label{font-weight:bold;}"
    "input[type=text]{width:100%;padding:10px;margin:10px 0 20px 0;border:1px solid #ccc;border-radius:5px;}"
    "input[type=submit]{width:100%;padding:12px;background:#007bff;color:#fff;border:none;border-radius:5px;font-size:16px;cursor:pointer;}"
    "input[type=submit]:hover{background:#0056b3;}"
    "p{font-size:14px;color:#555;}"
    "</style></head><body>"
    "<div class='container'>"
    "<h2>Configure Server URLs</h2>"
    "<form method='POST' action='/save'>"
    "<label>Sensor URL:</label>"
    "<input type='text' name='sensor' value='" + sensorUrl + "' required>"
    "<label>Pump URL:</label>"
    "<input type='text' name='pump' value='" + pumpUrl + "' required>"
    "<input type='submit' value='Save & Apply'>"
    "</form>"
    "<p>Current Sensor URL: " + sensorUrl + "</p>"
    "<p>Current Pump URL: " + pumpUrl + "</p>"
    "<p>Device sends data every 2 minutes.</p>"
    "</div></body></html>";
  server.send(200, "text/html", html);
}

void handleSave() {
  if (!server.hasArg("sensor") || !server.hasArg("pump")) {
    server.send(400, "text/plain", "Missing fields");
    return;
  }
  sensorUrl = normalizeUrl(server.arg("sensor"));
  pumpUrl   = normalizeUrl(server.arg("pump"));

  prefs.putString("sensorUrl", sensorUrl);
  prefs.putString("pumpUrl", pumpUrl);
  configSaved = true;

  String resp = "<html><body><h3>Saved!</h3>"
                "<p>Sensor URL: " + sensorUrl + "<br>Pump URL: " + pumpUrl + "</p>"
                "<p>Applied immediately.</p></body></html>";
  server.send(200, "text/html", resp);
}

void startConfigPortal() {
  WiFi.mode(WIFI_AP);
  if (apPass && strlen(apPass) > 0) WiFi.softAP(apSsid, apPass);
  else WiFi.softAP(apSsid);
  Serial.print("AP started -> http://"); Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSave);
  server.begin();
}

// -------------------- MODEM --------------------
bool modemOpenSession() {
  sendAT("AT", 1000);
  sendAT("ATE0", 500);
  sendAT("AT+CPIN?", 1000);
  sendAT("AT+CREG?", 1000);
  sendAT("AT+CSQ", 1000);
  sendAT("AT+CGDCONT=1,\"IP\",\"" + apn + "\"", 1500);
  sendAT("AT+CGATT=1", 3000);
  sendAT("AT+NETOPEN", 8000);
  flushSerialATShort();
  sendAT("AT+HTTPINIT", 2000);
  sendAT("AT+HTTPPARA=\"CID\",1", 1000);
  return true;
}

void modemCloseSession() {
  sendAT("AT+HTTPTERM", 1000);
  sendAT("AT+NETCLOSE", 2000);
  sendAT("AT+CGATT=0", 1000);
}

// -------------------- MODBUS SENSOR --------------------
void preTransmission() { digitalWrite(DE_RE_PIN, HIGH); }
void postTransmission() { digitalWrite(DE_RE_PIN, LOW); }

int readSensor() {
  uint8_t result = node.readHoldingRegisters(0x0100, 1);
  if (result == node.ku8MBSuccess) return node.getResponseBuffer(0);
  Serial.print("Modbus error: "); Serial.println(result);
  return -1;
}

// -------------------- PAYLOAD BUILDERS --------------------
String buildSensorPayload(int sensorValue) {

  return "{\"sensor_id\":\"SENSOR001\",\"data\":{\"value\":" + String(sensorValue) + "}}";
}

String buildPumpPayload(bool status) {
  return "{\"status\":\"" + String(status ? "ON" : "OFF") + "\"}";
}

// -------------------- HTTP --------------------
void sendJsonPost(const String &url, const String &payload) {
  size_t len = payload.length();
  Serial.println("---- Sending ----");
  Serial.println("URL: " + url);
  Serial.println("Payload: " + payload);

  sendAT("AT+HTTPPARA=\"URL\",\"" + url + "\"", 2000);
  sendAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", 1000);
  sendAT("AT+HTTPDATA=" + String(len) + ",10000", 3000);
  delay(500);
  SerialAT.print(payload);
  delay(500);
  sendAT("AT+HTTPACTION=1", 15000); // POST
  sendAT("AT+HTTPREAD", 5000);
  Serial.println("---- Done ----");
}

// -------------------- SENSOR + PUMP COMBINE --------------------
void sendSensorAndPumpData() {
  int sensorVal = readSensor();
  if (sensorVal < 0) {
    Serial.println("Sensor read failed, using default 0");
    sensorVal = 0;
  }
  sendJsonPost(sensorUrl, buildSensorPayload(sensorVal));

  bool pumpStatus = digitalRead(PUMP_PIN) == HIGH;
  sendAT("AT+HTTPPARA=\"CUSTOMMETHOD\",\"PATCH\"", 1000);
  sendJsonPost(pumpUrl, buildPumpPayload(pumpStatus));
  sendAT("AT+HTTPPARA=\"CUSTOMMETHOD\",\"POST\"", 1000);  // restore POST
}

// -------------------- SETUP --------------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP32 + GSM Sensor & Pump API (Fixed UARTs)");

  pinMode(DE_RE_PIN, OUTPUT); digitalWrite(DE_RE_PIN, LOW);
  pinMode(PUMP_PIN, INPUT_PULLUP); // safer against floating

  // Modbus Init (RS485)
  ModbusSerial.begin(9600, SERIAL_8N1, MODBUS_RX, MODBUS_TX);
  node.begin(1, ModbusSerial);
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);

  // Preferences (saved URLs)
  prefs.begin("config", false);
  sensorUrl = prefs.getString("sensorUrl", sensorUrl);
  pumpUrl   = prefs.getString("pumpUrl", pumpUrl);

  // Wi-Fi config portal
  startConfigPortal();

  // GSM Modem Init
  SerialAT.begin(115200, SERIAL_8N1, MODEM_RX, MODEM_TX);
  modemOpenSession();

  lastSendMillis = millis() - SEND_INTERVAL;
}

// -------------------- LOOP --------------------
void loop() {
  server.handleClient();

  if (configSaved) {
    prefs.putString("sensorUrl", sensorUrl);
    prefs.putString("pumpUrl", pumpUrl);
    configSaved = false;
  }

  if (millis() - lastSendMillis >= SEND_INTERVAL) {
    lastSendMillis = millis();
    sendSensorAndPumpData();
  }

  while (SerialAT.available()) Serial.write(SerialAT.read());
}
