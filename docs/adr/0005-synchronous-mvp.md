# ADR 0005: Keep the MVP workflow synchronous

- Status: Accepted
- Date: 2026-07-13

## Context

Document extraction, structured AI calls, optimization, and export can be slow. A durable queue would improve resilience and latency handling, but it also requires a broker, worker lifecycle, job state machine, idempotency, cancellation, retries, dead-letter handling, and additional API contracts.

For the first release, the expected workload is a single-tenant MVP with modest usage. A direct request/response workflow makes behavior and failure handling easier to understand and test while product assumptions are validated.

## Decision

Run parsing, AI extraction, matching, optimization, persistence, and export synchronously within the API request that initiated them.

- OpenAI timeout and retry settings bound provider behavior.
- HTTP errors report provider failures rather than leaving an implicit background job.
- Completed resources are persisted before success is returned.
- The API exposes resources directly; there are no job-status, cancellation, or callback endpoints.
- Expensive POST routes use a local safety-net rate limiter; deployments are responsible for shared edge rate and concurrency controls.

The domain and application boundaries must remain reusable from a future worker. No business rule may depend on an active FastAPI request.

## Consequences

### Positive

- Simple API semantics: success means the requested operation completed.
- No queue or worker is required for local development and Docker Compose.
- Integration tests can cover the entire workflow in one process.
- Fewer partial states and distributed failure modes exist in the MVP.

### Negative

- Slow provider calls occupy API worker capacity.
- Client disconnects do not provide a durable result-retrieval contract.
- Retries at the HTTP layer can create duplicate jobs or matches because there are no idempotency keys.
- Multi-worker in-memory rate limits are not globally consistent.
- CPU/memory-heavy document parsing is not isolated from the API process.

## Alternatives considered

- **Redis/Celery or another task queue now:** deferred until measured latency, reliability, or scale requires durable processing.
- **Fire-and-forget tasks in the API process:** rejected because they are not durable across crashes or restarts.
- **Serverless asynchronous workflow:** deferred because it would dictate deployment architecture before a target platform is selected.

## Migration trigger

Introduce durable background jobs when one or more of these becomes true:

- normal processing approaches infrastructure request timeouts;
- concurrent work exhausts API workers or memory;
- users require progress, cancellation, or reliable retry;
- parsing needs process/container isolation;
- provider cost controls require queue-level budgets;
- horizontal scale requires globally coordinated idempotency and rate limits.

The migration should add an explicit operation state model, idempotency keys, retry classification, and a worker composition root while reusing existing application services and domain policies.
