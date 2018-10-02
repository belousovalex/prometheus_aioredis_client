import copy
import json
import base64
from functools import partial
import asyncio
import collections
from .values import DocStringLine, MetricValue

from .registry import Registry
from .task_manager import TaskManager

REGISTRY = Registry(task_manager=TaskManager())



DEFAULT_GAUGE_INDEX_KEY = 'GLOBAL_GAUGE_INDEX'


class WithLabels(object):
    __slot__ = (
        "instance",
        "labels"
    )

    def __init__(self, instance, labels: dict):
        self.instance = instance
        self.labels = labels

    def __getattr__(self, item):
        attr = getattr(self.instance, item)
        if not callable(attr):
            raise TypeError("Labels work with function only")
        return partial(attr, labels=self.labels)


class Metric(object):
    """
    Proxy object for real work objects called 'minions'.
    Use as global representation on metric.
    """

    minion = None
    type = ''

    def __init__(self, name: str,
                 documentation: str, labelnames: list=None,
                 registry: Registry=REGISTRY):
        self.documentation = documentation
        self.labelnames = labelnames or []
        self.name = name
        self.registry = registry
        self.registry.add_metric(self)

    def doc_string(self) -> DocStringLine:
        return DocStringLine(
            self.name,
            self.type,
            self.documentation
        )

    async def collect(self) -> list:
        redis = self.registry.redis
        group_key = self.get_metric_group_key()
        members = await redis.smembers(
            group_key
        )

        result = []
        for metric_key in members:
            name, packed_labels = self.parse_metric_key(metric_key)
            labels = self.unpack_labels(packed_labels)
            value = await redis.get(metric_key)
            if value is None:
                await redis.srem(group_key, metric_key)
                continue
            result.append(MetricValue(
                name=name,
                labels=labels,
                value=value.decode('utf-8')
            ))
        return result

    def get_metric_group_key(self):
        return "{}_group".format(self.name)

    def get_metric_key(self, labels, suffix: str=None):
        return "{}{}:{}".format(
            self.name, suffix or "",
            self.pack_labels(labels).decode('utf-8')
        )

    def parse_metric_key(self, key) -> (str, dict):
        return key.decode('utf-8').split(':', maxsplit=1)

    def pack_labels(self, labels: dict) -> bytes:
        return base64.b64encode(
            json.dumps(labels, sort_keys=True).encode('utf-8')
        )

    def unpack_labels(self, labels: str) -> dict:
        return json.loads(base64.b64decode(labels).decode('utf-8'))

    def _check_labels(self, labels):
        if set(labels.keys()) != set(self.labelnames):
            raise ValueError("Expect define all labels {}, got only {}".format(
                ", ".join(self.labelnames),
                ", ".join(labels.keys())
            ))

    def labels(self, *args, **kwargs):
        labels = dict(zip(self.labelnames, args))
        labels.update(kwargs)
        return WithLabels(
            instance=self,
            labels=labels
        )

    async def cleanup(self):
        pass


class Counter(Metric):

    type = 'counter'

    def inc(self, value: int=1, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        self.registry.task_manager.add_task(
            self._a_inc(value, labels)
        )

    async def a_inc(self, value: int = 1, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._a_inc(value, labels)

    async def _a_inc(self, value: int = 1, labels=None):
        """
        Calculate metric with labels redis key.
        Add this key to set of key for this metric.
        """
        if not isinstance(value, int):
            raise ValueError("Value should be int, got {}".format(
                type(value)
            ))
        group_key = self.get_metric_group_key()
        metric_key = self.get_metric_key(labels)

        tr = self.registry.redis.multi_exec()
        tr.sadd(group_key, metric_key)
        future_answer = tr.incrby(metric_key, int(value))
        await tr.execute()

        return await future_answer


class Summary(Metric):

    type = 'summary'

    async def a_observe(self, value: float, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._a_observe(value, labels)

    def observe(self, value, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        self.registry.task_manager.add_task(
            self._a_observe(value, labels)
        )

    async def _a_observe(self, value: float, labels=None):

        group_key = self.get_metric_group_key()
        sum_metric_key = self.get_metric_key(labels, "_sum")
        count_metric_key = self.get_metric_key(labels, "_count")

        tr = self.registry.redis.multi_exec()
        tr.sadd(group_key, count_metric_key, sum_metric_key)
        future_answer = tr.incrbyfloat(sum_metric_key, float(value))
        tr.incr(count_metric_key)
        await tr.execute()

        return await future_answer


class Gauge(Metric):

    type = 'gauge'

    DEFAULT_EXPIRE = 60

    def __init__(self, *args,
                 expire=DEFAULT_EXPIRE,
                 refresh_enable=True,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.refresh_enable = refresh_enable
        self._refresher_added = False
        self.lock = asyncio.Lock()
        self.gauge_values = collections.defaultdict(lambda: 0)
        self.expire = expire
        self.index = None

    async def add_refresher(self):
        if self.refresh_enable and not self._refresher_added:
            await self.registry.task_manager.add_refresher(
                self.refresh_values
            )
            self._refresher_added = True

    def _set_internal(self, key: str, value: float):
        self.gauge_values[key] = value

    def _inc_internal(self, key: str, value: float):
        self.gauge_values[key] += value

    async def a_inc(self, value: float=1, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._a_inc(value, labels)

    async def a_dec(self, value: float=1, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._a_inc(-value, labels)

    async def _a_inc(self, value: float, labels: dict):
        async with self.lock:
            group_key = self.get_metric_group_key()
            labels['gauge_index'] = await self.get_gauge_index()
            metric_key = self.get_metric_key(labels)

            tr = self.registry.redis.multi_exec()
            tr.sadd(group_key, metric_key)
            future_answer = tr.incrbyfloat(metric_key, float(value))
            tr.expire(metric_key, self.expire)
            self._inc_internal(metric_key, float(value))
            await tr.execute()

            await self.add_refresher()

            return await future_answer

    async def a_set(self, value: float=1, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._a_set(value, labels)

    async def _a_set(self, value: float, labels: dict):
        async with self.lock:
            group_key = self.get_metric_group_key()
            labels['gauge_index'] = await self.get_gauge_index()
            metric_key = self.get_metric_key(labels)

            tr = self.registry.redis.multi_exec()
            tr.sadd(group_key, metric_key)
            future_answer = tr.set(
                metric_key, float(value),
                expire=self.expire
            )
            self._set_internal(metric_key, float(value))
            await tr.execute()
            await self.add_refresher()

            return await future_answer

    async def get_gauge_index(self):
        if self.index is None:
            self.index = await self.make_gauge_index()
        return self.index

    async def make_gauge_index(self):
        index = await self.registry.redis.incr(
            DEFAULT_GAUGE_INDEX_KEY
        )
        await self.registry.task_manager.add_refresher(
            self.refresh_values
        )
        return index

    async def refresh_values(self):
        async with self.lock:
            for key, value in self.gauge_values.items():
                await self.registry.redis.set(
                    key, value, expire=self.expire
                )
    
    async def cleanup(self):
        async with self.lock:
            group_key = self.get_metric_group_key()
            keys = list(self.gauge_values.keys())
            if len(keys) == 0:
                return
            tr = self.registry.redis.multi_exec()
            tr.srem(group_key, *keys)
            tr.delete(*keys)
            await tr.execute()


class Histogram(Metric):

    type = 'histogram'

    def __init__(self, *args, buckets: list, **kwargs):
        super().__init__(*args, **kwargs)
        self.buckets = sorted(buckets, reverse=True)


    async def a_observe(self, value: float, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._a_observe(value, labels)

    def observe(self, value, labels=None):
        labels = labels or {}
        self._check_labels(labels)
        self.registry.task_manager.add_task(
            self._a_observe(value, labels)
        )

    async def _a_observe(self, value: float, labels):
        group_key = self.get_metric_group_key()
        sum_key = self.get_metric_key(labels, '_sum')
        counter_key = self.get_metric_key(labels, '_count')
        tr = self.registry.redis.multi_exec()
        for bucket in self.buckets:
            if value > bucket:
                break
            labels['le'] = bucket
            bucket_key = self.get_metric_key(labels, '_bucket')
            tr.sadd(group_key, bucket_key)
            tr.incr(bucket_key)
        tr.sadd(group_key, sum_key, counter_key)
        tr.incr(counter_key)
        tr.incrbyfloat(sum_key, float(value))
        await tr.execute()

    def _get_missing_metric_values(self, redis_metric_values):
        missing_metrics_values = set(
            json.dumps({"le": b}) for b in self.buckets
        )
        groups = set("{}")

        # If flag is raised then we should add
        # *_sum and *_count values for empty labels.
        sc_flag = True
        for mv in redis_metric_values:
            key = json.dumps(mv.labels, sort_keys=True)
            labels = copy.copy(mv.labels)
            if 'le' in labels:
                del labels['le']
            group = json.dumps(labels, sort_keys=True)
            if group == "{}":
                sc_flag = False
            if group not in groups:
                for b in self.buckets:
                    labels['le'] = b
                    missing_metrics_values.add(
                        json.dumps(labels, sort_keys=True)
                    )
                groups.add(group)
            if key in missing_metrics_values:
                missing_metrics_values.remove(key)
        return missing_metrics_values, sc_flag

    async def collect(self) -> list:
        redis_metrics = await super().collect()
        missing_metrics_values, sc_flag = \
            self._get_missing_metric_values(
            redis_metrics
        )

        missing_values = [
            MetricValue(
                self.name + "_bucket",
                labels=json.loads(ls),
                value=0
            ) for ls in missing_metrics_values
        ]

        if sc_flag:
            missing_values.append(
                MetricValue(
                    self.name + "_sum",
                    labels={},
                    value=0
                )
            )
            missing_values.append(
                MetricValue(
                    self.name + "_count",
                    labels={},
                    value=0
                )
            )

        return redis_metrics + missing_values
