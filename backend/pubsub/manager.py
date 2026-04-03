import json
import asyncio
import redis.asyncio as aioredis


class RedisPubSubManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.pub = None
        self.sub = None

    async def initialize(self):
        self.pub = await aioredis.from_url(self.redis_url)
        self.sub = await aioredis.from_url(self.redis_url)

    async def publish(self, channel: str, message: dict):
        await self.pub.publish(channel, json.dumps(message))

    async def subscribe(self, channel: str, callback):
        asyncio.create_task(self._listener(channel, callback))

    async def _listener(self, channel: str, callback):
        pubsub = self.sub.pubsub()
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await callback(data)
