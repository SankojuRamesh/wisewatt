# device_post.py
import requests
import time
import json
from datetime import datetime
import   random  
SERVER = "http://localhost:8000/api/sensor-post/" 

def read_sensor():
    # replace with real sensor reading code
    destane = random.randint(1, 700)
    return {
        "sensor_id": "1",
        "site_id": "1",
        "tank_id": "1", 
        "pump_id": "1",
        "pump_name": "Pump One",
        "distance_cm": destane,
        'water_level_cm': 700 - destane,
        'water_level_perc':  f"{round((700 - destane) / 7, 2)}%",
        "pump_flow_lpm": random.randint(0, 10),
        "pump_on": True,
        "battery": 3.75,
        "ts": datetime.utcnow().isoformat() + "Z"
    }

while True:
    data = read_sensor()
    try:
        r = requests.post(SERVER, json=data, timeout=5)
        print("posted", r.status_code, r.text)
    except Exception as e:
        print("post error", e)
    time.sleep(1)  # send every second
