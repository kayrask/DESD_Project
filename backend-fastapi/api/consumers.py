import json
from channels.generic.websocket import AsyncWebsocketConsumer


class OrderNotificationConsumer(AsyncWebsocketConsumer):
    """
    Connected to by a customer on the order confirmation / dashboard page.
    Receives a push when a producer updates the vendor order status.

    URL: ws/orders/<order_id>/
    """

    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.group = f"order_{self.order_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    # Called when channel_layer.group_send type=="order.status.update"
    async def order_status_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "status_update",
            "order_id": event["order_id"],
            "status": event["status"],
        }))


class UserNotificationConsumer(AsyncWebsocketConsumer):
    """
    Per-user notification channel (dashboard live badge updates).

    URL: ws/notifications/
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.group = f"user_{user.id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def order_status_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "order_status_update",
            "order_id": event["order_id"],
            "status": event["status"],
        }))

    async def new_order(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_order",
            "order_id": event["order_id"],
            "customer_name": event["customer_name"],
        }))


class StockConsumer(AsyncWebsocketConsumer):
    """
    Broadcast channel for real-time stock changes.
    All connected product-list pages receive stock updates instantly.

    URL: ws/stock/
    """
    GROUP = "stock_updates"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    # Called when channel_layer.group_send type=="stock.update"
    async def stock_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "stock_update",
            "product_id": event["product_id"],
            "stock": event["stock"],
            "status": event["status"],
        }))
