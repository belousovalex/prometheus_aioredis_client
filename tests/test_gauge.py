import asyncio
import pytest
import base64

from .helpers import MetricEnvironment
import prometheus_aioredis_client as prom


class TestGauge(object):
    redis_uri = 'redis://localhost:6380'

    @pytest.mark.asyncio
    async def test_await_interface_without_labels(self):
        async with MetricEnvironment() as redis:
            gauge = prom.Gauge(
                "test_gauge",
                "Gauge Documentation",
                expire=4,
            )

            await gauge.a_set(12.3)
            gauge_index = int(await redis.get(prom.DEFAULT_GAUGE_INDEX_KEY))

            group_key = gauge.get_metric_group_key()
            metric_key = "test_gauge:{}".format(
                base64.b64encode(('{"gauge_index": %s}' % gauge_index).encode('utf-8')).decode('utf-8')
            ).encode('utf-8')
            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 12.3

            await gauge.a_set(12.9)
            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 12.9

            await gauge.a_dec(1.7)
            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 11.2

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_gauge Gauge Documentation\n"
                "# TYPE test_gauge gauge\n" 
                "test_gauge{gauge_index=\"%s\"} 11.2"
            ) % gauge_index

    @pytest.mark.asyncio
    async def test_await_interface_with_labels(self):
        async with MetricEnvironment() as redis:
            gauge = prom.Gauge(
                "test_gauge",
                "Gauge Documentation",
                ['name'],
                expire=4,
            )

            await gauge.labels(name='test').a_set(12.3)

            gauge_index = int(await redis.get(prom.DEFAULT_GAUGE_INDEX_KEY))
            group_key = gauge.get_metric_group_key()
            metric_key = "test_gauge:{}".format(
                base64.b64encode(('{"gauge_index": %s, "name": "test"}' % gauge_index).encode('utf-8')).decode('utf-8')
            ).encode('utf-8')
            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 12.3

            await gauge.labels(name='test').a_inc(1.7)
            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 14.0

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_gauge Gauge Documentation\n"
                "# TYPE test_gauge gauge\n" 
                "test_gauge{gauge_index=\"%s\",name=\"test\"} 14"
            ) % gauge_index

    @pytest.mark.asyncio
    async def test_sync_interface_with_labels(self):
        async with MetricEnvironment() as redis:
            gauge = prom.Gauge(
                "test_gauge",
                "Gauge Documentation",
                ['name'],
                expire=4,
            )

            gauge.labels(name='test').set(12.3)
            await prom.REGISTRY.task_manager.wait_tasks()

            gauge_index = int(await redis.get(prom.DEFAULT_GAUGE_INDEX_KEY))
            group_key = gauge.get_metric_group_key()
            metric_key = "test_gauge:{}".format(
                base64.b64encode(('{"gauge_index": %s, "name": "test"}' % gauge_index).encode('utf-8')).decode('utf-8')
            ).encode('utf-8')
            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 12.3

            gauge.labels(name='test').inc(1.7)
            await prom.REGISTRY.task_manager.wait_tasks()

            assert sorted(await redis.smembers(group_key)) == sorted([
                metric_key
            ])
            assert float(await redis.get(metric_key)) == 14.0

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_gauge Gauge Documentation\n"
                "# TYPE test_gauge gauge\n"
                "test_gauge{gauge_index=\"%s\",name=\"test\"} 14"
            ) % gauge_index

    @pytest.mark.asyncio
    async def test_auto_clean(self):
        async with MetricEnvironment() as redis:
            gauge = prom.Gauge(
                "test_gauge",
                "Gauge Documentation",
                expire=4,
            )

            await gauge.a_set(12.3)

            group_key = gauge.get_metric_group_key()
            gauge_index = int(await redis.get(prom.DEFAULT_GAUGE_INDEX_KEY))
            metric_key = "test_gauge:{}".format(
                base64.b64encode(('{"gauge_index": %s}' % gauge_index).encode('utf-8')).decode('utf-8')
            ).encode('utf-8')
            assert float(await redis.get(metric_key)) == 12.3

            # force stop refresh metrics
            prom.REGISTRY.task_manager._refresh_task.cancel()

            # after expire timeout metric should be remove
            await asyncio.sleep(5)
            assert (await redis.get(metric_key)) is None

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_gauge Gauge Documentation\n"
                "# TYPE test_gauge gauge"
            )
            # ... and remove metric from group
            assert (await redis.smembers(group_key)) == set()

    @pytest.mark.asyncio
    async def test_refresh(self):
        async with MetricEnvironment() as redis:
            gauge = prom.Gauge(
                "test_gauge",
                "Gauge Documentation",
                expire=4,
            )

            await gauge.a_set(12.3)

            gauge_index = int(await redis.get(prom.DEFAULT_GAUGE_INDEX_KEY))
            metric_key = "test_gauge:{}".format(
                base64.b64encode(('{"gauge_index": %s}' % gauge_index).encode('utf-8')).decode('utf-8')
            ).encode('utf-8')
            assert float(await redis.get(metric_key)) == 12.3

            await asyncio.sleep(6)
            assert float(await redis.get(metric_key)) == 12.3

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_gauge Gauge Documentation\n"
                "# TYPE test_gauge gauge\n" 
                "test_gauge{gauge_index=\"%s\"} 12.3"
            ) % gauge_index
