"""Tests for exception hierarchy.

Validates that all custom exceptions inherit correctly and that
catching base exceptions properly catches all children.
"""

import pytest

from app.core.exceptions import (
    AntivirusScanError,
    CacheError,
    ConfigurationError,
    DataProcessingError,
    DocumentProcessingError,
    EmbeddingServiceError,
    ExternalServiceError,
    GraphAPIError,
    NovusError,
    OllamaServiceError,
    RedisCacheError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_novus_error_is_base(self):
        """NovusError is the base exception class."""
        assert issubclass(NovusError, Exception)

    def test_external_service_error_inherits_from_novus(self):
        """ExternalServiceError inherits from NovusError."""
        assert issubclass(ExternalServiceError, NovusError)

    def test_data_processing_error_inherits_from_novus(self):
        """DataProcessingError inherits from NovusError."""
        assert issubclass(DataProcessingError, NovusError)

    def test_cache_error_inherits_from_novus(self):
        """CacheError inherits from NovusError."""
        assert issubclass(CacheError, NovusError)

    def test_configuration_error_inherits_from_novus(self):
        """ConfigurationError inherits from NovusError."""
        assert issubclass(ConfigurationError, NovusError)

    def test_graph_api_error_inherits_from_external_service(self):
        """GraphAPIError inherits from ExternalServiceError."""
        assert issubclass(GraphAPIError, ExternalServiceError)
        assert issubclass(GraphAPIError, NovusError)

    def test_ollama_service_error_inherits_from_external_service(self):
        """OllamaServiceError inherits from ExternalServiceError."""
        assert issubclass(OllamaServiceError, ExternalServiceError)
        assert issubclass(OllamaServiceError, NovusError)

    def test_embedding_service_error_inherits_from_data_processing(self):
        """EmbeddingServiceError inherits from DataProcessingError."""
        assert issubclass(EmbeddingServiceError, DataProcessingError)
        assert issubclass(EmbeddingServiceError, NovusError)

    def test_document_processing_error_inherits_from_data_processing(self):
        """DocumentProcessingError inherits from DataProcessingError."""
        assert issubclass(DocumentProcessingError, DataProcessingError)
        assert issubclass(DocumentProcessingError, NovusError)

    def test_antivirus_scan_error_inherits_from_data_processing(self):
        """AntivirusScanError inherits from DataProcessingError."""
        assert issubclass(AntivirusScanError, DataProcessingError)
        assert issubclass(AntivirusScanError, NovusError)

    def test_redis_cache_error_inherits_from_cache(self):
        """RedisCacheError inherits from CacheError."""
        assert issubclass(RedisCacheError, CacheError)
        assert issubclass(RedisCacheError, NovusError)


class TestExceptionCatching:
    """Tests for exception catching behavior."""

    def test_catching_novus_catches_all_children(self):
        """Catching NovusError catches all child exceptions."""
        exceptions_to_test = [
            ExternalServiceError("test"),
            DataProcessingError("test"),
            CacheError("test"),
            ConfigurationError("test"),
            GraphAPIError("test"),
            OllamaServiceError("test"),
            EmbeddingServiceError("test"),
            DocumentProcessingError("test"),
            RedisCacheError("test"),
        ]

        for exc in exceptions_to_test:
            try:
                raise exc
            except NovusError:
                pass  # Should catch
            else:
                pytest.fail(f"{type(exc).__name__} was not caught by NovusError")

    def test_catching_external_service_catches_children(self):
        """Catching ExternalServiceError catches its children."""
        try:
            raise GraphAPIError("test")
        except ExternalServiceError:
            pass  # Should catch

        try:
            raise OllamaServiceError("test")
        except ExternalServiceError:
            pass  # Should catch

    def test_catching_data_processing_catches_children(self):
        """Catching DataProcessingError catches its children."""
        try:
            raise EmbeddingServiceError("test")
        except DataProcessingError:
            pass  # Should catch

        try:
            raise DocumentProcessingError("test")
        except DataProcessingError:
            pass  # Should catch

    def test_catching_cache_catches_children(self):
        """Catching CacheError catches its children."""
        try:
            raise RedisCacheError("test")
        except CacheError:
            pass  # Should catch


class TestAntivirusScanErrorAttributes:
    """Tests for AntivirusScanError with threat_name attribute."""

    def test_antivirus_error_with_threat_name(self):
        """AntivirusScanError stores threat_name."""
        error = AntivirusScanError("Malware detected", threat_name="EICAR-Test")
        assert str(error) == "Malware detected"
        assert error.threat_name == "EICAR-Test"

    def test_antivirus_error_without_threat_name(self):
        """AntivirusScanError works without threat_name."""
        error = AntivirusScanError("Scan failed")
        assert str(error) == "Scan failed"
        assert error.threat_name is None
