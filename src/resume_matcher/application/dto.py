"""Framework-neutral transfer objects crossing application ports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    text: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    content: bytes
    media_type: str
    filename: str
