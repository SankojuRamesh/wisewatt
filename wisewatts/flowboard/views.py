from django.shortcuts import render, HttpResponse
import subprocess
import sys
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from django.core.cache import cache         # 👈 add this
from datetime import timedelta  
from rest_framework import viewsets 
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from .models import Site, Tank, Pump, Sensor, TankReading, pumpReading
from .serializers import SiteSerializer, TankSerializer, PumpSerializer, SensorSerializer, TankReadingSerializer, pumpReadingSerializer
from .filters import SiteFilter, TankFilter, PumpFilter, SensorFilter, TankReadingFilter, pumpReadingFilter 
from django_filters.rest_framework import DjangoFilterBackend   

# ---------------------------

SAVE_INTERVAL = timedelta(minutes=1)  # how often to store in DB

@csrf_exempt
def sensor_post(request):
    """
    Accepts POST JSON from device and broadcasts to channels group "sensors".
    Also stores a reading in DB at most once per minute per sensor.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "invalid json", "detail": str(e)}, status=400)

    # --------- 1) broadcast to websockets (unchanged) ----------
    payload.setdefault("ts", timezone.now().isoformat())

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "sensors",  # group name
        {
            "type": "sensor.update",   # handler name on consumers
            "payload": payload
        }
    )
   
    # --------- 2) save to DB at most every 1 minute ----------
    # adjust this depending on how you identify the sensor in your payload
    sensor_id = payload.get("sensor_id", None)  
    
    if sensor_id is not None:
        _maybe_save_sensor_reading(sensor_id, payload)

    return JsonResponse({"ok": True})

def _maybe_save_sensor_reading(sensor_id, payload):
    """
    Store a reading in SensorReading table at most once per minute per sensor.
    Uses Django cache to remember last save time.
    """
    now = timezone.now()
    cache_key = f"sensor_last_save_{sensor_id}"
    last_save = cache.get(cache_key)

    if last_save is not None and now - last_save < SAVE_INTERVAL:
        # too soon, skip DB write
        return 
    try:
        
        tank = Tank.objects.get(pk=payload.get("tank_id"))
        # sensor = Sensor.objects.get(pk=sensor_id)
         
    except Sensor.DoesNotExist:
        # unknown sensor, you can log or just ignore
        return

    # distance_cm = payload.get("distance_cm")
    pump_on = payload.get("pump_on", False)
    # flow_rate = payload.get("pump_flow_lpm", 0) 
    
    # Sensor.objects.create(
    #     sensor=sensor,
    #     tank = tank,
    #     sensor_info=payload 
    # )

    TankReading.objects.create(
        tank=tank,
        water_level_cm=payload.get("water_level_cm", 0),
        water_level_perc=payload.get("water_level_perc", 0)
    )
    pump = Pump.objects.get( pk=payload.get("pump_id") )
    pumpReading.objects.create(
        pump=pump,  # assuming one pump per site 
        pump_on=pump_on
    )


    # remember last save time
    cache.set(cache_key, now, timeout=3600 * 24)  # 1 day timeout is fine

class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filterset_class = SiteFilter
    filter_backends = [DjangoFilterBackend]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
class TankViewSet(viewsets.ModelViewSet):
    queryset = Tank.objects.all()
    serializer_class = TankSerializer
    filterset_class = TankFilter
    filter_backends = [DjangoFilterBackend]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
class PumpViewSet(viewsets.ModelViewSet):
    queryset = Pump.objects.all()
    serializer_class = PumpSerializer
    filterset_class = PumpFilter
    filter_backends = [DjangoFilterBackend]
    parser_classes = [JSONParser, FormParser, MultiPartParser]


class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer
    filterset_class = SensorFilter
    filter_backends = [DjangoFilterBackend]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
# Additional API views can be added here as needed

class TankReadingViewSet(viewsets.ModelViewSet):
    queryset = TankReading.objects.all()
    serializer_class = TankReadingSerializer 
    filter_backends = [DjangoFilterBackend]
    filterset_class = TankReadingFilter
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    http_method_names = ['get' ]   # effectively read-only


class pumpReadingViewSet(viewsets.ModelViewSet):
    queryset = pumpReading.objects.all()
    serializer_class = pumpReadingSerializer 
    filter_backends = [DjangoFilterBackend]
    filterset_class = pumpReadingFilter
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    http_method_names = ['get' ]   # effectively read-only