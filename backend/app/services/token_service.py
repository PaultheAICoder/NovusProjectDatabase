"""Token service for API token generation, validation, and lifecycle management.

Provides secure token operations:
- Generating cryptographically secure tokens with SHA-256 hashing
- Validating tokens using constant-time comparison
- Managing token lifecycle (create, revoke, delete, list)
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.api_token import APIToken
from app.models.user import User
from app.schemas.api_token import APITokenCreate

logger = get_logger(__name__)

# Token prefix for easy identification (e.g., "npd_abc123...")
TOKEN_PREFIX = "npd_"


class TokenService:
    """Service for API token CRUD operations and validation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _generate_token() -> str:
        """Generate a cryptographically secure random token.

        Returns:
            Token string with prefix (e.g., "npd_abc123...")
        """
        # secrets.token_urlsafe(32) produces 43 URL-safe characters
        random_part = secrets.token_urlsafe(32)
        return f"{TOKEN_PREFIX}{random_part}"

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token using SHA-256.

        Args:
            token: Plaintext token string

        Returns:
            64-character hex digest
        """
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _get_token_prefix(token: str) -> str:
        """Extract the first 8 characters of a token for identification.

        Args:
            token: Plaintext token string

        Returns:
            First 8 characters of the token
        """
        return token[:8]

    async def create_token(
        self,
        user_id: UUID,
        data: APITokenCreate,
    ) -> tuple[str, APIToken]:
        """Create a new API token.

        Args:
            user_id: UUID of the token owner
            data: Token creation data (name, scopes, expires_at)

        Returns:
            Tuple of (plaintext_token, APIToken model)
            NOTE: The plaintext token cannot be retrieved later!
        """
        # Generate secure token
        plaintext_token = self._generate_token()
        token_hash = self._hash_token(plaintext_token)
        token_prefix = self._get_token_prefix(plaintext_token)

        # Create database record
        api_token = APIToken(
            user_id=user_id,
            name=data.name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=data.scopes,
            expires_at=data.expires_at,
            is_active=True,
        )

        self.db.add(api_token)
        await self.db.flush()
        await self.db.refresh(api_token)

        logger.info(
            "api_token_created",
            token_id=str(api_token.id),
            user_id=str(user_id),
            token_prefix=token_prefix,
            has_expiry=data.expires_at is not None,
        )

        return plaintext_token, api_token

    async def validate_token(self, token_string: str) -> User | None:
        """Validate an API token and return the associated user.

        Performs:
        1. Hash the provided token
        2. Look up by hash (uses indexed column)
        3. Check is_active and expiration
        4. Update last_used_at timestamp
        5. Return associated user

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token_string: Plaintext token to validate

        Returns:
            User model if valid, None otherwise
        """
        if not token_string:
            return None

        # Hash the provided token
        token_hash = self._hash_token(token_string)

        # Look up token by hash
        result = await self.db.execute(
            select(APIToken).where(APIToken.token_hash == token_hash)
        )
        api_token = result.scalar_one_or_none()

        if not api_token:
            logger.debug(
                "api_token_validation_failed",
                reason="token_not_found",
            )
            return None

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(api_token.token_hash, token_hash):
            logger.debug(
                "api_token_validation_failed",
                reason="hash_mismatch",
            )
            return None

        # Check if token is active
        if not api_token.is_active:
            logger.debug(
                "api_token_validation_failed",
                token_id=str(api_token.id),
                reason="token_inactive",
            )
            return None

        # Check expiration
        if api_token.expires_at and api_token.expires_at < datetime.now(UTC):
            logger.debug(
                "api_token_validation_failed",
                token_id=str(api_token.id),
                reason="token_expired",
            )
            return None

        # Update last_used_at
        api_token.last_used_at = datetime.now(UTC)
        await self.db.flush()

        # Load and return the associated user
        result = await self.db.execute(select(User).where(User.id == api_token.user_id))
        user = result.scalar_one_or_none()

        if user:
            logger.info(
                "api_token_validated",
                token_id=str(api_token.id),
                user_id=str(user.id),
            )
        else:
            logger.warning(
                "api_token_user_not_found",
                token_id=str(api_token.id),
                user_id=str(api_token.user_id),
            )

        return user

    async def revoke_token(self, token_id: UUID, user_id: UUID) -> APIToken | None:
        """Revoke (soft-disable) a token.

        Args:
            token_id: UUID of the token to revoke
            user_id: UUID of the token owner (for authorization)

        Returns:
            Updated APIToken or None if not found/unauthorized
        """
        result = await self.db.execute(
            select(APIToken).where(
                APIToken.id == token_id,
                APIToken.user_id == user_id,
            )
        )
        api_token = result.scalar_one_or_none()

        if not api_token:
            logger.debug(
                "api_token_revoke_failed",
                token_id=str(token_id),
                user_id=str(user_id),
                reason="not_found_or_unauthorized",
            )
            return None

        api_token.is_active = False
        await self.db.flush()

        logger.info(
            "api_token_revoked",
            token_id=str(token_id),
            user_id=str(user_id),
        )

        return api_token

    async def list_user_tokens(self, user_id: UUID) -> list[APIToken]:
        """List all tokens for a user (metadata only).

        Args:
            user_id: UUID of the token owner

        Returns:
            List of APIToken models (without exposing hashes)
        """
        result = await self.db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .order_by(APIToken.created_at.desc())
        )
        tokens = list(result.scalars().all())

        logger.debug(
            "api_tokens_listed",
            user_id=str(user_id),
            count=len(tokens),
        )

        return tokens

    async def delete_token(self, token_id: UUID, user_id: UUID) -> bool:
        """Hard delete a token.

        Args:
            token_id: UUID of the token to delete
            user_id: UUID of the token owner (for authorization)

        Returns:
            True if deleted, False if not found/unauthorized
        """
        result = await self.db.execute(
            select(APIToken).where(
                APIToken.id == token_id,
                APIToken.user_id == user_id,
            )
        )
        api_token = result.scalar_one_or_none()

        if not api_token:
            logger.debug(
                "api_token_delete_failed",
                token_id=str(token_id),
                user_id=str(user_id),
                reason="not_found_or_unauthorized",
            )
            return False

        await self.db.delete(api_token)
        await self.db.flush()

        logger.info(
            "api_token_deleted",
            token_id=str(token_id),
            user_id=str(user_id),
        )

        return True

    async def get_token_by_id(self, token_id: UUID, user_id: UUID) -> APIToken | None:
        """Get a specific token by ID (for the owning user).

        Args:
            token_id: UUID of the token
            user_id: UUID of the token owner (for authorization)

        Returns:
            APIToken or None if not found/unauthorized
        """
        result = await self.db.execute(
            select(APIToken).where(
                APIToken.id == token_id,
                APIToken.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
