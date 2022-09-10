import pytest

from .helpers import MetricEnvironment
import prometheus_aioredis_client as prom


class TestHistogram(object):
    redis_uri = 'redis://localhost:6380'

    @pytest.mark.asyncio
    async def test_await_interface_without_labels(self):
        async with MetricEnvironment() as redis:

            histogram = prom.Histogram(
                name="test_histogram",
                documentation="Histogram documentation",
                buckets=[1, 20, 25.5]
            )

            await histogram.a_observe(25.4)
            group_key = histogram.get_metric_group_key()

            assert sorted(await redis.smembers(group_key)) == [
                b'test_histogram_bucket:eyJsZSI6IDI1LjV9',
                b'test_histogram_count:e30=',
                b'test_histogram_sum:e30=',
            ]
            assert float(await redis.get('test_histogram_sum:e30=')) == 25.4
            assert float(await redis.get('test_histogram_bucket:eyJsZSI6IDI1LjV9')) == 1
            assert float(await redis.get('test_histogram_count:e30=')) == 1

            await histogram.a_observe(3)

            assert sorted(await redis.smembers(group_key)) == [
                b'test_histogram_bucket:eyJsZSI6IDI1LjV9',
                b'test_histogram_bucket:eyJsZSI6IDIwfQ==',
                b'test_histogram_count:e30=',
                b'test_histogram_sum:e30='
            ]
            assert float(await redis.get('test_histogram_sum:e30=')) == 28.4
            assert float(await redis.get('test_histogram_count:e30=')) == 2
            assert float(await redis.get('test_histogram_bucket:eyJsZSI6IDIwfQ==')) == 1
            assert float(await redis.get('test_histogram_bucket:eyJsZSI6IDI1LjV9')) == 2

            assert (await prom.REGISTRY.output()) == (
                '# HELP test_histogram Histogram documentation\n'
                '# TYPE test_histogram histogram\n'
                'test_histogram_bucket{le="1"} 0\n'
                'test_histogram_bucket{le="20"} 1\n'
                'test_histogram_bucket{le="25.5"} 2\n'
                'test_histogram_count 2\n'
                'test_histogram_sum 28.4'
            )

    @pytest.mark.asyncio
    async def test_await_interface_with_labels(self):
        async with MetricEnvironment() as redis:

            histogram = prom.Histogram(
                name="test_histogram",
                documentation="Histogram documentation",
                labelnames=["host", "url"],
                buckets=[0, 1, 2.001, 3]
            )

            # need 'url' label
            with pytest.raises(ValueError):
                await histogram.labels(host="123.123.123.123").a_observe(12)

            # need use labels method
            with pytest.raises(Exception):
                await histogram.a_observe(23)

            labels = dict(host="123.123.123.123", url="/home/")
            await histogram.labels("123.123.123.123", "/home/").a_observe(2.1)
            group_key = histogram.get_metric_group_key()

            counter_key = b'test_histogram_count:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            sum_key = b'test_histogram_sum:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            key_bucket_3 = b'test_histogram_bucket:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJsZSI6IDMsICJ1cmwiOiAiL2hvbWUvIn0='

            key_bucket_1 = b'test_histogram_bucket:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJsZSI6IDEsICJ1cmwiOiAiL2hvbWUvIn0='
            key_bucket_2_001 = b'test_histogram_bucket:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJsZSI6IDIuMDAxLCAidXJsIjogIi9ob21lLyJ9'

            assert sorted(await redis.smembers(group_key)) == [
                key_bucket_3, counter_key, sum_key
            ]
            assert float(await redis.get(key_bucket_3)) == 1

            await histogram.labels(**labels).a_observe(0.2)

            assert sorted(await redis.smembers(group_key)) == sorted([
                key_bucket_1,
                key_bucket_2_001,
                key_bucket_3,
                counter_key, sum_key
            ])
            assert float(await redis.get(key_bucket_3)) == 2
            assert float(await redis.get(key_bucket_1)) == 1
            assert float(await redis.get(sum_key)) == 2.3
            assert float(await redis.get(counter_key)) == 2

            assert (await prom.REGISTRY.output()) == (
                '# HELP test_histogram Histogram documentation\n'
                '# TYPE test_histogram histogram\n'
                'test_histogram_bucket{host="123.123.123.123",le="0",url="/home/"} 0\n'
                'test_histogram_bucket{host="123.123.123.123",le="1",url="/home/"} 1\n'
                'test_histogram_bucket{host="123.123.123.123",le="2.001",url="/home/"} 1\n'
                'test_histogram_bucket{host="123.123.123.123",le="3",url="/home/"} 2\n'
                'test_histogram_bucket{le="0"} 0\n'
                'test_histogram_bucket{le="1"} 0\n'
                'test_histogram_bucket{le="2.001"} 0\n'
                'test_histogram_bucket{le="3"} 0\n'
                'test_histogram_count 0\n'
                'test_histogram_count{host="123.123.123.123",url="/home/"} 2\n'
                'test_histogram_sum 0\n'
                'test_histogram_sum{host="123.123.123.123",url="/home/"} 2.3'
            )

    @pytest.mark.asyncio
    async def test_simple_interface_without_labels(self):
        async with MetricEnvironment() as redis:

            histogram = prom.Histogram(
                name="test_histogram",
                documentation="Histogram documentation",
                buckets=[0, 1, 167]
            )

            histogram.observe(125)
            group_key = histogram.get_metric_group_key()
            await prom.REGISTRY.task_manager.wait_tasks()

            assert sorted(await redis.smembers(group_key)) == [
                b'test_histogram_bucket:eyJsZSI6IDE2N30=',
                b'test_histogram_count:e30=',
                b'test_histogram_sum:e30='
            ]

    @pytest.mark.asyncio
    async def test_simple_interface_with_labels(self):
        async with MetricEnvironment() as redis:

            histogram = prom.Histogram(
                name="test_histogram",
                documentation="Histogram documentation",
                labelnames=["host", "url"],
                buckets=[0, 3, 4]
            )
            labels = dict(host="123.123.123.123", url="/home/")
            histogram.labels(**labels).observe(2.1)
            group_key = histogram.get_metric_group_key()

            await prom.REGISTRY.task_manager.wait_tasks()

            bucket_3_key = b'test_histogram_bucket:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJsZSI6IDMsICJ1cmwiOiAiL2hvbWUvIn0='
            bucket_4_key = b'test_histogram_bucket:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJsZSI6IDQsICJ1cmwiOiAiL2hvbWUvIn0='
            counter_key = b'test_histogram_count:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            sum_key = b'test_histogram_sum:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            assert sorted(await redis.smembers(group_key)) == [
                bucket_3_key,
                bucket_4_key,
                counter_key,
                sum_key
            ]
            assert float(await redis.get(bucket_3_key)) == 1
            assert float(await redis.get(bucket_4_key)) == 1
            assert float(await redis.get(counter_key)) == 1
            assert float(await redis.get(sum_key)) == 2.1

            histogram.labels(**labels).observe(3)
            await prom.REGISTRY.task_manager.wait_tasks()

            assert float(await redis.get(bucket_3_key)) == 2
            assert float(await redis.get(bucket_4_key)) == 2
            assert float(await redis.get(counter_key)) == 2
            assert float(await redis.get(sum_key)) == 5.1
