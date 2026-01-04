"""Team sync service for Azure AD group membership synchronization.

Syncs Azure AD security group membership to local TeamMember cache.
Uses Microsoft Graph API to fetch group members.

Configuration Required:
- AZURE_AD_TENANT_ID
- AZURE_AD_CLIENT_ID
- AZURE_AD_CLIENT_SECRET

Azure AD App Registration Required Permission:
- GroupMember.Read.All (Application permission)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.o_data_errors.o_data_error import ODataError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.database import async_session_maker
from app.models.team import Team, TeamMember
from app.models.user import User

logger = get_logger(__name__)


@dataclass
class TeamSyncResult:
    """Result of a team sync operation."""

    team_id: UUID
    team_name: str
    members_added: int = 0
    members_removed: int = 0
    members_unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    synced_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TeamSyncService:
    """Service for syncing Azure AD group membership to local cache.

    This service fetches the current membership of Azure AD security groups
    and updates the local TeamMember table to match. It handles:
    - Adding new members when they join the AD group
    - Removing members when they leave the AD group
    - Rate limiting with exponential backoff
    - Graceful degradation when not configured
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: GraphServiceClient | None = None

    def is_configured(self) -> bool:
        """Check if Azure AD is configured for team sync.

        Returns:
            True if all required Azure AD credentials are set
        """
        return bool(
            self.settings.azure_ad_tenant_id
            and self.settings.azure_ad_client_id
            and self.settings.azure_ad_client_secret
        )

    def _get_client(self) -> GraphServiceClient | None:
        """Get or create Microsoft Graph client.

        Returns:
            GraphServiceClient instance, or None if not configured
        """
        if not self.is_configured():
            logger.warning("team_sync_not_configured")
            return None

        if self._client is None:
            credential = ClientSecretCredential(
                tenant_id=self.settings.azure_ad_tenant_id,
                client_id=self.settings.azure_ad_client_id,
                client_secret=self.settings.azure_ad_client_secret,
            )
            self._client = GraphServiceClient(
                credentials=credential,
                scopes=["https://graph.microsoft.com/.default"],
            )

        return self._client

    async def _fetch_group_members_with_retry(
        self,
        client: GraphServiceClient,
        group_id: str,
        max_retries: int = 3,
    ) -> list[str]:
        """Fetch group members from Azure AD with exponential backoff.

        Args:
            client: Graph API client
            group_id: Azure AD group object ID
            max_retries: Maximum number of retries on rate limit

        Returns:
            List of Azure AD object IDs (oids) for group members

        Raises:
            Exception: If all retries exhausted or non-retryable error
        """
        member_oids: list[str] = []
        retry_count = 0
        base_delay = 1  # seconds

        while True:
            try:
                # Fetch group members using Graph API
                # Returns DirectoryObject instances (users, groups, service principals)
                members_response = await client.groups.by_group_id(
                    group_id
                ).members.get()

                if not members_response or not members_response.value:
                    return []

                # Extract OIDs from members, filtering for users only
                for member in members_response.value:
                    # Check if this is a user by looking at odata_type
                    odata_type = getattr(member, "odata_type", None)
                    if odata_type == "#microsoft.graph.user":
                        member_id = getattr(member, "id", None)
                        if member_id:
                            member_oids.append(member_id)

                # Handle pagination if needed
                next_link = getattr(members_response, "odata_next_link", None)
                while next_link:
                    # Use the next link to get more members
                    members_response = (
                        await client.groups.by_group_id(group_id)
                        .members.with_url(next_link)
                        .get()
                    )
                    if members_response and members_response.value:
                        for member in members_response.value:
                            odata_type = getattr(member, "odata_type", None)
                            if odata_type == "#microsoft.graph.user":
                                member_id = getattr(member, "id", None)
                                if member_id:
                                    member_oids.append(member_id)
                    next_link = getattr(members_response, "odata_next_link", None)

                return member_oids

            except ODataError as e:
                error_code = getattr(e.error, "code", None) if e.error else None
                status_code = getattr(e, "response_status_code", None)

                # Check for rate limiting (429 Too Many Requests)
                if status_code == 429 or error_code == "TooManyRequests":
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(
                            "team_sync_rate_limit_exhausted",
                            group_id=group_id,
                            retries=retry_count,
                        )
                        raise

                    delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
                    logger.warning(
                        "team_sync_rate_limited",
                        group_id=group_id,
                        retry_count=retry_count,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-retryable error
                raise

    async def sync_team(self, db: AsyncSession, team: Team) -> TeamSyncResult:
        """Sync a single team's membership from Azure AD.

        Fetches current group members from Azure AD and updates the local
        TeamMember table to match. Members not in AD are removed, new members
        are added.

        Args:
            db: Database session
            team: Team to sync

        Returns:
            TeamSyncResult with sync statistics
        """
        result = TeamSyncResult(
            team_id=team.id,
            team_name=team.name,
        )

        if not team.azure_ad_group_id:
            result.errors.append("Team has no Azure AD group ID configured")
            return result

        client = self._get_client()
        if not client:
            result.errors.append("Azure AD not configured")
            return result

        try:
            # Fetch current members from Azure AD
            ad_member_oids = await self._fetch_group_members_with_retry(
                client, team.azure_ad_group_id
            )

            logger.info(
                "team_sync_fetched_ad_members",
                team_id=str(team.id),
                team_name=team.name,
                ad_member_count=len(ad_member_oids),
            )

            # Fetch current local members
            existing_members_result = await db.execute(
                select(TeamMember).where(TeamMember.team_id == team.id)
            )
            existing_members = list(existing_members_result.scalars().all())

            # Build lookup of existing user_id -> TeamMember
            existing_by_user_id: dict[UUID, TeamMember] = {
                m.user_id: m for m in existing_members
            }

            # Fetch all users that match the AD OIDs
            if ad_member_oids:
                users_result = await db.execute(
                    select(User).where(User.azure_id.in_(ad_member_oids))
                )
                ad_users = list(users_result.scalars().all())
            else:
                ad_users = []

            # Build lookup of azure_id -> User
            user_by_azure_id: dict[str, User] = {u.azure_id: u for u in ad_users}

            # Determine which users should be members based on AD group
            target_user_ids: set[UUID] = {
                user_by_azure_id[oid].id
                for oid in ad_member_oids
                if oid in user_by_azure_id
            }

            current_user_ids: set[UUID] = set(existing_by_user_id.keys())

            # Calculate changes
            to_add = target_user_ids - current_user_ids
            to_remove = current_user_ids - target_user_ids
            unchanged = current_user_ids & target_user_ids

            # Remove departed members
            if to_remove:
                await db.execute(
                    delete(TeamMember).where(
                        TeamMember.team_id == team.id,
                        TeamMember.user_id.in_(to_remove),
                    )
                )
                result.members_removed = len(to_remove)

            # Add new members
            now = datetime.now(UTC)
            for user_id in to_add:
                new_member = TeamMember(
                    team_id=team.id,
                    user_id=user_id,
                    synced_at=now,
                )
                db.add(new_member)
            result.members_added = len(to_add)

            # Update synced_at for unchanged members
            for user_id in unchanged:
                member = existing_by_user_id[user_id]
                member.synced_at = now
            result.members_unchanged = len(unchanged)

            await db.flush()

            logger.info(
                "team_sync_completed",
                team_id=str(team.id),
                team_name=team.name,
                added=result.members_added,
                removed=result.members_removed,
                unchanged=result.members_unchanged,
            )

        except ODataError as e:
            error_message = str(e.error.message) if e.error else str(e)
            result.errors.append(f"Graph API error: {error_message}")
            logger.error(
                "team_sync_graph_error",
                team_id=str(team.id),
                error=error_message,
            )
        except Exception as e:
            result.errors.append(f"Unexpected error: {str(e)}")
            logger.exception(
                "team_sync_error",
                team_id=str(team.id),
                error=str(e),
            )

        return result

    async def sync_all_teams(self) -> dict:
        """Sync all teams' membership from Azure AD.

        Creates its own database session. Designed to be called from cron.

        Returns:
            Dict with overall sync results suitable for API response
        """
        if not self.is_configured():
            return {
                "status": "skipped",
                "reason": "Azure AD not configured",
                "teams_processed": 0,
                "teams_succeeded": 0,
                "teams_failed": 0,
                "total_members_added": 0,
                "total_members_removed": 0,
                "errors": [],
            }

        async with async_session_maker() as db:
            try:
                # Fetch all teams
                teams_result = await db.execute(select(Team))
                teams = list(teams_result.scalars().all())

                if not teams:
                    return {
                        "status": "success",
                        "teams_processed": 0,
                        "teams_succeeded": 0,
                        "teams_failed": 0,
                        "total_members_added": 0,
                        "total_members_removed": 0,
                        "errors": [],
                    }

                # Sync each team
                results: list[TeamSyncResult] = []
                for team in teams:
                    try:
                        sync_result = await self.sync_team(db, team)
                        results.append(sync_result)
                    except Exception as e:
                        # Isolate errors per team
                        logger.exception(
                            "team_sync_team_error",
                            team_id=str(team.id),
                            error=str(e),
                        )
                        results.append(
                            TeamSyncResult(
                                team_id=team.id,
                                team_name=team.name,
                                errors=[f"Unhandled error: {str(e)}"],
                            )
                        )

                await db.commit()

                # Aggregate results
                teams_succeeded = sum(1 for r in results if not r.errors)
                teams_failed = sum(1 for r in results if r.errors)
                total_added = sum(r.members_added for r in results)
                total_removed = sum(r.members_removed for r in results)
                all_errors: list[str] = []
                for r in results:
                    for err in r.errors:
                        all_errors.append(f"{r.team_name}: {err}")

                return {
                    "status": "success" if not teams_failed else "partial",
                    "teams_processed": len(teams),
                    "teams_succeeded": teams_succeeded,
                    "teams_failed": teams_failed,
                    "total_members_added": total_added,
                    "total_members_removed": total_removed,
                    "errors": all_errors[:10],  # Limit error count
                }

            except Exception as e:
                await db.rollback()
                logger.exception("team_sync_all_error", error=str(e))
                return {
                    "status": "error",
                    "teams_processed": 0,
                    "teams_succeeded": 0,
                    "teams_failed": 0,
                    "total_members_added": 0,
                    "total_members_removed": 0,
                    "errors": [str(e)],
                }

    def get_status(self) -> dict:
        """Get configuration status for debugging.

        Returns:
            Dict with configuration status
        """
        return {
            "configured": self.is_configured(),
            "tenant_id": bool(self.settings.azure_ad_tenant_id),
            "client_id": bool(self.settings.azure_ad_client_id),
            "client_secret": bool(self.settings.azure_ad_client_secret),
        }
