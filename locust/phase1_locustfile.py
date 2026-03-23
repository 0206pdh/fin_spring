"""Phase 1 Load Test — Sync vs Async Pipeline

Purpose:
    Demonstrate why we replaced the blocking /pipeline/run endpoint
    with the async /pipeline/enqueue approach.

Scenarios:
    A) sync_user  → POST /pipeline/run  (blocking, LLM calls inside)
    B) async_user → POST /pipeline/enqueue (non-blocking, enqueues job)

Run:
    # Sync baseline (before Phase 1)
    locust -f locust/phase1_locustfile.py SyncPipelineUser \
        --host http://localhost:8000 \
        --users 10 --spawn-rate 2 --run-time 60s --headless

    # Async after Phase 1
    locust -f locust/phase1_locustfile.py AsyncPipelineUser \
        --host http://localhost:8000 \
        --users 10 --spawn-rate 2 --run-time 60s --headless

Expected results:
    Sync:  P95 ~30-80s, RPS < 0.5,  error rate ~20% (timeout)
    Async: P95 < 50ms,  RPS > 50,   error rate ~0%

See docs/load-tests/phase1-sync-vs-async.md for analysis.
"""
from locust import HttpUser, task, between, constant


class SyncPipelineUser(HttpUser):
    """Simulates pre-Phase1 behavior: blocking pipeline endpoint."""
    wait_time = constant(1)

    @task
    def run_pipeline(self):
        with self.client.post(
            "/pipeline/run",
            params={"category": "business", "limit_per_category": 2},
            timeout=120,
            catch_response=True,
        ) as resp:
            if resp.elapsed.total_seconds() > 30:
                resp.failure(f"Too slow: {resp.elapsed.total_seconds():.1f}s")
            elif resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def read_timeline(self):
        self.client.get("/timeline?limit=20")

    @task(2)
    def read_heatmap(self):
        self.client.get("/heatmap")


class AsyncPipelineUser(HttpUser):
    """Simulates post-Phase1 behavior: non-blocking enqueue endpoint."""
    wait_time = between(0.1, 0.5)

    @task
    def enqueue_pipeline(self):
        with self.client.post(
            "/pipeline/enqueue",
            params={"category": "business", "limit_per_category": 2},
            timeout=5,
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 202):
                resp.failure(f"HTTP {resp.status_code}")
            elif resp.elapsed.total_seconds() > 1:
                resp.failure(f"Enqueue too slow: {resp.elapsed.total_seconds():.2f}s")

    @task(3)
    def read_timeline(self):
        self.client.get("/timeline?limit=20")

    @task(3)
    def read_heatmap(self):
        self.client.get("/heatmap")

    @task
    def health_check(self):
        self.client.get("/health")
