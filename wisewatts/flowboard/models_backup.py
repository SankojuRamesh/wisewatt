from django.db import models

# Create your models here.
# models.py
import uuid
from django.db import models
from django.utils import timezone

# -------------------------
# Core / Organization
# -------------------------
class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    access_level = models.CharField(max_length=50, blank=True)   # e.g. admin/operator/viewer
    organization = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.organization})"


class Site(models.Model):
    """
    A physical place/location where devices, tanks, and pumps exist.
    Example: 'Pumpstation A', 'Farm Well #2'
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_code = models.CharField(max_length=100, unique=True)   # friendly code/ID
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sites")
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.site_code})"


# -------------------------
# Devices & Equipment
# -------------------------
class UserDevice(models.Model):
    """
    Physical device (ESP32 / sensor node). A device can be assigned to a site.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_id = models.CharField(max_length=200, unique=True)   # hardware unique id
    device_type = models.CharField(max_length=100, blank=True)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device_id} ({self.device_type})"


class Tank(models.Model):
    """
    A tank at a site. A site can have multiple tanks.
    total_height_mm: provided by user (integer mm)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="tanks")
    equipment_id = models.CharField(max_length=200, blank=True)  # optional equipment tag
    description = models.TextField(blank=True)
    total_height_mm = models.PositiveIntegerField(help_text="Total tank height in mm (provided by user)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('site', 'equipment_id')

    def __str__(self):
        return f"Tank {self.equipment_id or self.id} @ {self.site.site_code}"


class Pump(models.Model):
    """
    A pump attached to a site/tank. A site or tank may have many pumps.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pumps")
    tank = models.ForeignKey(Tank, on_delete=models.SET_NULL, null=True, blank=True, related_name="pumps")
    pump_id = models.CharField(max_length=200, blank=True)  # tag/label
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('site', 'pump_id')

    def __str__(self):
        return f"Pump {self.pump_id or self.id} @ {self.site.site_code}"


# -------------------------
# Per-minute telemetry (normalized)
# -------------------------
class TankMeasurement(models.Model):
    """
    One row per measurement for a tank (typically per-minute).
    distance_mm: raw sensor reading (distance from sensor to liquid surface)
    tank_level_mm: computed = total_height_mm - distance_mm
    tank_level_percent: derived percent (0-100)
    pump_status_snapshot: JSON mapping pump_id -> state at that timestamp (optional)
    raw_payload: raw JSON from device, helpful for debugging
    """
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="tank_measurements")
    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name="measurements")
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="tank_measurements")
    timestamp = models.DateTimeField()  # measurement time (store in UTC)
    distance_mm = models.IntegerField(null=True, blank=True)
    tank_level_mm = models.IntegerField(null=True, blank=True)
    tank_level_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pump_status_snapshot = models.JSONField(null=True, blank=True, help_text='{"pump_1":"ON","pump_2":"OFF"}')
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['site', 'timestamp']),
            models.Index(fields=['tank', 'timestamp']),
            models.Index(fields=['device', 'timestamp']),
        ]
        unique_together = ('tank', 'timestamp')  # one measurement per tank per timestamp

    def save(self, *args, **kwargs):
        # derive tank level values if we have the distance and tank total height
        if self.distance_mm is not None and self.tank and self.tank.total_height_mm:
            try:
                total = int(self.tank.total_height_mm)
                level = total - int(self.distance_mm)
                self.tank_level_mm = max(0, level)
                if total > 0:
                    self.tank_level_percent = round((self.tank_level_mm / total) * 100, 2)
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tank} @ {self.timestamp.isoformat()}"


class PumpMeasurement(models.Model):
    """
    Normalized pump status per timestamp for analytics.
    Use when you want a joinable table instead of a JSON snapshot.
    """
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pump_measurements")
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name="measurements")
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="pump_measurements")
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=5, choices=(('ON','ON'),('OFF','OFF')))
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['pump', 'timestamp']),
            models.Index(fields=['site', 'timestamp']),
        ]
        unique_together = ('pump', 'timestamp')

    def __str__(self):
        return f"{self.pump} {self.status} @ {self.timestamp.isoformat()}"


# -------------------------
# Pump run events (persisted)
# -------------------------
class PumpRunEvent(models.Model):
    """
    Persisted start/stop runs for a pump.
    Create on detecting transitions (ON -> OFF or OFF -> ON).
    """
    id = models.BigAutoField(primary_key=True)
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name="run_events")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pump_run_events")
    start_time = models.DateTimeField(auto_now_add=True)
    stop_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['pump', 'start_time']),
        ]

    def save(self, *args, **kwargs):
        if self.start_time and self.stop_time and not self.duration_seconds:
            delta = self.stop_time - self.start_time
            self.duration_seconds = int(delta.total_seconds())
        super().save(*args, **kwargs)

    def __str__(self):
        if self.duration_seconds:
            return f"{self.pump.pump_id} run {self.start_time} ({self.duration_seconds}s)"
        return f"{self.pump.pump_id} run start {self.start_time}"


# -------------------------
# Raw logs (catch-all)
# -------------------------
class SensorLog(models.Model):
    """
    Store raw payloads for debugging, auditing, replay.
    Optionally used if you need full raw history (can be large).
    """
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    payload = models.JSONField()
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['site', 'timestamp']), models.Index(fields=['device', 'timestamp'])]


class sensore_data(models.Model):
    sensor_id = models.CharField(max_length=100)
    data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
         