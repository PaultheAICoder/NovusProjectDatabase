"""API Token management endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.rate_limit import admin_limit, crud_limit, limiter
from app.schemas.api_token import (
    APITokenCreate,
    APITokenCreateResponse,
    APITokenListResponse,
    APITokenResponse,
    APITokenUpdate,
)
from app.services.token_service import TokenService

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.post(
    "", response_model=APITokenCreateResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(crud_limit)
async def create_token(
    request: Request,
    data: APITokenCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> APITokenCreateResponse:
    """Create a new API token.

    Returns the plaintext token ONLY ONCE. Store it securely as it
    cannot be retrieved again.

    Security note: Consider setting an expiration date for tokens.
    """
    service = TokenService(db)
    plaintext_token, api_token = await service.create_token(
        user_id=current_user.id,
        data=data,
    )

    return APITokenCreateResponse(
        token=plaintext_token,
        token_info=APITokenResponse.model_validate(api_token),
    )


@router.get("", response_model=APITokenListResponse)
@limiter.limit(crud_limit)
async def list_tokens(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> APITokenListResponse:
    """List all tokens for the current user.

    Returns token metadata only (no secrets). Tokens are ordered by
    creation date (newest first).
    """
    service = TokenService(db)
    tokens = await service.list_user_tokens(current_user.id)

    # Apply pagination in memory (list is typically small)
    total = len(tokens)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = tokens[start:end]

    return APITokenListResponse(
        items=[APITokenResponse.model_validate(t) for t in paginated],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{token_id}", response_model=APITokenResponse)
@limiter.limit(crud_limit)
async def get_token(
    request: Request,
    token_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> APITokenResponse:
    """Get details of a specific token.

    Only returns tokens owned by the current user.
    """
    service = TokenService(db)
    api_token = await service.get_token_by_id(token_id, current_user.id)

    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )

    return APITokenResponse.model_validate(api_token)


@router.patch("/{token_id}", response_model=APITokenResponse)
@limiter.limit(crud_limit)
async def update_token(
    request: Request,
    token_id: UUID,
    data: APITokenUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> APITokenResponse:
    """Update token metadata (name or active status).

    Only the token owner can update their tokens.
    """
    service = TokenService(db)
    api_token = await service.update_token(
        token_id=token_id,
        user_id=current_user.id,
        name=data.name,
        is_active=data.is_active,
    )

    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )

    return APITokenResponse.model_validate(api_token)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(crud_limit)
async def delete_token(
    request: Request,
    token_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete (revoke) a token permanently.

    This action cannot be undone. The token will immediately stop
    working for authentication.
    """
    service = TokenService(db)
    deleted = await service.delete_token(token_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )


# ============== Admin Token Management (Admin Only) ==============

admin_router = APIRouter(prefix="/admin/tokens", tags=["admin"])


@admin_router.get("", response_model=APITokenListResponse)
@limiter.limit(admin_limit)
async def admin_list_tokens(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: UUID | None = Query(None, description="Filter by user ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
) -> APITokenListResponse:
    """List all tokens across all users. Admin only.

    Supports filtering by user_id and active status.
    """
    service = TokenService(db)
    tokens, total = await service.list_all_tokens(
        page=page,
        page_size=page_size,
        user_id=user_id,
        is_active=is_active,
    )

    return APITokenListResponse(
        items=[APITokenResponse.model_validate(t) for t in tokens],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(admin_limit)
async def admin_delete_token(
    request: Request,
    token_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Delete any token (admin override). Admin only.

    Use this to revoke compromised tokens or clean up inactive accounts.
    """
    service = TokenService(db)
    deleted = await service.admin_delete_token(token_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
