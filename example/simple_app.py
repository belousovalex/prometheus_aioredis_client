import aioredis
from aiohttp import web
from prometheus_aioredis_client import (
    Counter, Histogram, Summary, Gauge,
    REGISTRY
)

counter = Counter("simple_counter", "Simple Counter documentation")
counter_with_labels = Counter(
    "simple_counter_with_labels",
    "Counter with labels documentation",
    labelnames=['name', ]
)

summary = Summary(
    "simple_summary",
    "Simple Summary Documentation"
)
summary_with_labels = Summary(
    "simple_summary_with_labels",
    "Summary with labels Documentation",
    ["name"]
)

histogram = Histogram(
    "simple_histogram",
    "Simple Histogram Documentation",
    buckets=[0, 100, 200]
)
histogram_with_labels = Histogram(
    "simple_histogram_with_labels",
    "Histogram with labels Documentation",
    ["name"],
    buckets=[0, 100, 200]
)

gauge = Gauge(
    "simple_gauge",
    "Simple Gauge Documentation",
)
gauge_with_labels = Gauge(
    "simple_gauge_with_labels",
    "Gauge with labels Documentation",
    ["name"],
)


async def counter_view(request):
    labelname = request.match_info.get('labelname')
    if labelname is None:
        counter.inc()
    else:
        counter_with_labels.labels(name=labelname).inc()
    return web.Response(
        body=b"counter",
        content_type='text'
    )


async def summary_view(request):
    labelname = request.match_info.get('labelname')
    value = float(request.match_info.get('value'))
    if labelname is None:
        summary.observe(float(value))
    else:
        summary_with_labels.labels(name=labelname).observe(float(value))
    return web.Response(
        body="summary",
        content_type='text'
    )


async def histogram_view(request):
    labelname = request.match_info.get('labelname')
    value = float(request.match_info.get('value'))
    if labelname is None:
        histogram.observe(value)
    else:
        histogram_with_labels.labels(name=labelname).observe(value)
    return web.Response(
        body=b'histogram',
        content_type='text'
    )


async def gauge_view(request):
    labelname = request.match_info.get('labelname')
    value = float(request.match_info.get('value'))
    if labelname is None:
        await gauge.a_set(value)
    else:
        await gauge_with_labels.labels(name=labelname).a_set(value)
    return web.Response(
        body=b"gauge",
        content_type='text'
    )

async def metrics_view(request):
    return web.Response(body=(await REGISTRY.output()), content_type='text')


async def prometheus_init(app):
    app['redis_pool'] = await aioredis.create_redis_pool(
        "redis://localhost:6380",
        timeout=15,
        maxsize=500,
    )
    REGISTRY.set_redis(
        redis=app['redis_pool'],
    )


async def prometheus_clear(app):
    await REGISTRY.cleanup_and_close()
    app['redis_pool'].close()
    await app['redis_pool'].wait_closed()

def init_app():
    app = web.Application()

    app.router.add_get("/counter/{labelname}", counter_view)
    app.router.add_get("/counter", counter_view)
    app.router.add_get("/summary/{labelname}/{value}", summary_view)
    app.router.add_get("/summary/{value}", summary_view)
    app.router.add_get("/histogram/{labelname}/{value}", histogram_view)
    app.router.add_get("/histogram/{value}", histogram_view)
    app.router.add_get("/gauge/{labelname}/{value}", gauge_view)
    app.router.add_get("/gauge/{value}", gauge_view)
    app.router.add_get("/metrics", metrics_view)

    app.on_startup.append(prometheus_init)
    app.on_cleanup.append(prometheus_clear)


    return app

app = init_app()

if __name__ == "__main__":
    web.run_app(app)
