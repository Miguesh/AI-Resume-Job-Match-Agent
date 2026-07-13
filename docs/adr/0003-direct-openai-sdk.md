# ADR 0003: Integrate OpenAI through the official SDK without LangChain

- Status: Accepted
- Date: 2026-07-13

## Context

The current AI workflow has three bounded operations: resume extraction, job extraction, and resume optimization. Each operation is one structured request with a strict response contract. The application needs provider isolation, timeouts, retries, safe error mapping, and prompt versioning, but not agents, retrieval, tool graphs, memory, or multi-provider routing.

Adding an orchestration framework would expand dependencies and abstraction surface without reducing meaningful complexity in this workflow.

## Decision

Use the official async OpenAI Python SDK and Responses API structured parsing directly inside `OpenAIResumeIntelligence`.

- The application depends on the `ResumeIntelligence` protocol, not OpenAI types.
- Pydantic contracts validate structured provider output.
- Untrusted document content is serialized as data and separated from developer instructions.
- Provider timeouts, connection failures, rate limits, and status errors map to application exceptions.
- Prompt versions live beside reviewed prompt instructions.
- Optimized output passes through a deterministic fact guard before persistence.
- `LocalResumeIntelligence` remains the offline implementation for development and tests.

Do not add LangChain or LlamaIndex unless a future use case demonstrates orchestration complexity their abstractions materially solve. Such a framework must remain an infrastructure detail and must not enter domain scoring.

## Consequences

### Positive

- The provider boundary is small, typed, and easy to audit.
- SDK features and error types are available without framework indirection.
- Dependency and supply-chain surface is smaller.
- Tests can replace the entire provider behind one protocol.
- The deterministic local adapter keeps normal CI credential-free.

### Negative

- Provider-specific request construction is maintained in the repository.
- Switching providers requires a new adapter and contract-compatibility work.
- Retries are SDK-level; there is no workflow-level durable retry or fallback.
- OpenAI mode transfers sensitive resume/job content to an external processor.

## Alternatives considered

- **LangChain:** not selected because the current calls are direct structured transformations with no graph, tools, memory, or retrieval.
- **LlamaIndex:** not selected because the MVP has no index or retrieval workflow.
- **Provider calls inside application services:** rejected because external SDK types and failures would cross the Clean Architecture boundary.

## Revisit when

- workflows require branching tool use, durable state, or multi-step orchestration;
- multiple providers need runtime policy routing;
- retrieval/indexing becomes a product requirement;
- provider portability benefits outweigh the additional abstraction and dependency cost.
