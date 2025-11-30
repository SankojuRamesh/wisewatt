/*
  ESP32 + A7670C: Modbus -> GSM POST (full payload)
  - Single configurable sensorUrl via AP portal
  - Sends data every 5 seconds (measured after each send completes)
  - Modem UART1: MODEM_RX=26 MODEM_TX=27
*/

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <HardwareSerial.h>
#include <ModbusMaster.h>
#include <time.h>

// -------------------- PIN DEFINITIONS --------------------
#define MODBUS_RX 16      // RS485 RO -> ESP32 RX2
#define MODBUS_TX 17      // RS485 DI <- ESP32 TX2
#define DE_RE_PIN 4       // RS485 DE+RE control
#define PUMP_PIN 5        // unused, kept for compatibility
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

String apn = "airtelgprs.com";                    // <-- set your APN
String sensorUrl = "http://example.com/sensor";   // <-- default endpoint

// Send interval = 5 seconds (measured AFTER each send completes)
const unsigned long SEND_INTERVAL = 6000UL;
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

// send AT and forward response to USB Serial, while handling web server
void sendAT(const String &cmd, unsigned long timeout = 2000) {
  Serial.print("> "); Serial.println(cmd);
  SerialAT.println(cmd);
  unsigned long start = millis();
  while (millis() - start < timeout) {
    while (SerialAT.available()) Serial.write(SerialAT.read());
    server.handleClient();
  }
}

// small flush printer
void flushSerialATShort() {
  delay(100);
  while (SerialAT.available()) Serial.write(SerialAT.read());
}

// -------------------- WEB UI --------------------
void handleRoot() {
  String html =
    "<!doctype html><html lang='en'>"
    "<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
    "<title>ESP32 Sensor URL Config</title><style>"
    "body{font-family:Arial,sans-serif;background:#f4f6f8;} "
    ".container{max-width:480px;margin:50px auto;background:#fff;padding:30px;border-radius:10px;box-shadow:0 4px 10px rgba(0,0,0,0.1);} "
    "h2{text-align:center;color:#333;} label{font-weight:bold;} "
    "input[type=text]{width:100%;padding:10px;margin:10px 0 20px 0;border:1px solid #ccc;border-radius:5px;} "
    "input[type=submit]{width:100%;padding:12px;background:#007bff;color:#fff;border:none;border-radius:5px;font-size:16px;cursor:pointer;} "
    "input[type=submit]:hover{background:#0056b3;} p{font-size:14px;color:#555;} "
    "</style></head><body>"
    "<div class='container'>"
    "<h2>Configure Sensor Server URL</h2>"
    "<form method='POST' action='/save'>"
    "<label>Sensor URL:</label>"
    "<input type='text' name='sensor' value='" + sensorUrl + "' required>"
    "<input type='submit' value='Save & Apply'>"
    "</form>"
    "<p>Current Sensor URL: " + sensorUrl + "</p>"
    "<p>Device sends data every 5 seconds (measured after each send completes).</p>"
    "</div></body></html>";
  server.send(200, "text/html", html);
}

void handleSave() {
  if (!server.hasArg("sensor")) {
    server.send(400, "text/plain", "Missing sensor field");
    return;
  }
  sensorUrl = normalizeUrl(server.arg("sensor"));
  prefs.putString("sensorUrl", sensorUrl);
  configSaved = true;

  String resp = "<html><body><h3>Saved!</h3>"
                "<p>Sensor URL: " + sensorUrl + "</p>"
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

// -------------------- MODEM SESSION --------------------
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

// -------------------- PAYLOAD BUILDER (full static fields except distance_cm) --------------------
String buildFullPayload(int distance_cm) {
  int water_level_cm = 700 - distance_cm;
  float perc = (float)water_level_cm / 7.0f;
  char percStr[16];
  snprintf(percStr, sizeof(percStr), "%.2f%%", perc);

  // Timestamp ISO8601 UTC
  time_t now = time(nullptr);
  struct tm timeinfo;
  if (gmtime_r(&now, &timeinfo) == nullptr) {
    strcpy(percStr, "0.00%");
  }
  char ts[40];
  strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);

  int pump_flow_lpm = random(0, 11); // static random each call
  const float battery = 3.75f;
  const char *pump_name = "Pump One";

  String json = "{";
  json += "\"sensor_id\":\"1\",";
  json += "\"site_id\":\"1\",";
  json += "\"tank_id\":\"1\",";
  json += "\"pump_id\":\"1\",";
  json += "\"pump_name\":\"" + String(pump_name) + "\",";
  json += "\"distance_cm\":" + String(distance_cm) + ",";
  json += "\"water_level_cm\":" + String(water_level_cm) + ",";
  json += "\"water_level_perc\":\"" + String(percStr) + "\",";
  json += "\"pump_flow_lpm\":" + String(pump_flow_lpm) + ",";
  json += "\"pump_on\":true,";
  json += "\"battery\":" + String(battery, 2) + ",";
  json += "\"ts\":\"" + String(ts) + "\"";
  json += "}";
  return json;
}

// -------------------- HTTP (simple AT+HTTP flow) --------------------
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

// -------------------- SENDER --------------------
void sendSensorData() {
  int sensorVal = readSensor();
  if (sensorVal < 0) {
    Serial.println("Sensor read failed, using default 0");
    sensorVal = 0;
  }
  String payload = buildFullPayload(sensorVal);
  sendJsonPost(sensorUrl, payload);
}

// -------------------- SETUP --------------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP32 + A7670C: Modbus -> GSM POST (full payload)");

  pinMode(DE_RE_PIN, OUTPUT);
  digitalWrite(DE_RE_PIN, LOW);
  pinMode(PUMP_PIN, INPUT_PULLUP);

  // Modbus init (unchanged)
  ModbusSerial.begin(9600, SERIAL_8N1, MODBUS_RX, MODBUS_TX);
  node.begin(1, ModbusSerial);
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);

  // Preferences
  prefs.begin("config", false);
  sensorUrl = prefs.getString("sensorUrl", sensorUrl);

  // Web config portal
  startConfigPortal();

  // Modem init
  SerialAT.begin(115200, SERIAL_8N1, MODEM_RX, MODEM_TX);
  modemOpenSession();

  // NTP time (best effort)
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  // random seed
  randomSeed(analogRead(34) ^ millis());

  // send first immediately
  lastSendMillis = 0;
}

// -------------------- LOOP --------------------
void loop() {
  server.handleClient();

  if (configSaved) {
    prefs.putString("sensorUrl", sensorUrl);
    configSaved = false;
  }

  if (millis() - lastSendMillis >= SEND_INTERVAL) {
    // perform send (blocking) then record send time AFTER it completes
    sendSensorData();
    lastSendMillis = millis(); // <-- moved here so interval is measured after send
  }

  while (SerialAT.available()) Serial.write(SerialAT.read());
}
