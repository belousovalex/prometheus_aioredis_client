import asyncio
import logging

logger = logging.getLogger(__name__)


class TaskManager(object):
    """
    Manage all running tasks and refresh gauge values.
    """

    def __init__(self, refresh_period=30, refresh_enable=True, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self.tasks = []
        self._refresh_enable = refresh_enable
        self._refresh_period = refresh_period
        self._refresh_task = None
        self._refreshers = []
        self._refresh_lock = asyncio.Lock()
        self._close = False

    def set_refresh_period(self, period):
        self._refresh_period = period

    def add_task(self, coro):
        if self._close:
            raise Exception("Cant add task for closed manager.")
        task = asyncio.ensure_future(coro, loop=self._loop)
        self.tasks.append(task)
        task.add_done_callback(self.tasks.remove)

    async def add_refresher(self, refresh_async_func: callable):
        if not self._refresh_enable:
            raise Exception('Refresh disable in this manager. Use refresh_enable=True in constructor.')
        async with self._refresh_lock:
            if self._close:
                raise Exception("Cant add refresh function in closed manager.")
            self._refreshers.append(refresh_async_func)
            if self._refresh_task is None:
                self._refresh_task = asyncio.ensure_future(
                    self.refresh(), loop=self._loop
                )

    async def refresh(self):
        while self._close is False:
            await asyncio.sleep(self._refresh_period)
            async with self._refresh_lock:
                for refresher in self._refreshers:
                    await refresher()

    async def wait_tasks(self):
        await asyncio.gather(
            *self.tasks,
            return_exceptions=True,
            loop=self._loop
        )

    async def close(self):
        self._close = True
        await self.wait_tasks()
        async with self._refresh_lock:
            if self._refresh_task:
                self._refresh_task.cancel()