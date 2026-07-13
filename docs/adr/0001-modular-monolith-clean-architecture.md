# ADR 0001: Use a modular monolith with Clean Architecture

- Status: Accepted
- Date: 2026-07-13

## Context

The product needs HTTP APIs, untrusted document parsing, AI-provider calls, deterministic matching, persistence, file storage, and multiple export formats. Those concerns change for different reasons. The business rules must remain testable without FastAPI, a database, an API key, or document libraries.

The MVP also needs operational simplicity. Splitting an early system into separately deployed services would add network contracts, distributed tracing, retries, deployment coordination, and eventual-consistency failure modes before load or organizational boundaries justify them.

## Decision

Build one deployable Python application as a modular monolith with these boundaries:

- `domain`: immutable entities, matching policy, recommendations, normalization, and factual-integrity rules;
- `application`: use-case services and framework-neutral ports;
- `infrastructure`: adapters for AI, parsing, persistence, storage, export, logging, and rate limiting;
- `presentation`: FastAPI routes, schemas, middleware, dependencies, and error mapping;
- `container.py`: explicit composition root and dependency injection.

Dependencies point toward the domain. The domain must not import FastAPI, Pydantic transport schemas, SQLAlchemy, OpenAI, or file-format libraries. Infrastructure implements protocols declared by the application layer. Routers remain thin and delegate use-case behavior.

Module boundaries are architectural boundaries even though they run in one process. Cross-module access should use public types and ports rather than reaching into adapter internals.

## Consequences

### Positive

- Matching and factual-integrity policies are fast, deterministic unit-test targets.
- AI, database, storage, and parsing adapters can be replaced independently.
- Local mode can exercise the complete workflow without network credentials.
- One process and one repository keep development, debugging, and deployment approachable.
- A later worker can reuse application services and ports without moving domain logic.

### Negative

- Python does not enforce module boundaries; review and tests must preserve dependency direction.
- CPU-heavy parsing and synchronous external calls share API worker resources.
- A single deployment scales all modules together.
- Database and filesystem operations cannot share one atomic transaction.

## Alternatives considered

- **Microservices now:** rejected because the MVP lacks independent scale, ownership, and availability requirements that compensate for distributed-system cost.
- **Traditional route/service/model layering:** rejected because it often couples business rules to ORM and web types.
- **Framework-owned architecture:** rejected because provider and transport details would make deterministic domain testing harder.

## Follow-up rules

- Add a new external dependency behind an application port when its behavior matters to a use case.
- Do not introduce a service boundary until measured scale, isolation, or ownership needs justify it.
- Keep architecture tests or import-boundary checks on the roadmap if module drift becomes a recurring review issue.
