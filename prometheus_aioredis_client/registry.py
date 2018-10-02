import asyncio


class Registry(object):

    def __init__(self, redis=None, task_manager=None, loop=None):
        self._metrics = []
        self._refresh_metric_process = None
        self.redis = None
        self.task_manager = None
        self.setup(redis, task_manager, loop)

    async def output(self) -> str:
        all_metric = []
        for metric in self._metrics:
            all_metric.append(metric.doc_string())
            ms = await metric.collect()
            all_metric += sorted([
                p for p in ms
            ], key=lambda x: x.output())
        return "\n".join((
            m.output() for m in all_metric
        ))

    def setup(self, redis=None, task_manager=None, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self.redis = redis
        self.task_manager = task_manager
        return self

    def add_metric(self, *metrics):
        already_added = set([
            m.name for m in self._metrics
        ])
        new_metrics = set([
            m.name for m in metrics
        ])
        doubles = already_added.intersection(new_metrics)
        if doubles:
            raise ValueError("Metrics {} already added".format(
                ", ".join(doubles)
            ))

        for m in metrics:
            self._metrics.append(m)

    def set_redis(self, redis):
        self.redis = redis

    def set_task_manager(self, manager):
        self.task_manager = manager

    async def cleanup_and_close(self):
        await self.task_manager.close()
        for metric in self._metrics:
            await metric.cleanup()
        self._metrics = []
