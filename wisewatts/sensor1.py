# device_post.py
import requests
import time
import json
from datetime import datetime
import random

SERVER = "http://13.210.103.10:8000/api/sensor-post/"

# --- Configuration / defaults (edit these as needed) ---
CFG_PUMP1_ID = "1"
CFG_PUMP1_NAME = "Pump One"
CFG_PUMP2_ID = "2"
CFG_PUMP2_NAME = "Pump Two"
SENSOR_MAX_DISTANCE_CM = 700  # used to calculate water level

def read_sensor():
    """
    Simulate sensor readings and build the JSON payload including a 'pumps' array.
    Replace the random parts with real sensor/pump readings as required.
    """
    # simulated distance reading
    distance_cm = random.randint(1, SENSOR_MAX_DISTANCE_CM)

    # simulated pump states and flows (replace with real logic)
    pump1_on = random.choice([True, False])
    pump2_on = random.choice([True, False])
    pump1_flow_lpm = random.randint(0, 10) if pump1_on else 0
    pump2_flow_lpm = random.randint(0, 10) if pump2_on else 0

    # Construct pumps array
    pumps = [
        {
            "pump_id": CFG_PUMP1_ID,
            "pump_name": CFG_PUMP1_NAME,
            "pump_on": pump1_on,
            "pump_flow_lpm": pump1_flow_lpm
        },
        {
            "pump_id": CFG_PUMP2_ID,
            "pump_name": CFG_PUMP2_NAME,
            "pump_on": pump2_on,
            "pump_flow_lpm": pump2_flow_lpm
        }
    ]

    # remaining fields
    battery = round(3.5 + random.random() * 0.5, 2)  # example battery voltage
    ts = datetime.utcnow().isoformat() + "Z"

    payload = {
        "sensor_id": "1",
        "site_id": "1",
        "tank_id": "1",
        # top-level pump info kept for backward compatibility (optional)
        "pump_id": CFG_PUMP1_ID,
        "pump_name": CFG_PUMP1_NAME,
        "pump_on": pump1_on,
        "pump_flow_lpm": pump1_flow_lpm,
        # pumps array (new)
        "pumps": pumps,
        "distance_cm": distance_cm,
        "water_level_cm": SENSOR_MAX_DISTANCE_CM - distance_cm,
        "water_level_perc": f"{round((SENSOR_MAX_DISTANCE_CM - distance_cm) / (SENSOR_MAX_DISTANCE_CM/100), 2)}%",
        "battery": battery,
        "ts": ts
    }

    return payload

def main():
    while True:
        data = read_sensor()
        try:
            r = requests.post(SERVER, json=data, timeout=5)
            print("posted", r.status_code, r.text)
            # print the json we sent (pretty) for debugging
            print("sent payload:", json.dumps(data, indent=2))
        except Exception as e:
            print("post error", e)
        time.sleep(1)  # send every second

if __name__ == "__main__":
    main()
