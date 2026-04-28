from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from tenants.models import Store


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user', AnonymousUser())
        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        self.store_id = self.scope['url_route']['kwargs']['store_id']

        # Verify the user owns this store
        is_owner = await self._check_store_owner(user.id, self.store_id)
        if not is_owner:
            await self.close(code=4003)
            return

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

    @database_sync_to_async
    def _check_store_owner(self, user_id, store_id):
        return Store.objects.filter(id=store_id, owner_id=user_id, is_active=True).exists()
