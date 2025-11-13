# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'sites', views.SiteViewSet)
router.register(r'devices', views.UserDeviceViewSet)
router.register(r'tanks', views.TankViewSet)
router.register(r'pumps', views.PumpViewSet)
router.register(r'tank-measurements', views.TankMeasurementViewSet)
router.register(r'pump-measurements', views.PumpMeasurementViewSet)
# router.register(r'pump-runs', views.PumpRunEventViewSet)
router.register(r'sensore_data', views.sensore_viewset) 
router.register(r'logs', views.SensorLogViewSet)
pump_update = views.PumpUpdateViewSet.as_view({'post': 'post'})


urlpatterns = [
    path('', include(router.urls)),
    path('ingest/', views.ingest_data, name='ingest_data'),
    path('install/', views.install, name='install'),
     path('pumpupdate/<int:pk>/', pump_update, name='pump-update'),
]
