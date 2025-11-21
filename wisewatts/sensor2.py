# device_post.py
import requests
import time
import json
from datetime import datetime
import   random  
SERVER = "http://13.210.103.10:8000/api/sensor-post/" 

def read_sensor():
    # replace with real sensor reading code
    destane = random.randint(1, 700)
    return {
        "sensor_id": "2",
        "site_id": "1",
        "tank_id": "1", 
        "pump_id": "2",
        "pump_name": "Pump Two",
        "distance_cm": destane,
        'water_level_cm': 700 - destane,
        'water_level_perc':    round((700 - destane) / 7, 2) ,
        "pump_flow_lpm": random.randint(0, 10),
        "pump_on": False,
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
