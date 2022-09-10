import aioredis
import prometheus_aioredis_client as prom


class MetricEnvironment(object):

    def __init__(self, redis_uri: str = None):
        self.redis_uri = redis_uri or 'redis://redis:6379'

    async def __aenter__(self):
        self.redis = await aioredis.from_url(self.redis_uri)
        await self.redis.flushdb()
        self.task_manager = prom.TaskManager(refresh_period=2)
        prom.REGISTRY.set_redis(self.redis)
        prom.REGISTRY.set_task_manager(self.task_manager)
        return self.redis

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await prom.REGISTRY.cleanup_and_close()
        await self.redis.close()
