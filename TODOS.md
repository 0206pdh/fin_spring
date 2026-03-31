# Technical Debt & Future Work

## Dead Code

### `app/llm/chain.py` — LangGraph 3-node chain (unused)
**Status:** Dead code. Do not delete yet — kept for Phase 6 reference.

`chain.py` defines a LangGraph classify → channel → rationale pipeline but is never
imported by `main.py`, `worker.py`, or any other module. The actual LLM pipeline runs
through `app/llm/normalize.py` using a single MistralClient prompt.

When to act: Phase 6 multi-step reasoning upgrade. At that point, wire `chain.py`
into `normalize.py` as a drop-in replacement for `MistralClient.chat()`.

---

## Phase 6.5 — EDGAR Grounding

### Idea: Ground rationale with real SEC filings via EDGAR full-text search API

**Motivation:** Current rationale quality is limited by what the LLM "knows" about
a company at inference time. EDGAR's full-text search API (free, no key required)
lets us pull recent 8-K/10-Q snippets for the named company and inject them as
grounding context into the rationale prompt.

**Design sketch:**
1. `app/ingest/edgar.py` — extract company ticker from article title via NER or
   regex, query `https://efts.sec.gov/LATEST/search-index?q="TICKER"&dateRange=custom&startdt=...`
2. Inject top 2-3 filing excerpts into `USER_TEMPLATE` as `{edgar_context}`.
3. Rationale can now cite: "Per Apple's Q1 2024 10-Q, services revenue grew 11.3% YoY..."

**Tradeoffs:**
- Adds ~500ms latency per normalize call (EDGAR HTTP round-trip).
- EDGAR rate limit: ~10 req/sec. At batch size 10, fine.
- No key required. Public API.

**Blocked by:** Phase 5 deployment must ship first. EDGAR integration is Phase 6.5.
