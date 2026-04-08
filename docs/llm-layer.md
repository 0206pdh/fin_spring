# LLM Layer

## Why The Old Design Was Not Enough

The previous normalization flow relied on one prompt that tried to do all of the following at once:

- classify the event
- infer market transmission channels
- explain the market impact
- emit parseable JSON

That approach had three structural problems:

1. Classification and explanation were coupled.
2. JSON parsing depended on best-effort text extraction.
3. The runtime path did not actually use the planned LangGraph and structured-output layer.

This update fixes that by moving the real runtime path to a layered design.

---

## Current LLM Architecture

The LLM stack is now split into four layers.

### 1. Transport Layer

File:
- `app/llm/client.py`

Responsibility:
- initialize the OpenAI-compatible SDK client
- send plain chat requests
- send strict JSON-schema chat requests
- request embeddings for semantic dedupe

Exposed methods:
- `chat()`
- `structured_chat()`
- `embedding()`

This keeps API transport details out of normalization logic.

---

### 2. Schema Layer

File:
- `app/llm/structured.py`

Responsibility:
- define the output contract for each LLM node with Pydantic
- convert those contracts into strict JSON schema
- validate every node response before it can move downstream

Node schemas:
- `ClassificationOutput`
- `ChannelOutput`
- `RationaleOutput`

Merged schema:
- `NormalizationOutput`

Why this matters:
- every node has a narrow job
- failures become local and understandable
- downstream code receives typed data instead of loose dicts

---

### 3. Orchestration Layer

File:
- `app/llm/chain.py`

Responsibility:
- define the LangGraph workflow
- execute the nodes in a stable order
- keep the state object explicit

Graph:

```text
classify -> channel -> rationale
```

#### classify node

Inputs:
- title
- sector
- published_at
- article details

Outputs:
- `event_type`
- `policy_domain`
- `risk_signal`
- `confidence`

Purpose:
- decide what happened before any explanation work begins

#### channel node

Inputs:
- classification output
- article context

Outputs:
- `rate_signal`
- `geo_signal`
- `channels`
- `regime`

Purpose:
- decide how the event propagates into FX and sector pressure

#### rationale node

Inputs:
- event classification
- chosen channels
- article context

Outputs:
- `keywords`
- `rationale`
- `sentiment`
- `sector_impacts`

Purpose:
- produce the analyst-style explanation only after classification is stable

---

### 4. Runtime Orchestration Layer

File:
- `app/llm/normalize.py`

Responsibility:
- call semantic dedupe first
- run the LangGraph chain
- normalize and guardrail outputs
- append implied channels from primary signals
- enforce rationale numeric quality
- persist embeddings
- write evaluation telemetry
- return a `NormalizedEvent`

This file is the actual runtime bridge between LLM logic and the worker/API pipeline.

---

## Full Runtime Flow

```text
RawEvent
  -> build embedding text
  -> pgvector duplicate check
  -> if duplicate and prior normalization exists:
       reuse prior normalization
     else:
       run LangGraph classify node
       run LangGraph channel node
       run LangGraph rationale node
       merge outputs
       validate and normalize fields
  -> persist embedding
  -> log evaluator row
  -> return NormalizedEvent
```

---

## Why LangGraph Is Useful Here

The current graph is linear, but LangGraph is still justified because the system now has a real orchestration boundary.

Benefits:

- the node contract is explicit
- each node can be tested independently
- future retries can target one node instead of the whole prompt
- future branching is easy to add
- observability is cleaner because the pipeline is step-shaped, not blob-shaped

This is materially different from keeping three prompts inside one function with no graph runtime.

---

## Why Strict Structured Output Matters

`structured_chat()` requests JSON that must match the node schema.

That gives us:

- less brittle parsing
- clearer failure modes
- no silent acceptance of malformed free text
- direct compatibility with Pydantic validation

The old `_safe_json()` fallback still exists at the client utility level for resilience, but the main normalization path now expects strict schema output.

---

## Semantic Dedupe

Files:
- `app/store/vector_store.py`
- `app/llm/normalize.py`

How it works:

1. Build embedding text from title plus article details.
2. Generate an embedding with `text-embedding-3-small`.
3. Query pgvector for the nearest prior event.
4. If similarity crosses the threshold and a normalized row exists, reuse that normalization.
5. Otherwise continue with a fresh LangGraph run.

Why it matters:
- repeated syndicated stories do not force full LLM cost every time
- duplicate market narratives stay consistent across similar headlines

---

## Evaluator Logging

File:
- `app/llm/evaluator.py`

Runtime integration:
- called from `app/llm/normalize.py`

Stored fields:
- `raw_event_id`
- `event_type`
- `risk_signal`
- expected risk signal
- confidence
- consistency flag
- provider
- model

Why it matters:
- confidence without calibration is weak telemetry
- consistency gives a basic production signal for drift and misclassification

---

## Packages Used

Already required by the project:

- `openai`
- `langgraph`
- `pydantic`
- `pydantic-settings`
- `psycopg`
- `redis`
- `arq`

Why each matters here:

- `openai`: transport client and embeddings
- `langgraph`: step orchestration for the LLM pipeline
- `pydantic`: strict output validation
- `psycopg`: event storage and evaluation storage
- `redis` and `arq`: async execution path so multi-step LLM work does not block HTTP

---

## What Is Still Not Done

- node-level retries are not implemented yet
- prompt/version metadata is not persisted per node
- retrieval-grounded rationale generation is not implemented yet
- the main React UI still does not expose the full LLM reasoning surface

These are next-phase improvements, not blockers for the current layered runtime.
