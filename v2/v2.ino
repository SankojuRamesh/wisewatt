#include <Arduino.h>
#include <ModbusMaster.h>

// === Pins ===
const int DE_RE_PIN = 4;
const int RX_PIN    = 16;
const int TX_PIN    = 17;
const uint32_t BAUD = 9600;

ModbusMaster node;

// -------------------------------------------------------------------
// DE/RE TRIGGER CALLBACKS
// -------------------------------------------------------------------
void preTransmission()  { digitalWrite(DE_RE_PIN, HIGH); }
void postTransmission() { digitalWrite(DE_RE_PIN, LOW);  }

// -------------------------------------------------------------------
// FUNCTION: Read One Holding Register
// Returns true on success, false on error.
// Out value is returned in 'outValue'
// -------------------------------------------------------------------
bool readHoldingRegister(uint16_t regAddress, uint16_t &outValue) {
  uint8_t result = node.readHoldingRegisters(regAddress, 1);

  if (result == node.ku8MBSuccess) {
    outValue = node.getResponseBuffer(0);
    return true;
  } else {
    Serial.print("Modbus error: ");
    Serial.println(result);
    return false;
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.println("\nESP32 Modbus RS485 with Function");

  pinMode(DE_RE_PIN, OUTPUT);
  digitalWrite(DE_RE_PIN, LOW);

  Serial2.begin(BAUD, SERIAL_8N1, RX_PIN, TX_PIN);
  delay(50);

  node.begin(1, Serial2);
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);

  Serial.println("Setup complete.");
}

void loop() {
  uint16_t value = 0;

  // USE THE FUNCTION HERE
  if (readHoldingRegister(0x0101, value)) {
    Serial.print("Distance: ");
    Serial.println(value);
  }

  delay(1000);
}
