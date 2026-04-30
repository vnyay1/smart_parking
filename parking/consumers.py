import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ParkingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Rejoindre le groupe "parking"
        await self.channel_layer.group_add('parking', self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard('parking', self.channel_name)

    async def spot_update(self, event):
        # Envoyer la mise à jour au client JS
        await self.send(text_data=json.dumps(event['data']))

# Dans une view, envoyer une MAJ :
# from channels.layers import get_channel_layer
# from asgiref.sync import async_to_sync
# channel_layer = get_channel_layer()
# async_to_sync(channel_layer.group_send)('parking', {
# 'type': 'spot_update',
# 'data': {'spot_id': 5, 'statut': 'occupee'}
# })