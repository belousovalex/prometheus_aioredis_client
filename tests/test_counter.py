import pytest

from .helpers import MetricEnvironment
import prometheus_aioredis_client as prom


class TestCounter(object):
    redis_uri = 'redis://localhost:6380'

    @pytest.mark.asyncio
    async def test_await_interface_without_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            counter = prom.Counter(
                name="test_counter1",
                documentation="Counter documentation"
            )

            await counter.a_inc()
            group_key = counter.get_metric_group_key()
            metric_key = counter.get_metric_key({})

            assert (await redis.smembers(group_key)) == [b'test_counter1:e30=']
            assert int(await redis.get(metric_key)) == 1

            await counter.a_inc(3)
            assert float(await redis.get(metric_key)) == 4

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_counter1 Counter documentation\n"
                "# TYPE test_counter1 counter\n" 
                "test_counter1 4"
            )

    @pytest.mark.asyncio
    async def test_await_interface_with_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            counter = prom.Counter(
                name="test_counter2",
                documentation="Counter documentation",
                labelnames=["host", "url"]
            )

            # need 'url' label
            with pytest.raises(ValueError):
                await counter.labels(host="123.123.123.123").a_inc()

            # need use labels method
            with pytest.raises(Exception):
                await counter.a_inc()

            labels = dict(host="123.123.123.123", url="/home/")
            await counter.labels(**labels).a_inc(2)
            group_key = counter.get_metric_group_key()
            metric_key = counter.get_metric_key(labels)

            assert (await redis.smembers(group_key)) == [b'test_counter2:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0=']
            assert int(await redis.get(metric_key)) == 2

            assert (await counter.labels(**labels).a_inc(3)) == 5
            assert int(await redis.get(metric_key)) == 5


    @pytest.mark.asyncio
    async def test_simple_interface_without_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            counter = prom.Counter(
                name="test_counter2",
                documentation="Counter documentation"
            )

            counter.inc()
            group_key = counter.get_metric_group_key()
            metric_key = counter.get_metric_key({})
            await prom.REGISTRY.task_manager.wait_tasks()

            assert (await redis.smembers(group_key)) == [b'test_counter2:e30=']
            assert int(await redis.get(metric_key)) == 1

    @pytest.mark.asyncio
    async def test_simple_interface_with_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            counter = prom.Counter(
                name="test_counter2",
                documentation="Counter documentation",
                labelnames=["host", "url"]
            )

            # need 'url' label
            with pytest.raises(ValueError):
                counter.labels(host="123.123.123.123").inc()

            # need use labels method
            with pytest.raises(Exception):
                counter.inc()

            labels = dict(host="123.123.123.123", url="/home/")
            counter.labels(**labels).inc(2)
            group_key = counter.get_metric_group_key()
            metric_key = counter.get_metric_key(labels)

            await prom.REGISTRY.task_manager.wait_tasks()

            assert (await redis.smembers(group_key)) == [
                b'test_counter2:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            ]
            assert int(await redis.get(metric_key)) == 2

            counter.labels(**labels).inc(3)
            await prom.REGISTRY.task_manager.wait_tasks()

            assert int(await redis.get(metric_key)) == 5
