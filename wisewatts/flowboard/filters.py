from django_filters import rest_framework as filters
import django_filters
from datetime import datetime, time
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
    start_date = django_filters.CharFilter(method='filter_start_date')
    end_date   = django_filters.CharFilter(method='filter_end_date')

    class Meta:
        model = TankReading
        fields = "__all__"

    def filter_start_date(self, queryset, name, value):
        try:
            # If only date is given (2025-01-01)
            if len(value) == 10:
                dt = datetime.strptime(value, "%Y-%m-%d")
                dt = datetime.combine(dt, time.min)  # 00:00:00
            else:
                # full datetime input
                dt = datetime.fromisoformat(value)
            return queryset.filter(timestamp__gte=dt)
        except:
            return queryset

    def filter_end_date(self, queryset, name, value):
        try:
            if len(value) == 10:
                dt = datetime.strptime(value, "%Y-%m-%d")
                dt = datetime.combine(dt, time.max)  # 23:59:59.999999
            else:
                dt = datetime.fromisoformat(value)
            return queryset.filter(timestamp__lte=dt)
        except:
            return queryset
        
class pumpReadingFilter(filters.FilterSet):  
    start_date = django_filters.CharFilter(method='filter_start_date')
    end_date   = django_filters.CharFilter(method='filter_end_date')
    class Meta:
        model = pumpReading
        fields =  "__all__"
    def filter_start_date(self, queryset, name, value):
        try:
            # If only date is given (2025-01-01)
            if len(value) == 10:
                dt = datetime.strptime(value, "%Y-%m-%d")
                dt = datetime.combine(dt, time.min)  # 00:00:00
            else:
                # full datetime input
                dt = datetime.fromisoformat(value)
            return queryset.filter(timestamp__gte=dt)
        except:
            return queryset

    def filter_end_date(self, queryset, name, value):
        try:
            if len(value) == 10:
                dt = datetime.strptime(value, "%Y-%m-%d")
                dt = datetime.combine(dt, time.max)  # 23:59:59.999999
            else:
                dt = datetime.fromisoformat(value)
            return queryset.filter(timestamp__lte=dt)
        except:
            return queryset