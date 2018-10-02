import aioredis
import prometheus_aioredis_client as prom


class MetricEnvironment(object):

    def __init__(self, redis_uri:str):
        self.redis_uri = redis_uri

    async def __aenter__(self):
        self.redis = await aioredis.create_redis_pool(self.redis_uri)
        self.redis.execute("FLUSHDB")
        self.task_manager = prom.TaskManager(refresh_period=2)
        prom.REGISTRY.set_redis(self.redis)
        prom.REGISTRY.set_task_manager(self.task_manager)
        return self.redis

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await prom.REGISTRY.cleanup_and_close()
        self.redis.close()
        await self.redis.wait_closed()
