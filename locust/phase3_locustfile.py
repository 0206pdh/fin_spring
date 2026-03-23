"""Phase 3 Load Test — Redis Cache Impact on Heatmap & Timeline

Purpose:
    Quantify the performance improvement from Redis caching on the two
    most frequently read endpoints: /heatmap and /timeline.

    Phase 3 introduced:
    - Redis cache with 30s TTL for /heatmap
    - Redis cache with 15s TTL for /timeline
    - TimescaleDB hypertable for scored_events (time-range queries)

Scenarios:
    A) NoCacheUser         — disable Redis and hit DB directly (baseline)
    B) WithCacheUser       — normal operation with Redis cache
    C) TimeSeriesQueryUser — time-range queries on scored_events (TimescaleDB benefit)

Run:
    # Baseline: no cache (set CACHE_DISABLED=1 or stop Redis)
    locust -f locust/phase3_locustfile.py NoCacheUser \
        --host http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 60s --headless

    # With cache
    locust -f locust/phase3_locustfile.py WithCacheUser \
        --host http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 60s --headless

Expected results (10,000 events in DB):
    NoCacheUser  /heatmap:  P95 ~2,300ms, DB CPU ~80%
    WithCacheUser /heatmap: P95 ~8ms,     DB CPU ~5%
    Reason: 30s TTL means 1 DB query per 30s regardless of RPS

See docs/load-tests/phase3-cache-timescale.md for detailed analysis.
"""
from locust import HttpUser, task, between, constant_throughput


class NoCacheUser(HttpUser):
    """Simulates pre-Phase3: every request hits DB directly."""
    wait_time = between(0.1, 0.5)

    @task(5)
    def heatmap_no_cache(self):
        # Add cache-busting param to bypass any proxy cache
        import time
        with self.client.get(
            f"/heatmap?_t={int(time.time())}",
            name="/heatmap [no cache]",
            timeout=10,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
            if resp.elapsed.total_seconds() > 5:
                resp.failure(f"Too slow: {resp.elapsed.total_seconds():.2f}s")

    @task(3)
    def timeline_no_cache(self):
        import time
        self.client.get(f"/timeline?limit=50&_t={int(time.time())}", name="/timeline [no cache]")

    @task(1)
    def health(self):
        self.client.get("/health")


class WithCacheUser(HttpUser):
    """Simulates Phase3: Redis cache active."""
    wait_time = between(0.05, 0.2)

    @task(5)
    def heatmap_cached(self):
        with self.client.get(
            "/heatmap",
            name="/heatmap [cached]",
            timeout=3,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
            if resp.elapsed.total_seconds() > 0.5:
                resp.failure(f"Cache miss too slow: {resp.elapsed.total_seconds():.2f}s")

    @task(3)
    def timeline_cached(self):
        self.client.get("/timeline?limit=50", name="/timeline [cached]")

    @task(2)
    def enqueue(self):
        self.client.post("/pipeline/enqueue", params={"limit_per_category": 2}, name="/pipeline/enqueue")

    @task(1)
    def health(self):
        self.client.get("/health")


class TimeSeriesQueryUser(HttpUser):
    """Tests graph endpoint (TimescaleDB time-range query)."""
    wait_time = constant_throughput(10)

    @task
    def graph_recent(self):
        with self.client.get(
            "/graph?limit=100",
            name="/graph [timescale]",
            timeout=5,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
