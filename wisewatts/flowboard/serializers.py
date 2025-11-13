# serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import (
    User, Site, UserDevice, Tank, Pump,
    TankMeasurement, PumpMeasurement, PumpRunEvent, SensorLog, sensore_data
)

class sensore_dataSerializer(serializers.ModelSerializer):
    class Meta:
        model = sensore_data
        fields = "__all__"
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = "__all__"


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = "__all__"


class TankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tank
        fields = "__all__"


class PumpSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pump
        fields = "__all__"


class TankMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = TankMeasurement
        fields = "__all__"


class PumpMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PumpMeasurement
        fields = "__all__"


class PumpRunEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PumpRunEvent
        fields = "__all__"


class SensorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorLog
        fields = "__all__"


# ---------------------------
# Ingest payload serializer
# ---------------------------
class PumpIngestSerializer(serializers.Serializer):
    pump_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["ON", "OFF"])


class TankIngestSerializer(serializers.Serializer):
    equipment_id = serializers.CharField(required=False, allow_blank=True)
    total_height_mm = serializers.IntegerField()
    distance_mm = serializers.IntegerField(required=False, allow_null=True)


class SiteIngestSerializer(serializers.Serializer):
    site_code = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)
    device_id = serializers.CharField(required=False, allow_blank=True)
    tank = TankIngestSerializer(required=False)
    pumps = PumpIngestSerializer(many=True, required=False)
    timestamp = serializers.DateTimeField(required=False)  # ISO8601 expected
    raw = serializers.DictField(child=serializers.JSONField(), required=False)


class MultiSiteIngestSerializer(serializers.Serializer):
    sites = SiteIngestSerializer(many=True)
