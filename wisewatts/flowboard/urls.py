# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register(r'sites', views.SiteViewSet)
router.register(r'tanks', views.TankViewSet)
router.register(r'pumps', views.PumpViewSet) 
router.register(r'sensors', views.SensorViewSet)
router.register(r'tank-readings', views.TankReadingViewSet)
router.register(r'pump-readings', views.pumpReadingViewSet)
urlpatterns = [
    path('', include(router.urls)),
     path("sensor-post/", views.sensor_post, name="sensor_post"),
]   