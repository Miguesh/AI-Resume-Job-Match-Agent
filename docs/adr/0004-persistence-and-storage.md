# ADR 0004: Use PostgreSQL and private filesystem storage behind ports

- Status: Accepted
- Date: 2026-07-13

## Context

The service persists structured profiles, raw extracted text, match evidence, optimized drafts, and original document bytes. Relational references and migrations are useful for analyses, while large opaque source files do not need to live in database rows.

Local contributors need a zero-service option. The Docker deployment needs a production-capable relational database. Future deployments may use S3-compatible encrypted object storage, so storage behavior must not leak into use cases.

## Decision

- Use async SQLAlchemy repositories behind application protocols.
- Use PostgreSQL in Docker/self-hosted deployment and SQLite for local development/tests.
- Manage deployable schema changes through Alembic.
- Persist structured profiles and analysis snapshots as JSON within relational records.
- Store original PDF/DOCX bytes in a private filesystem path behind `DocumentStorage`.
- Address stored files only by server-generated resume UUIDs, never by user filenames.
- Force the local upload directory to `0700`, stored files to `0600`, and remove temporary files after failed atomic writes.
- Hash source bytes with SHA-256 for exact duplicate detection.
- Request cascade deletion from resume/job rows to match rows through foreign keys.
- Use compensating operations around filesystem/database writes: remove a newly uploaded file after a failed database commit, and restore a deleted file if its metadata deletion cannot commit.

The initial filesystem adapter does not implement application-layer encryption. Deployments must provide encrypted volumes, encrypted backups, least-privilege access, and lifecycle management. `APP_DATA_RETENTION_DAYS` expresses intended policy but is not automatically enforced in this release.

## Consequences

### Positive

- PostgreSQL provides durable relational persistence and schema migration support.
- SQLite keeps local and automated tests self-contained.
- Original files do not inflate database JSON rows.
- Storage and repositories can be replaced without changing use cases.
- UUID filenames and safe path resolution prevent direct use of attacker filenames.

### Negative

- Database and filesystem changes are not atomic; compensation reduces common failure windows, but failed compensation still requires operational reconciliation.
- JSON profiles have weaker field-level query constraints than normalized tables.
- SQLite and PostgreSQL differ in foreign-key and concurrency behavior, so PostgreSQL integration coverage remains important.
- Local filesystem storage complicates horizontal scaling unless the volume is shared.
- Encryption, backup deletion, and automatic retention are deployment gaps.

## Alternatives considered

- **Store originals in PostgreSQL:** rejected for the MVP because binary lifecycle and object-storage migration are cleaner behind a file port.
- **S3-compatible storage immediately:** deferred to keep local/self-hosted setup small; the port preserves the migration path.
- **Fully normalized profile schema:** deferred because extraction contracts will evolve and analyses are primarily loaded as aggregates.
- **In-memory persistence:** rejected because users need durable analyses and exports.

## Follow-up rules

- Add a retention worker and deletion audit before relying on `APP_DATA_RETENTION_DAYS`.
- Add encrypted object storage for horizontally scaled or managed deployment.
- Test migrations and deletion semantics against PostgreSQL, not only SQLite.
- Treat JSON exports and backups as highly sensitive because they can contain raw source text.
