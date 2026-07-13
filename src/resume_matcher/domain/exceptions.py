"""Domain and application-safe exceptions."""

from __future__ import annotations


class ResumeMatcherError(Exception):
    """Base exception that is safe to map at the API boundary."""

    code = "resume_matcher_error"


class EntityNotFoundError(ResumeMatcherError):
    code = "entity_not_found"

    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(f"{entity} '{entity_id}' was not found")
        self.entity = entity
        self.entity_id = entity_id


class InvalidDocumentError(ResumeMatcherError):
    code = "invalid_document"


class UnsupportedDocumentError(InvalidDocumentError):
    code = "unsupported_document"


class DocumentTooLargeError(InvalidDocumentError):
    code = "document_too_large"


class DocumentExtractionError(InvalidDocumentError):
    code = "document_extraction_failed"


class IntelligenceProviderError(ResumeMatcherError):
    code = "intelligence_provider_error"


class IntelligenceProviderUnavailableError(IntelligenceProviderError):
    code = "intelligence_provider_unavailable"


class FactualIntegrityError(ResumeMatcherError):
    code = "factual_integrity_error"

    def __init__(self, violations: list[str]) -> None:
        super().__init__("Optimized resume failed factual-integrity checks")
        self.violations = tuple(violations)


class ConfigurationError(ResumeMatcherError):
    code = "configuration_error"
