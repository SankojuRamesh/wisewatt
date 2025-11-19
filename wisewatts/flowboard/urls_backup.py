# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views_backup

router = DefaultRouter()
router.register(r'users', views_backup.UserViewSet)
router.register(r'sites', views_backup.SiteViewSet)
router.register(r'devices', views_backup.UserDeviceViewSet)
router.register(r'tanks', views_backup.TankViewSet)
router.register(r'pumps', views_backup.PumpViewSet)
router.register(r'tank-measurements', views_backup.TankMeasurementViewSet)
router.register(r'pump-measurements', views_backup.PumpMeasurementViewSet)
# router.register(r'pump-runs', views.PumpRunEventViewSet)
router.register(r'sensore_data', views_backup.sensore_viewset) 
router.register(r'logs', views_backup.SensorLogViewSet)
pump_update = views_backup.PumpUpdateViewSet.as_view({'post': 'post'})


urlpatterns = [
    path('', include(router.urls)),
    path('ingest/', views_backup.ingest_data, name='ingest_data'),
    path('install/', views_backup.install, name='install'),
     path('pumpupdate/<int:pk>/', pump_update, name='pump-update'),
]
