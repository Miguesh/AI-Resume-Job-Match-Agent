from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID


class FileSystemDocumentStorage:
    """Private local storage addressed only by server-generated UUIDs."""

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path.resolve()

    async def save(self, document_id: UUID, content: bytes) -> None:
        await asyncio.to_thread(self._save_sync, document_id, content)

    def _save_sync(self, document_id: UUID, content: bytes) -> None:
        self._base_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._base_path.chmod(0o700)
        target = self._safe_path(document_id)
        temporary = target.with_suffix(".tmp")
        try:
            temporary.write_bytes(content)
            temporary.chmod(0o600)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    async def load(self, document_id: UUID) -> bytes | None:
        return await asyncio.to_thread(self._load_sync, document_id)

    def _load_sync(self, document_id: UUID) -> bytes | None:
        target = self._safe_path(document_id)
        try:
            return target.read_bytes()
        except FileNotFoundError:
            return None

    async def delete(self, document_id: UUID) -> None:
        await asyncio.to_thread(self._delete_sync, document_id)

    def _delete_sync(self, document_id: UUID) -> None:
        self._safe_path(document_id).unlink(missing_ok=True)

    def _safe_path(self, document_id: UUID) -> Path:
        target = (self._base_path / f"{document_id}.bin").resolve()
        if self._base_path not in target.parents:
            raise ValueError("Resolved storage path escaped the configured base directory")
        return target
