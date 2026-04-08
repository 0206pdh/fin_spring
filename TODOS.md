# Technical Debt and Next Work

## Completed in This Update

- Removed the duplicate Spring backend.
- Replaced the old single-prompt normalization path with a real LangGraph chain.
- Switched node outputs to strict schema validation through `app/llm/structured.py`.
- Wired evaluator logging into the runtime normalization path.
- Wired pgvector semantic dedupe and embedding persistence into the runtime normalization path.

## Active Technical Debt

### Legacy startup DDL in `app/store/db.py`

`init_db()` still creates and patches tables at process startup. That was useful for fast iteration, but schema ownership should now sit entirely with Alembic.

When to act:
- before Phase 5 CI/CD hardening

What to do:
- reduce `init_db()` to connectivity/bootstrap checks only
- fail fast when migrations are missing instead of mutating schema at runtime

---

### Frontend still does not consume the full Phase 2 backend

The backend now exposes:
- live pipeline events over WebSocket
- timeline data
- event insight and rationale endpoints

The main React app still renders only the chart and heatmap pages.

When to act:
- Phase 4

What to do:
- add WebSocket client to `src/`
- add timeline and event detail panels
- remove duplicate prototype frontends and converge on one app

---

## Future Work

### Phase 6: EDGAR Grounding

Ground analyst rationale with real SEC filings via EDGAR full-text search.

Expected benefit:
- better company-specific rationale
- less unsupported narrative generation
- stronger auditability for market-impact explanations

Blocked by:
- frontend integration and deployment hardening should land first
