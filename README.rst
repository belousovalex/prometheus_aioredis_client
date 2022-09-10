About
=====

Prometheus client that stored metric in Redis.
Use it for share metrics in multiprocessing application.

Use one instance Redis for metrics.

Library pass simple performance test. If your performance tests find errors or leak write about it: prometheus.aioredis.client@gmail.com

Be careful for use it in production.

Features
========

- Support pythons 3.8, 3.9, 3.10
- Support Counter
- Support Summary
- Support Histogram
- Support Gauge with auto clearing of dead processes gauge values (based on Redis expire).

Install
=======

.. code-block:: bash

    $ pip install prometheus-aioredis-client

Usage
=====

Simple aiohttp app example
----------------------

.. code-block:: python

    from aiohttp import web
    import aioredis
    import prometheus_aioredis_client as prom

    counter = prom.Counter(
        "counter", "Counter documentation"
        # global prom.REGISTRY is default of metrics registry
        # you can define another registry:
        # registry=prom.Registry(task_manager=prom.TaskManager())
        # dont forget close all using registries
    )

    registry = prom.Registry()

    async def on_start(app):
        app['redis_pool'] = await aioredis.from_url(
            "redis://localhost:6380",
        )
        # setup redis connection in registry
        # all metrics in this registry will use this connection
        prom.REGISTRY.set_redis(app['redis_pool'])

    async def on_stop(app):
        # wait for closing all tasks and delete gauge metric values
        await prom.REGISTRY.cleanup_and_close()
        await app['redis_pool'].close()

    async def inc(r):
        # create future and put it in event loop
        counter.inc()
        return web.Response(body=(await prom.REGISTRY.output()), content_type='text')

    async def a_inc(r):
        # wait while increment value
        await counter.a_inc()
        return web.Response(body=(await prom.REGISTRY.output()), content_type='text')

    if __name__ == '__main__':
        app = web.Application()
        app.router.add_get("/inc", inc)
        app.router.add_get("/a_inc", a_inc)
        app.on_startup.append(on_start)
        app.on_cleanup.append(on_stop)
        web.run_app(app)


Counter
-------

Counter based on atomic "incrby" command.
All processes increment one value in Redis.

.. code-block:: python

    import prometheus_aioredis_client as prom

    c = prom.Counter(
        "my_first_counter" # name of metric
        "Docstring for counter"
    )

    async def some_func():
        # you can wait incrementation
        await c.a_inc(2)
        # or make future
        c.inc(1)

    # counter with labels
    cl = prom.Counter(
        "counter_with_labels"
        "Docstring for counter"
        ['one', 'two']
    )

    async def some_func2():
        c1.labels("first", "second").inc()
        c1.labels("first", "another").inc()


You can call Redis commands `keys my_first_counter*` and `keys counter_with_labels*`
for watch all created keys.


Summary
-------

Its like a Counter. All processes increment one value.

.. code-block:: python

    import prometheus_aioredis_client as prom

    s = prom.Summary(
        "my_summary"
        "Docstring for counter",
        ["label"]
    )

    async def some_func():
        s.labels(label="something").observe(1.2)


Histogram
---------

.. code-block:: python

    import prometheus_aioredis_client as prom

    h = prom.Histogram(
        "my_histogram"
        "Docstring for counter",
        [1, 20, 25.5]
    )

    async def some_func():
        # Buckets '20' and '25.5' will be incremented.
        # Bucket '1' stay zero value.
        s.observe(1.2)


Gauge
-----

All gauge metric of all processes got unique identifier.
You can see this identifier in label `gauge_index`.

Gauge index is not a PID. It is simple Redis counter.

If you want stop process you should make `await Registry.cleanup_and_close()` before.
This function wait all futures and drop gauge metrics which relate to the process.

If you use gunicorn `max_requests` or uwsgi `harakiri` `cleanup_and_close` will not called.

But it is not problem because gauge metrics set
with expire param and after expire period will be deleted.

Expire period can be set in Gauge constructor:

.. code-block:: python

    import prometheus_aioredis_client as prom

    h = prom.Gauge(
        "my_gauge"
        "Docstring",
        expire=20 # expire value after 20 seconds
    )

    async def some_func():
        s.set(1.2)

What happen if you set gauge metric less than once every 20 seconds?

Everything will be fine because Registry.task_manager contains
refresh coroutine. This coroutine refresh all gauge values every N seconds.

N should be less then smallest `expire` param.

Default expire for Gauge metrics 60 seconds. Default refresh period 30 seconds.

You can define refresh period:

.. code-block:: python

    import prometheus_aioredis_client as prom
    prom.REGISTRY.task_manager.set_refresh_period(10)

