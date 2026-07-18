from __future__ import annotations

from uuid import uuid4

from resume_matcher.infrastructure.storage import FileSystemDocumentStorage


async def test_filesystem_storage_round_trip_and_idempotent_delete(tmp_path) -> None:
    storage = FileSystemDocumentStorage(tmp_path / "uploads")
    document_id = uuid4()

    assert await storage.load(document_id) is None

    await storage.save(document_id, b"resume bytes")

    assert await storage.load(document_id) == b"resume bytes"

    await storage.delete(document_id)
    await storage.delete(document_id)

    assert await storage.load(document_id) is None
