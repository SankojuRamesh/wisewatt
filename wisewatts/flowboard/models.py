from django.db import models 
import uuid 
from django.utils import timezone


class Site(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now) 
    site_ifo = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name
    
class Tank(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='tanks')
    name = models.CharField(max_length=255)
    capacity = models.FloatField()
    height = models.FloatField()
    
    created_at = models.DateTimeField(default=timezone.now) 
    

    def __str__(self):
        return self.name
    
class Pump(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='site_pumps')
    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='site_tank')
    name = models.CharField(max_length=255)
    flow_rate = models.FloatField()
   
    

    def __str__(self):
        return self.name
class Sensor(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='site_sensors')
    
    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='tank_sensors')
    name = models.CharField(max_length=255)
    sensor_type = models.CharField(max_length=100, default='ultrasonic', null=True, blank=True  )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    sensor_info = models.JSONField(default=dict, blank=True)

class TankReading(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='tank_readings')
    water_level_cm = models.FloatField()
    water_level_perc = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now) 
    def __str__(self):
        return self.name
    
class pumpReading(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name='pump_readings')
    flow_rate_lpm = models.CharField(max_length=20, default='0', null=True, blank=True  )
    pump_on = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now) 
    def __str__(self):
        return self.name
 