# myapi/views.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

@csrf_exempt
def sensor_post(request):
    """
    Accepts POST JSON from device and broadcasts to channels group "sensors".
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "invalid json", "detail": str(e)}, status=400)

    # normalize / enrich payload
    payload.setdefault("ts", timezone.now().isoformat())
    # optionally validate fields here

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "sensors",  # group name
        {
            "type": "sensor.update",   # handler name on consumers
            "payload": payload
        }
    )

    return JsonResponse({"ok": True})
