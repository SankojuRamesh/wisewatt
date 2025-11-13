from django.shortcuts import render, HttpResponse
import subprocess
import sys
# Create your views here.
# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from .models import (
    User, Site, UserDevice, Tank, Pump,
    TankMeasurement, PumpMeasurement, PumpRunEvent, SensorLog, sensore_data
)
from .serializers import (
    UserSerializer, SiteSerializer, UserDeviceSerializer, TankSerializer, PumpSerializer,
    TankMeasurementSerializer, PumpMeasurementSerializer, PumpRunEventSerializer, SensorLogSerializer,
    MultiSiteIngestSerializer, sensore_dataSerializer
)
from django.shortcuts import get_object_or_404


# ---------------------------
# ViewSets for CRUD (optional)
# ---------------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class SiteViewSet(viewsets.ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer


class UserDeviceViewSet(viewsets.ModelViewSet):
    queryset = UserDevice.objects.all()
    serializer_class = UserDeviceSerializer


class TankViewSet(viewsets.ModelViewSet):
    queryset = Tank.objects.all()
    serializer_class = TankSerializer


class PumpViewSet(viewsets.ModelViewSet):
    queryset = Pump.objects.all()
    serializer_class = PumpSerializer


class TankMeasurementViewSet(viewsets.ModelViewSet):
    queryset = TankMeasurement.objects.all().order_by('-timestamp')
    serializer_class = TankMeasurementSerializer


class PumpMeasurementViewSet(viewsets.ModelViewSet):
    queryset = PumpMeasurement.objects.all().order_by('-timestamp')
    serializer_class = PumpMeasurementSerializer


class PumpRunEventViewSet(viewsets.ModelViewSet):
    queryset = PumpRunEvent.objects.all().order_by('-start_time')
    serializer_class = PumpRunEventSerializer


class SensorLogViewSet(viewsets.ModelViewSet):
    queryset = SensorLog.objects.all().order_by('-timestamp')
    serializer_class = SensorLogSerializer


# ---------------------------
# Ingest API
# ---------------------------

def install(request):
    subprocess.check_call([sys.executable, "manage.py", "collectstatic", "--noinput"])
    return HttpResponse( "FlowBoard is installed and running." )
@api_view(['POST'])
@transaction.atomic
def ingest_data(request):
    """
    POST payload example:
    {
      "sites": [
        {
          "site_code": "SITE001",
          "name": "Pumpstation A",
          "device_id": "DEV123",
          "tank": {
            "equipment_id": "TANK-A1",
            "total_height_mm": 3000,
            "distance_mm": 1200
          },
          "pumps": [
            {"pump_id": "PUMP-A1", "status": "ON"},
            {"pump_id": "PUMP-A2", "status": "OFF"}
          ],
          "timestamp": "2025-11-11T12:01:00Z",
          "raw": {...}
        },
        ...
      ]
    }
    """
    serializer = MultiSiteIngestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data
    results = []

    for s in payload.get("sites", []):
        site_code = s["site_code"]
        site_name = s.get("name") or site_code
        device_id = s.get("device_id")
        ts = s.get("timestamp") or timezone.now()
        raw_payload = s.get("raw", s)

        # Get or create site
        site, _ = Site.objects.get_or_create(site_code=site_code, defaults={
            "name": site_name
        })
        # update name if changed
        if site.name != site_name:
            site.name = site_name
            site.save(update_fields=["name"])

        # device (optional)
        device = None
        if device_id:
            device, _ = UserDevice.objects.get_or_create(device_id=device_id, defaults={
                "site": site,
                "user": site.user if hasattr(site, 'user') and site.user else None
            })

        # Tank handling
        tank_data = s.get("tank")
        tank = None
        if tank_data:
            equipment_id = tank_data.get("equipment_id") or None
            total_height = tank_data.get("total_height_mm")
            # find by equipment_id and site, else create new tank
            if equipment_id:
                tank, created = Tank.objects.get_or_create(
                    site=site, equipment_id=equipment_id,
                    defaults={"total_height_mm": total_height}
                )
                if not created and tank.total_height_mm != total_height:
                    tank.total_height_mm = total_height
                    tank.save(update_fields=["total_height_mm"])
            else:
                # fallback: create an unnamed tank
                tank = Tank.objects.create(site=site, total_height_mm=total_height)

            distance = tank_data.get("distance_mm")
            # create TankMeasurement
            tm = TankMeasurement.objects.create(
                site=site,
                tank=tank,
                device=device, 
                distance_mm=distance,
                raw_payload=raw_payload,
                pump_status_snapshot={p["pump_id"]: p["status"] for p in s.get("pumps", [])} if s.get("pumps") else None
            )

        # Pump handling (create or update pumps, and write PumpMeasurement)
        pumps = s.get("pumps") or []
        for p in pumps:
            pid = p["pump_id"]
            status = p["status"]
            pump_obj, _ = Pump.objects.get_or_create(site=site, pump_id=pid, defaults={"tank": tank})
            # create PumpMeasurement row
            pm = PumpMeasurement.objects.create(
                site=site,
                pump=pump_obj,
                device=device,
                timestamp=ts,
                status=status,
                raw_payload=raw_payload
            )

            # Detect transitions for run events
            # Get last measurement for this pump (excluding this new row) - use ordering by timestamp desc
            last_pm = PumpMeasurement.objects.filter(pump=pump_obj).exclude(pk=pm.pk).order_by('-timestamp').first()

            last_status = last_pm.status if last_pm else None

            # If state changed and new state is ON -> create PumpRunEvent start
            if last_status != status:
                if status == "ON":
                    # create run event with start_time
                    PumpRunEvent.objects.create(
                        pump=pump_obj,
                        site=site,
                        start_time=ts
                    )
                elif status == "OFF":
                    # find last open run event (no stop_time) and close it
                    open_run = PumpRunEvent.objects.filter(pump=pump_obj, stop_time__isnull=True).order_by('-start_time').first()
                    if open_run:
                        open_run.stop_time = ts
                        # duration will be auto-calculated in model.save()
                        open_run.save()

        # Save raw payload (SensorLog) for this site/device/timestamp
        SensorLog.objects.create(site=site, device=device, payload=raw_payload, timestamp=ts)
        results.append({"site_code": site.site_code, "tank_measurement_id": tm.id if tank_data else None})

    return Response({"status": "ok", "results": results}, status=status.HTTP_201_CREATED)
class sensore_viewset(viewsets.ModelViewSet):
    queryset = sensore_data.objects.all().order_by('-timestamp')
    serializer_class = sensore_dataSerializer


class PumpUpdateViewSet(viewsets.ViewSet):
    """
    Custom ViewSet to update pump status via POST.
    """

    def post(self, request, pk=None):
        """
        POST /api/pump-measurements/<pk>/
        Payload: {"status": "ON" or "OFF"}
        """
        try:
            pump = PumpMeasurement.objects.get(pk=pk)
        except PumpMeasurement.DoesNotExist:
            return Response({"detail": "Pump not found."}, status=status.HTTP_404_NOT_FOUND)

        status_value = request.data.get("status")
        if status_value not in ["ON", "OFF"]:
            return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)

        pump.status = status_value
        pump.save()
        serializer = PumpMeasurementSerializer(pump)
        return Response(serializer.data, status=status.HTTP_200_OK)