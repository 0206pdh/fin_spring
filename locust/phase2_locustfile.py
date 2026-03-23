"""Phase 2 Load Test — LLM Processing Throughput & Evaluator Overhead

Purpose:
    Measure the impact of the LangGraph chain + evaluator on overall throughput.
    Single LLM call vs 3-step chain: is the latency increase justified by quality?

Scenarios:
    A) InsightHeavyUser     → hits /events/insight (full LLM insight, most expensive)
    B) EvalReportUser       → hits /events/eval/report (consistency metrics read)
    C) MixedPipelineUser    → mix of read endpoints + enqueue

Run:
    # Scenario A — LLM insight concurrency limit
    locust -f locust/phase2_locustfile.py InsightHeavyUser \
        --host http://localhost:8000 \
        --users 5 --spawn-rate 1 --run-time 120s --headless

    # Scenario C — Realistic mixed load
    locust -f locust/phase2_locustfile.py MixedPipelineUser \
        --host http://localhost:8000 \
        --users 20 --spawn-rate 2 --run-time 60s --headless

Expected findings:
    - InsightHeavyUser: LLM bound at ~2-3 concurrent requests (LLM API rate limit)
    - MixedPipelineUser: Read endpoints unaffected by LLM load (async worker isolation)
    - EvalReportUser: < 50ms (pure DB aggregation)

See docs/load-tests/phase2-llm-structured.md for analysis.
"""
import random
from locust import HttpUser, task, between, constant_throughput

SAMPLE_EVENT_IDS = [
    "sample-event-001",
    "sample-event-002",
    "sample-event-003",
]


class InsightHeavyUser(HttpUser):
    """Stresses the LLM insight endpoint to find concurrency ceiling."""
    wait_time = between(1, 3)

    @task
    def get_insight(self):
        event_id = random.choice(SAMPLE_EVENT_IDS)
        with self.client.get(
            f"/events/insight?raw_event_id={event_id}",
            timeout=60,
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                resp.success()  # expected for sample IDs
            elif resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
            elif resp.elapsed.total_seconds() > 30:
                resp.failure(f"LLM timeout: {resp.elapsed.total_seconds():.1f}s")


class EvalReportUser(HttpUser):
    """Read-only: consistency report should be fast regardless of LLM load."""
    wait_time = constant_throughput(5)  # 5 req/s

    @task
    def get_eval_report(self):
        with self.client.get(
            "/events/eval/report",
            timeout=5,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            if resp.elapsed.total_seconds() > 1:
                resp.failure(f"Eval report slow: {resp.elapsed.total_seconds():.2f}s")

    @task(2)
    def read_timeline(self):
        self.client.get("/timeline?limit=20")


class MixedPipelineUser(HttpUser):
    """Realistic mix: mostly reads, occasional enqueue, check WebSocket health."""
    wait_time = between(0.2, 1.0)

    @task(5)
    def read_timeline(self):
        self.client.get("/timeline?limit=50")

    @task(5)
    def read_heatmap(self):
        self.client.get("/heatmap")

    @task(2)
    def enqueue(self):
        self.client.post(
            "/pipeline/enqueue",
            params={"limit_per_category": 3},
            timeout=3,
        )

    @task(1)
    def health(self):
        self.client.get("/health")
