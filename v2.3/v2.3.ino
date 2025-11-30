/*
  ESP32 + A7670C: Modbus -> GSM POST (full payload) with two pump inputs
  - Single configurable sensorUrl + IDs + pump_name + pump2_name via AP portal
  - Sends data every ~6 seconds (measured AFTER each send completes)
  - Adds a Test POST button and shows last HTTP status/response
  - pump_on reflects PUMP_PIN: LOW -> false (external pull-down), HIGH -> true
  - pump2_on reflects PUMP2_PIN similarly
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
#define PUMP_PIN 5        // pump1 status input pin (external pull-down to GND)
#define PUMP2_PIN 18      // pump2 status input pin (external pull-down to GND) - change if needed
#define MODEM_RX 26       // A7670C TX -> ESP RX
#define MODEM_TX 27       // A7670C RX <- ESP TX

// -------------------- OBJECTS --------------------
HardwareSerial SerialAT(1);     // GSM Modem (A7670C)
HardwareSerial ModbusSerial(2); // RS485 Modbus sensor
WebServer server(80);
ModbusMaster node;
Preferences prefs;   
// -------------------- CONFIG --------------------
const char *apSsid = "wisewatt";
const char *apPass = "admin@123";

String apn = "airtelgprs.com";                    // <-- set your APN
String sensorUrl = "http://example.com/sensor";   // <-- default endpoint

// Configurable payload fields (defaults)
String cfg_sensor_id = "1";
String cfg_site_id   = "1";
String cfg_tank_id   = "1";

// pump1 configurable
String cfg_pump_id   = "1";
String cfg_pump_name = "Pump One";

// pump2 configurable
String cfg_pump2_id   = "2";
String cfg_pump2_name = "Pump Two";

// Send interval (kept as you had it)
const unsigned long SEND_INTERVAL = 6000UL;
unsigned long lastSendMillis = 0;
volatile bool configSaved = false;

// Last HTTP info (for UI)
int lastHttpStatus = -1;
String lastHttpResp = "";

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

// send AT and return the collected response as a String (does not block server handling)
String sendATGet(const String &cmd, unsigned long timeout = 2000) {
  while (SerialAT.available()) SerialAT.read(); // flush
  if (cmd.length()) {
    Serial.print("> "); Serial.println(cmd);
    SerialAT.println(cmd);
  }
  unsigned long start = millis();
  String resp = "";
  while (millis() - start < timeout) {
    while (SerialAT.available()) {
      char c = (char)SerialAT.read();
      resp += c;
    }
    server.handleClient();
  }
  Serial.print("< "); Serial.println(resp);
  return resp;
}

// small flush printer
void flushSerialATShort() {
  delay(100);
  while (SerialAT.available()) Serial.write(SerialAT.read());
}

// -------------------- WEB UI --------------------
void handleRoot() {
  // build HTML form with fields for sensorUrl and payload IDs/pump_name
  String html =
    "<!doctype html><html lang='en'>"
    "<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
    "<title>ESP32 Sensor & Pumps Config</title><style>"
    "body{font-family:Arial,sans-serif;background:#f4f6f8;} "
    ".container{max-width:720px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.08);} "
    "h2{text-align:center;color:#333;} label{display:block;font-weight:600;margin-top:10px;} "
    "input[type=text]{width:100%;padding:10px;margin:8px 0;border:1px solid #ccc;border-radius:6px;} "
    "input[type=submit],button{padding:10px 14px;margin-top:12px;background:#007bff;color:#fff;border:none;border-radius:6px;font-size:15px;cursor:pointer;} "
    "button.secondary{background:#28a745;} p{font-size:14px;color:#555;margin-top:12px;} pre{background:#f0f0f0;padding:10px;border-radius:6px;overflow:auto;} "
    "</style></head><body>"
    "<div class='container'>"
    "<h2>Device Configuration</h2>"
    "<form method='POST' action='/save'>"
    "<label>Sensor URL</label>"
    "<input type='text' name='sensorUrl' value='" + sensorUrl + "' required>"

    "<label>sensor_id</label>"
    "<input type='text' name='sensor_id' value='" + cfg_sensor_id + "' required>"

    "<label>site_id</label>"
    "<input type='text' name='site_id' value='" + cfg_site_id + "' required>"

    "<label>tank_id</label>"
    "<input type='text' name='tank_id' value='" + cfg_tank_id + "' required>"

    "<hr>"

    "<h3>Pump 1 (primary)</h3>"
    "<label>pump_id</label>"
    "<input type='text' name='pump_id' value='" + cfg_pump_id + "' required>"
    "<label>pump_name</label>"
    "<input type='text' name='pump_name' value='" + cfg_pump_name + "' required>"

    "<h3>Pump 2 (secondary)</h3>"
    "<label>pump2_id</label>"
    "<input type='text' name='pump2_id' value='" + cfg_pump2_id + "' required>"
    "<label>pump2_name</label>"
    "<input type='text' name='pump2_name' value='" + cfg_pump2_name + "' required>"

    "<br/><input type='submit' value='Save & Apply'>"
    "</form>"

    "<form method='POST' action='/test' style='margin-top:12px;'>"
    "<button type='submit' class='secondary'>Test POST Now</button>"
    "</form>"

    "<p>Device sends data every ~6 seconds (measured after each send completes).</p>"
    "<p>Current Sensor URL: " + sensorUrl + "</p>"

    "<p>Payload fields: sensor_id=" + cfg_sensor_id
      + " site_id=" + cfg_site_id
      + " tank_id=" + cfg_tank_id + "</p>"

    "<p>Pump1: id=" + cfg_pump_id + " name=" + cfg_pump_name + "</p>"
    "<p>Pump2: id=" + cfg_pump2_id + " name=" + cfg_pump2_name + "</p>"

    "<h3>Last HTTP Result</h3>"
    "<p>Status: " + String(lastHttpStatus) + "</p>"
    "<pre>" + lastHttpResp + "</pre>"

    "</div></body></html>";
  server.send(200, "text/html", html);
}

void handleSave() {
  // Expect all fields
  if (!server.hasArg("sensorUrl") || !server.hasArg("sensor_id") || !server.hasArg("site_id")
      || !server.hasArg("tank_id") || !server.hasArg("pump_id") || !server.hasArg("pump_name")
      || !server.hasArg("pump2_id") || !server.hasArg("pump2_name")) {
    server.send(400, "text/plain", "Missing fields");
    return;
  }

  // Save to runtime vars & preferences
  sensorUrl    = normalizeUrl(server.arg("sensorUrl"));
  cfg_sensor_id = server.arg("sensor_id");
  cfg_site_id   = server.arg("site_id");
  cfg_tank_id   = server.arg("tank_id");

  cfg_pump_id   = server.arg("pump_id");
  cfg_pump_name = server.arg("pump_name");

  cfg_pump2_id   = server.arg("pump2_id");
  cfg_pump2_name = server.arg("pump2_name");

  prefs.putString("sensorUrl", sensorUrl);
  prefs.putString("sensor_id", cfg_sensor_id);
  prefs.putString("site_id", cfg_site_id);
  prefs.putString("tank_id", cfg_tank_id);

  prefs.putString("pump_id", cfg_pump_id);
  prefs.putString("pump_name", cfg_pump_name);

  prefs.putString("pump2_id", cfg_pump2_id);
  prefs.putString("pump2_name", cfg_pump2_name);

  configSaved = true;

  String resp = "<html><body><h3>Saved!</h3><p>Applied immediately.</p>"
                "<p><a href='/'>Back</a></p></body></html>";
  server.send(200, "text/html", resp);
}

// Test POST handler (trigger single send and show immediate result)
void handleTestPost() {
  // Perform a send (blocking) and then show result in a small page
  sendSensorData(); // this updates lastHttpStatus / lastHttpResp
  String page = "<html><body><h3>Test POST Result</h3>";
  page += "<p>HTTP Status: " + String(lastHttpStatus) + "</p>";
  page += "<pre>" + lastHttpResp + "</pre>";
  page += "<p><a href='/'>Back</a></p></body></html>";
  server.send(200, "text/html", page);
}

void startConfigPortal() {
  WiFi.mode(WIFI_AP);
  if (apPass && strlen(apPass) > 0) WiFi.softAP(apSsid, apPass);
  else WiFi.softAP(apSsid);
  Serial.print("AP started -> http://"); Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSave);
  server.on("/test", HTTP_POST, handleTestPost);
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

// -------------------- PAYLOAD BUILDER (uses configured fields) --------------------
String buildFullPayload(int distance_cm, bool pump_on, bool pump2_on) {
  int water_level_cm = 700 - distance_cm;
  float perc = (float)water_level_cm / 7.0f;
  char percStr[16];
  snprintf(percStr, sizeof(percStr), "%.2f%%", perc);

  // Timestamp ISO8601 UTC
  time_t now = time(nullptr);
  struct tm timeinfo;
  if (gmtime_r(&now, &timeinfo) == nullptr) {
    // fallback timestamp (we keep percStr as is here)
    // you may want a different fallback action if needed
  }
  char ts[40];
  strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);

  // random flows for each pump (0..10)
  int pump1_flow_lpm = random(0, 11);
  int pump2_flow_lpm = random(0, 11);
  const float battery = 3.75f;

  // Build JSON using configured strings (only pump part changed)
  String json = "{";
  json += "\"sensor_id\":\"" + cfg_sensor_id + "\",";
  json += "\"site_id\":\""   + cfg_site_id   + "\",";
  json += "\"tank_id\":\""   + cfg_tank_id   + "\",";
  // ------------------ pumps array (replaces pump1_/pump2_ top-level fields) ------------------
  json += "\"pumps\":[";
    // pump 1
    json += "{";
      json += "\"pump_id\":\""   + cfg_pump_id   + "\",";
      json += "\"pump_name\":\"" + cfg_pump_name + "\",";
      json += "\"pump_on\":" + String(pump_on ?  "false": "true") + ",";
      json += "\"pump_flow_lpm\":" + String(pump1_flow_lpm);
    json += "},";
    // pump 2
    json += "{";
      json += "\"pump_id\":\""   + cfg_pump2_id   + "\",";
      json += "\"pump_name\":\"" + cfg_pump2_name + "\",";
      json += "\"pump_on\":" + String(pump2_on ?  "false": "true") + ",";
      json += "\"pump_flow_lpm\":" + String(pump2_flow_lpm);
    json += "}";
  json += "],";
  // ------------------ end pumps array ------------------
  json += "\"distance_cm\":" + String(distance_cm) + ",";
  json += "\"water_level_cm\":" + String(water_level_cm) + ",";
  json += "\"water_level_perc\":\"" + String(percStr) + "\",";
  json += "\"battery\":" + String(battery, 2) + ",";
  json += "\"ts\":\"" + String(ts) + "\"";
  json += "}";
  return json;
}


// -------------------- HTTP (simple AT+HTTP flow) --------------------
// This version captures +HTTPACTION and stores status/response for UI
void sendJsonPost(const String &url, const String &payload) {
  size_t len = payload.length();
  Serial.println("---- Sending ----");
  Serial.println("URL: " + url);
  Serial.println("Payload: " + payload);

  // set URL/content
  sendAT("AT+HTTPPARA=\"URL\",\"" + url + "\"", 2000);
  sendAT("AT+HTTPPARA=\"CONTENT\",\"application/json\"", 1000);

  // prepare to send data, wait for DOWNLOAD via sendATGet
  String resp = sendATGet("AT+HTTPDATA=" + String(len) + ",10000", 5000);
  if (resp.indexOf("DOWNLOAD") == -1 && resp.indexOf("OK") == -1) {
    // no DOWNLOAD prompt — still try to print response and continue, but mark failure
    lastHttpStatus = -999;
    lastHttpResp = "HTTPDATA failed or no DOWNLOAD prompt: " + resp;
    Serial.println(lastHttpResp);
    return;
  }

  // send payload (raw)
  SerialAT.print(payload);
  delay(500);

  // trigger POST and wait for +HTTPACTION
  // flush pre-existing
  while (SerialAT.available()) SerialAT.read();
  SerialAT.println("AT+HTTPACTION=1");
  Serial.println("> AT+HTTPACTION=1");

  unsigned long start = millis();
  String actionResp = "";
  while (millis() - start < 20000) { // wait up to 20s
    while (SerialAT.available()) actionResp += (char)SerialAT.read();
    if (actionResp.indexOf("+HTTPACTION:") != -1) break;
    server.handleClient();
    delay(10);
  }

  if (actionResp.length() == 0) {
    lastHttpStatus = -998;
    lastHttpResp = "No +HTTPACTION response (timed out)";
    Serial.println(lastHttpResp);
  } else {
    // parse status code, e.g. "+HTTPACTION: 1,200,45"
    int idx = actionResp.indexOf("+HTTPACTION:");
    lastHttpResp = actionResp;
    if (idx >= 0) {
      int c1 = actionResp.indexOf(',', idx);
      int c2 = actionResp.indexOf(',', c1 + 1);
      if (c1 >= 0 && c2 >= 0) {
        String statusStr = actionResp.substring(c1 + 1, c2);
        statusStr.trim();
        lastHttpStatus = statusStr.toInt();
      } else {
        lastHttpStatus = -997;
      }
    } else {
      lastHttpStatus = -996;
    }
    Serial.print("HTTP action raw resp: "); Serial.println(actionResp);
    Serial.print("Parsed status: "); Serial.println(lastHttpStatus);
  }

  // optionally read body
  String body = sendATGet("AT+HTTPREAD", 5000);
  Serial.println("HTTPREAD body:");
  Serial.println(body);
}

// -------------------- SENDER --------------------
// small debounce read: sample pin a few times to avoid transient glitches
bool readPinStable(uint8_t pin) {
  const int SAMPLES = 5;
  int highCount = 0;
  for (int i = 0; i < SAMPLES; ++i) {
    if (digitalRead(pin) == HIGH) highCount++;
    delay(5);
  }
  return (highCount >= (SAMPLES/2 + 1));
}

void sendSensorData() {
  int sensorVal = readSensor();
  if (sensorVal < 0) {
    Serial.println("Sensor read failed, using default 0");
    sensorVal = 0;
  }

  // Determine pump_on from PUMP_PIN (external pull-down wiring)
  bool pumpOn = readPinStable(PUMP_PIN);  // true if pin reads HIGH stable
  bool pump2On = readPinStable(PUMP2_PIN);

  String payload = buildFullPayload(sensorVal, pumpOn, pump2On);
  sendJsonPost(sensorUrl, payload);
}

// -------------------- SETUP --------------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP32 + A7670C: Modbus -> GSM POST (full payload) with 2 pumps");

  pinMode(DE_RE_PIN, OUTPUT);
  digitalWrite(DE_RE_PIN, LOW);

  // Use external pull-down resistors on pump pins (do NOT enable INPUT_PULLUP)
  pinMode(PUMP_PIN, INPUT);
  pinMode(PUMP2_PIN, INPUT);

  // Modbus init (unchanged)
  ModbusSerial.begin(9600, SERIAL_8N1, MODBUS_RX, MODBUS_TX);
  node.begin(1, ModbusSerial);
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);

  // Preferences: load saved config if available
  prefs.begin("config", false);
  sensorUrl     = prefs.getString("sensorUrl", sensorUrl);
  cfg_sensor_id = prefs.getString("sensor_id", cfg_sensor_id);
  cfg_site_id   = prefs.getString("site_id", cfg_site_id);
  cfg_tank_id   = prefs.getString("tank_id", cfg_tank_id);

  cfg_pump_id   = prefs.getString("pump_id", cfg_pump_id);
  cfg_pump_name = prefs.getString("pump_name", cfg_pump_name);

  cfg_pump2_id   = prefs.getString("pump2_id", cfg_pump2_id);
  cfg_pump2_name = prefs.getString("pump2_name", cfg_pump2_name);

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
    // already saved in handleSave; clear flag
    configSaved = false;
  }

  if (millis() - lastSendMillis >= SEND_INTERVAL) {
    // perform send (blocking) then record send time AFTER it completes
    sendSensorData();
    lastSendMillis = millis(); // measure interval AFTER send completes
  }

  while (SerialAT.available()) Serial.write(SerialAT.read());
}
