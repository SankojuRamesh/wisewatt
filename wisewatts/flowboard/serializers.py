from rest_framework import serializers
from django.utils import timezone
from .models import Site, Tank, Pump, Sensor, TankReading, pumpReading

class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = "__all__"
class TankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tank
        fields = "__all__"
class PumpSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pump
        fields = "__all__"
class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = "__all__"
class TankReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TankReading
        fields = "__all__"
class pumpReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = pumpReading
        fields = "__all__"

