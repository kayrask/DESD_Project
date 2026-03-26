from django.urls import re_path
from api import consumers

websocket_urlpatterns = [
    re_path(r"^ws/orders/(?P<order_id>[^/]+)/$", consumers.OrderNotificationConsumer.as_asgi()),
    re_path(r"^ws/notifications/$", consumers.UserNotificationConsumer.as_asgi()),
    re_path(r"^ws/stock/$", consumers.StockConsumer.as_asgi()),
]
