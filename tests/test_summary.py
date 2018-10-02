import pytest

from .helpers import MetricEnvironment
import prometheus_aioredis_client as prom


class TestSummary(object):
    redis_uri = 'redis://localhost:6380'

    @pytest.mark.asyncio
    async def test_await_interface_without_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            summary = prom.Summary(
                name="test_summary",
                documentation="Summary documentation"
            )

            await summary.a_observe(1)
            group_key = summary.get_metric_group_key()

            assert sorted(await redis.smembers(group_key)) == [
                b'test_summary_count:e30=',
                b'test_summary_sum:e30='
            ]
            assert int(await redis.get('test_summary_count:e30=')) == 1
            assert float(await redis.get('test_summary_sum:e30=')) == 1

            await summary.a_observe(3.5)
            assert int(await redis.get('test_summary_count:e30=')) == 2
            assert float(await redis.get('test_summary_sum:e30=')) == 4.5

            assert (await prom.REGISTRY.output()) == (
                "# HELP test_summary Summary documentation\n"
                "# TYPE test_summary summary\n"
                "test_summary_count 2\n"
                "test_summary_sum 4.5"
            )

    @pytest.mark.asyncio
    async def test_await_interface_with_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            summary = prom.Summary(
                name="test_summary",
                documentation="Summary documentation",
                labelnames=["host", "url"]
            )

            # need 'url' label
            with pytest.raises(ValueError):
                await summary.labels(host="123.123.123.123").a_observe(3)

            # need use labels method
            with pytest.raises(Exception):
                await summary.a_observe(1)

            labels = dict(host="123.123.123.123", url="/home/")
            await summary.labels(**labels).a_observe(2)
            group_key = summary.get_metric_group_key()

            assert sorted(await redis.smembers(group_key)) == [
                b'test_summary_count:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0=',
                b'test_summary_sum:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0=',
            ]
            metric_sum_key = 'test_summary_sum:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            metric_count_key = 'test_summary_count:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            assert int(await redis.get(metric_count_key)) == 1
            assert float(await redis.get(metric_sum_key)) == 2

            assert (await summary.labels(**labels).a_observe(3.1)) == 5.1
            assert int(await redis.get(metric_count_key)) == 2
            assert float(await redis.get(metric_sum_key)) == 5.1

            assert (await prom.REGISTRY.output()) == (
                '# HELP test_summary Summary documentation\n'
                '# TYPE test_summary summary\n'
                'test_summary_count{host="123.123.123.123",url="/home/"} 2\n'
                'test_summary_sum{host="123.123.123.123",url="/home/"} 5.1'
            )

    @pytest.mark.asyncio
    async def test_simple_interface_without_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            counter = prom.Summary(
                name="test_summary",
                documentation="Summary documentation"
            )

            counter.observe(3.6)
            group_key = counter.get_metric_group_key()
            await prom.REGISTRY.task_manager.wait_tasks()

            assert sorted(await redis.smembers(group_key)) == [
                b'test_summary_count:e30=',
                b'test_summary_sum:e30=',
            ]
            assert int(await redis.get('test_summary_count:e30=')) == 1
            assert float(await redis.get('test_summary_sum:e30=')) == 3.6

    @pytest.mark.asyncio
    async def test_simple_interface_with_labels(self):
        async with MetricEnvironment(self.redis_uri) as redis:

            summary = prom.Summary(
                name="test_summary",
                documentation="Summary documentation",
                labelnames=["host", "url"]
            )

            # need 'url' label
            with pytest.raises(ValueError):
                summary.labels(host="123.123.123.123").observe(1.2)

            # need use labels method
            with pytest.raises(Exception):
                summary.observe(2.3)

            labels = dict(host="123.123.123.123", url="/home/")
            summary.labels(**labels).observe(2.3)
            group_key = summary.get_metric_group_key()

            await prom.REGISTRY.task_manager.wait_tasks()

            assert sorted(await redis.smembers(group_key)) == [
                b'test_summary_count:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0=',
                b'test_summary_sum:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            ]
            metric_count_key = 'test_summary_count:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='
            metric_sum_key = 'test_summary_sum:eyJob3N0IjogIjEyMy4xMjMuMTIzLjEyMyIsICJ1cmwiOiAiL2hvbWUvIn0='

            assert int(await redis.get(metric_count_key)) == 1
            assert float(await redis.get(metric_sum_key)) == 2.3

            summary.labels(**labels).observe(3.1)
            await prom.REGISTRY.task_manager.wait_tasks()

            assert int(await redis.get(metric_count_key)) == 2
            assert float(await redis.get(metric_sum_key)) == 5.4
