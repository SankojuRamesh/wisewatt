from django_filters import rest_framework as filters
from .models import Site, Tank, Pump, Sensor, TankReading, pumpReading
class SiteFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    created_at = filters.DateFromToRangeFilter()

    class Meta:
        model = Site
        fields = ['name', 'created_at']
class TankFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    site = filters.ModelChoiceFilter(queryset=Site.objects.all())
    capacity = filters.RangeFilter()
    height = filters.RangeFilter()
    created_at = filters.DateFromToRangeFilter()

    class Meta:
        model = Tank
        fields = ['site', 'name', 'capacity', 'height', 'created_at'] 

class PumpFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    site = filters.ModelChoiceFilter(queryset=Site.objects.all())
    tank = filters.ModelChoiceFilter(queryset=Tank.objects.all())
    flow_rate = filters.RangeFilter()
    pump_state = filters.BooleanFilter()
    pump_power_state = filters.BooleanFilter()
    created_at = filters.DateFromToRangeFilter()


    class Meta:
        model = Pump
        fields = ['site', 'tank', 'name', 'flow_rate', 'pump_state', 'pump_power_state', 'created_at'] 

class SensorFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')
    site = filters.ModelChoiceFilter(queryset=Site.objects.all())
    tank = filters.ModelChoiceFilter(queryset=Tank.objects.all())
    sensor_type = filters.CharFilter(lookup_expr='icontains')
    created_at = filters.DateFromToRangeFilter()
    updated_at = filters.DateFromToRangeFilter()

    class Meta:
        model = Sensor
        fields = ['site', 'tank', 'name', 'sensor_type', 'created_at', 'updated_at']    

class TankReadingFilter(filters.FilterSet):
    

    class Meta:
        model = TankReading
        fields =  "__all__"   
class pumpReadingFilter(filters.FilterSet):  
    class Meta:
        model = pumpReading
        fields =  "__all__"