from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user', AnonymousUser())
        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        self.store_id = self.scope['url_route']['kwargs']['store_id']
        self.room_group_name = f'store_{self.store_id}_notifications'

        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def send_notification(self, event):
        await self.send_json(event['data'])
