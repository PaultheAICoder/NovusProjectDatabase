"""Tests for TokenService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.api_token import APIToken
from app.models.user import User, UserRole
from app.schemas.api_token import APITokenCreate
from app.services.token_service import TOKEN_PREFIX, TokenService


class TestGenerateToken:
    """Tests for _generate_token static method."""

    def test_generate_token_has_correct_prefix(self):
        """Generated tokens start with the npd_ prefix."""
        token = TokenService._generate_token()
        assert token.startswith(TOKEN_PREFIX)

    def test_generate_token_has_sufficient_length(self):
        """Generated tokens are at least 43 characters (prefix + urlsafe)."""
        token = TokenService._generate_token()
        # npd_ (4) + urlsafe(32) = ~47 chars
        assert len(token) >= 40

    def test_generate_token_is_unique(self):
        """Multiple calls generate unique tokens."""
        tokens = [TokenService._generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100


class TestHashToken:
    """Tests for _hash_token static method."""

    def test_hash_token_produces_64_char_hex(self):
        """SHA-256 hash produces 64 hex characters."""
        token = "npd_test_token_value"
        hash_result = TokenService._hash_token(token)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_hash_token_is_deterministic(self):
        """Same input produces same hash."""
        token = "npd_test_token"
        hash1 = TokenService._hash_token(token)
        hash2 = TokenService._hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_inputs_different_hashes(self):
        """Different inputs produce different hashes."""
        hash1 = TokenService._hash_token("token1")
        hash2 = TokenService._hash_token("token2")
        assert hash1 != hash2


class TestGetTokenPrefix:
    """Tests for _get_token_prefix static method."""

    def test_get_token_prefix_returns_first_8_chars(self):
        """Prefix is first 8 characters."""
        token = "npd_abcdefghijklmnop"
        prefix = TokenService._get_token_prefix(token)
        assert prefix == "npd_abcd"
        assert len(prefix) == 8


class TestCreateToken:
    """Tests for create_token method."""

    @pytest.mark.asyncio
    async def test_create_token_returns_plaintext_and_model(self):
        """Create returns tuple of (plaintext, APIToken)."""
        user_id = uuid4()
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = TokenService(mock_db)
        data = APITokenCreate(name="Test Token")

        plaintext, api_token = await service.create_token(user_id, data)

        assert plaintext.startswith(TOKEN_PREFIX)
        assert mock_db.add.called
        assert mock_db.flush.called

    @pytest.mark.asyncio
    async def test_create_token_stores_hash_not_plaintext(self):
        """Token hash is stored, not plaintext."""
        user_id = uuid4()
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = TokenService(mock_db)
        data = APITokenCreate(name="Test Token", scopes=["read"])

        plaintext, _ = await service.create_token(user_id, data)

        # Verify the add call
        add_call = mock_db.add.call_args
        created_token = add_call[0][0]

        # Hash should be 64 chars (SHA-256)
        assert len(created_token.token_hash) == 64
        # Hash should not equal plaintext
        assert created_token.token_hash != plaintext
        # Prefix should be first 8 chars of plaintext
        assert created_token.token_prefix == plaintext[:8]

    @pytest.mark.asyncio
    async def test_create_token_with_expiry(self):
        """Token can be created with expiration date."""
        user_id = uuid4()
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = TokenService(mock_db)
        expiry = datetime.now(UTC) + timedelta(days=30)
        data = APITokenCreate(name="Expiring Token", expires_at=expiry)

        plaintext, _ = await service.create_token(user_id, data)

        add_call = mock_db.add.call_args
        created_token = add_call[0][0]
        assert created_token.expires_at == expiry


class TestValidateToken:
    """Tests for validate_token method."""

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_empty_token(self):
        """Empty token returns None."""
        mock_db = AsyncMock()
        service = TokenService(mock_db)

        result = await service.validate_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_none_token(self):
        """None token returns None."""
        mock_db = AsyncMock()
        service = TokenService(mock_db)

        result = await service.validate_token(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_unknown_token(self):
        """Unknown token returns None."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.validate_token("npd_unknown_token")

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_inactive_token(self):
        """Inactive token returns None."""
        mock_token = MagicMock(spec=APIToken)
        mock_token.token_hash = TokenService._hash_token("npd_test_token")
        mock_token.is_active = False
        mock_token.expires_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.validate_token("npd_test_token")

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_expired_token(self):
        """Expired token returns None."""
        mock_token = MagicMock(spec=APIToken)
        mock_token.token_hash = TokenService._hash_token("npd_test_token")
        mock_token.is_active = True
        mock_token.expires_at = datetime.now(UTC) - timedelta(days=1)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.validate_token("npd_test_token")

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_updates_last_used_at(self):
        """Valid token updates last_used_at timestamp."""
        user_id = uuid4()

        mock_token = MagicMock(spec=APIToken)
        mock_token.token_hash = TokenService._hash_token("npd_test_token")
        mock_token.is_active = True
        mock_token.expires_at = None
        mock_token.user_id = user_id
        mock_token.last_used_at = None

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.role = UserRole.USER

        mock_db = AsyncMock()
        # First call returns token, second returns user
        mock_result_token = MagicMock()
        mock_result_token.scalar_one_or_none.return_value = mock_token
        mock_result_user = MagicMock()
        mock_result_user.scalar_one_or_none.return_value = mock_user

        mock_db.execute.side_effect = [mock_result_token, mock_result_user]
        mock_db.flush = AsyncMock()

        service = TokenService(mock_db)
        result = await service.validate_token("npd_test_token")

        assert result == mock_user
        assert mock_token.last_used_at is not None
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_validate_token_returns_user_for_valid_token(self):
        """Valid token returns associated user."""
        user_id = uuid4()

        mock_token = MagicMock(spec=APIToken)
        mock_token.token_hash = TokenService._hash_token("npd_valid_token")
        mock_token.is_active = True
        mock_token.expires_at = datetime.now(UTC) + timedelta(days=30)
        mock_token.user_id = user_id

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "test@example.com"

        mock_db = AsyncMock()
        mock_result_token = MagicMock()
        mock_result_token.scalar_one_or_none.return_value = mock_token
        mock_result_user = MagicMock()
        mock_result_user.scalar_one_or_none.return_value = mock_user

        mock_db.execute.side_effect = [mock_result_token, mock_result_user]
        mock_db.flush = AsyncMock()

        service = TokenService(mock_db)
        result = await service.validate_token("npd_valid_token")

        assert result == mock_user


class TestRevokeToken:
    """Tests for revoke_token method."""

    @pytest.mark.asyncio
    async def test_revoke_token_sets_inactive(self):
        """Revoke sets is_active to False."""
        token_id = uuid4()
        user_id = uuid4()

        mock_token = MagicMock(spec=APIToken)
        mock_token.id = token_id
        mock_token.user_id = user_id
        mock_token.is_active = True

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        service = TokenService(mock_db)
        result = await service.revoke_token(token_id, user_id)

        assert result is not None
        assert mock_token.is_active is False
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_revoke_token_returns_none_for_wrong_user(self):
        """Revoke returns None if user doesn't own token."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.revoke_token(uuid4(), uuid4())

        assert result is None


class TestListUserTokens:
    """Tests for list_user_tokens method."""

    @pytest.mark.asyncio
    async def test_list_user_tokens_returns_all_user_tokens(self):
        """List returns all tokens for user."""
        user_id = uuid4()

        mock_token1 = MagicMock(spec=APIToken)
        mock_token1.id = uuid4()
        mock_token2 = MagicMock(spec=APIToken)
        mock_token2.id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_token1, mock_token2]
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        tokens = await service.list_user_tokens(user_id)

        assert len(tokens) == 2

    @pytest.mark.asyncio
    async def test_list_user_tokens_returns_empty_for_no_tokens(self):
        """List returns empty list if user has no tokens."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        tokens = await service.list_user_tokens(uuid4())

        assert tokens == []


class TestDeleteToken:
    """Tests for delete_token method."""

    @pytest.mark.asyncio
    async def test_delete_token_removes_from_database(self):
        """Delete removes token from database."""
        token_id = uuid4()
        user_id = uuid4()

        mock_token = MagicMock(spec=APIToken)
        mock_token.id = token_id
        mock_token.user_id = user_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()

        service = TokenService(mock_db)
        result = await service.delete_token(token_id, user_id)

        assert result is True
        mock_db.delete.assert_called_once_with(mock_token)

    @pytest.mark.asyncio
    async def test_delete_token_returns_false_for_wrong_user(self):
        """Delete returns False if user doesn't own token."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.delete_token(uuid4(), uuid4())

        assert result is False


class TestGetTokenById:
    """Tests for get_token_by_id method."""

    @pytest.mark.asyncio
    async def test_get_token_by_id_returns_token(self):
        """Get returns token if owned by user."""
        token_id = uuid4()
        user_id = uuid4()

        mock_token = MagicMock(spec=APIToken)
        mock_token.id = token_id
        mock_token.user_id = user_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.get_token_by_id(token_id, user_id)

        assert result == mock_token

    @pytest.mark.asyncio
    async def test_get_token_by_id_returns_none_for_wrong_user(self):
        """Get returns None if user doesn't own token."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TokenService(mock_db)
        result = await service.get_token_by_id(uuid4(), uuid4())

        assert result is None
