"""Core application exception classes.

This module provides a centralized exception hierarchy for all NPD-specific
errors. All custom exceptions inherit from NovusError, enabling:
- Consistent error handling across the application
- Easy categorization of errors by type
- Structured logging with exception context

Exception Hierarchy:
    NovusError (base)
    +-- ExternalServiceError (API/service failures)
    |   +-- GraphAPIError
    |   +-- OllamaServiceError
    |   +-- JiraAPIError (defined in jira_service.py, inherits from here)
    |   +-- MondayAPIError (defined in monday_service.py, inherits from here)
    +-- DataProcessingError (data/document processing failures)
    |   +-- EmbeddingServiceError
    |   +-- DocumentProcessingError
    |   +-- AntivirusScanError
    +-- CacheError (caching failures)
    |   +-- RedisCacheError
    +-- ConfigurationError (missing/invalid configuration)
"""


class NovusError(Exception):
    """Base exception for all NPD application errors.

    All custom exceptions should inherit from this class to enable:
    - Catching all application errors with a single except clause
    - Distinguishing application errors from system errors
    - Consistent error handling and logging patterns

    Example:
        try:
            await some_operation()
        except NovusError as e:
            logger.error("application_error", error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    """

    pass


# --- Category Exceptions ---


class ExternalServiceError(NovusError):
    """Base exception for external service/API failures.

    Use this for errors when communicating with external APIs such as:
    - Microsoft Graph API
    - Ollama embedding service
    - Jira API
    - Monday.com API
    - Any third-party service

    Subclasses should be created for specific services to enable
    targeted error handling.
    """

    pass


class DataProcessingError(NovusError):
    """Base exception for data and document processing failures.

    Use this for errors during:
    - Text extraction from documents
    - Embedding generation
    - File validation and scanning
    - Data transformation/parsing

    Subclasses should be created for specific processing types.
    """

    pass


class CacheError(NovusError):
    """Base exception for caching operation failures.

    Use this for errors related to:
    - Redis connection/operation failures
    - Cache serialization errors
    - Cache key conflicts

    The application should gracefully degrade when cache operations fail.
    """

    pass


class ConfigurationError(NovusError):
    """Exception for missing or invalid configuration.

    Raised when required configuration is missing or invalid, such as:
    - Missing environment variables
    - Invalid configuration values
    - Incompatible configuration combinations

    This exception typically indicates a deployment/setup issue rather
    than a runtime error.
    """

    pass


# --- Service-Specific Exceptions ---


class GraphAPIError(ExternalServiceError):
    """Exception for Microsoft Graph API failures.

    Use for errors from Graph API operations including:
    - Email operations (reading, sending)
    - Team/group operations
    - User profile operations

    Note: SharePoint-specific errors use SharePointError hierarchy.
    """

    pass


class OllamaServiceError(ExternalServiceError):
    """Exception for Ollama embedding service failures.

    Use for errors during:
    - Embedding generation requests
    - Ollama service connectivity issues
    - Model loading/inference failures
    """

    pass


class EmbeddingServiceError(DataProcessingError):
    """Exception for embedding generation failures.

    Use for errors during embedding generation, including:
    - API request failures to embedding service
    - Invalid input text
    - Embedding dimension mismatches

    This is distinct from OllamaServiceError in that it represents
    failures in the embedding pipeline, not just the Ollama API.
    """

    pass


class DocumentProcessingError(DataProcessingError):
    """Exception for document processing failures.

    Use for errors during document text extraction such as:
    - Corrupted or invalid documents
    - Unsupported document formats
    - Password-protected files
    - Extraction timeouts

    Note: Tika-specific errors use TikaExtractionError hierarchy
    in tika_client.py.
    """

    pass


class AntivirusScanError(DataProcessingError):
    """Exception for antivirus scanning failures.

    Use for errors during file scanning such as:
    - ClamAV connectivity issues
    - Scan timeouts
    - Malware detection (should include threat name)
    """

    def __init__(
        self,
        message: str,
        threat_name: str | None = None,
    ):
        super().__init__(message)
        self.threat_name = threat_name


class RedisCacheError(CacheError):
    """Exception for Redis-specific cache failures.

    Use for errors during Redis operations such as:
    - Connection failures
    - Authentication errors
    - Command execution failures
    - Serialization errors
    """

    pass
