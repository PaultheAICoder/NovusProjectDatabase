"""Background sync service for Monday.com integration.

This module provides background sync functions for pushing NPD changes
to Monday.com. Functions create their own database session since
FastAPI BackgroundTasks run after the response is sent.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.core.logging import get_logger
from app.database import async_session_maker
from app.models.contact import Contact
from app.models.monday_sync import (
    RecordSyncStatus,
    SyncDirection,
    SyncQueueDirection,
    SyncQueueOperation,
)
from app.models.organization import Organization
from app.services.monday_service import (
    MondayAPIError,
    MondayColumnFormatter,
    MondayService,
)

logger = get_logger(__name__)
settings = get_settings()


def _build_contact_column_values(contact: Contact) -> dict:
    """Build Monday.com column values from a Contact.

    Maps NPD contact fields to Monday.com column format.
    Note: The item name (contact.name) is passed separately to create_item/update_item.

    Args:
        contact: The Contact model instance

    Returns:
        Dict of column_id -> formatted value
    """
    column_values = {}

    # Email column
    if contact.email:
        column_values["email"] = MondayColumnFormatter.format_email(contact.email)

    # Phone column
    if contact.phone:
        column_values["phone"] = MondayColumnFormatter.format_phone(contact.phone)

    # Role/Title as text column
    if contact.role_title:
        column_values["role_title"] = MondayColumnFormatter.format_text(
            contact.role_title
        )

    # Notes as text column
    if contact.notes:
        column_values["notes"] = MondayColumnFormatter.format_text(contact.notes)

    return column_values


def _build_organization_column_values(org: Organization) -> dict:
    """Build Monday.com column values from an Organization.

    Maps NPD organization fields to Monday.com column format.
    Note: The item name (org.name) is passed separately to create_item/update_item.

    Args:
        org: The Organization model instance

    Returns:
        Dict of column_id -> formatted value
    """
    column_values = {}

    # Notes as text column
    if org.notes:
        column_values["notes"] = MondayColumnFormatter.format_text(org.notes)

    # Address fields could be combined into a text column
    address_parts = []
    if org.address_street:
        address_parts.append(org.address_street)
    if org.address_city:
        address_parts.append(org.address_city)
    if org.address_state:
        address_parts.append(org.address_state)
    if org.address_zip:
        address_parts.append(org.address_zip)
    if org.address_country:
        address_parts.append(org.address_country)

    if address_parts:
        column_values["address"] = MondayColumnFormatter.format_text(
            ", ".join(address_parts)
        )

    return column_values


async def sync_contact_to_monday(contact_id: UUID) -> None:
    """Sync a contact to Monday.com in the background.

    This function is designed to be called from FastAPI BackgroundTasks.
    It creates its own database session since the original request session
    is closed when this runs.

    The sync respects the contact's sync_enabled flag and sync_direction setting.
    On success, updates sync_status to SYNCED and monday_last_synced timestamp.
    On failure, sets sync_status to PENDING and logs the error (does not raise).

    Args:
        contact_id: The UUID of the contact to sync
    """
    logger.info(
        "sync_contact_to_monday_started",
        contact_id=str(contact_id),
    )

    # Check if Monday.com is configured with a contacts board
    if not settings.is_monday_configured:
        logger.debug(
            "sync_contact_skipped_monday_not_configured",
            contact_id=str(contact_id),
        )
        return

    if not settings.monday_contacts_board_id:
        logger.debug(
            "sync_contact_skipped_no_board_id",
            contact_id=str(contact_id),
        )
        return

    async with async_session_maker() as db:
        try:
            # Fetch the contact
            result = await db.execute(select(Contact).where(Contact.id == contact_id))
            contact = result.scalar_one_or_none()

            if not contact:
                logger.error(
                    "contact_not_found_for_sync",
                    contact_id=str(contact_id),
                )
                return

            # Check if sync is enabled for this contact
            if not contact.sync_enabled:
                logger.debug(
                    "sync_contact_skipped_disabled",
                    contact_id=str(contact_id),
                )
                return

            # Check sync direction - skip if sync is from Monday to NPD only
            if contact.sync_direction in (
                SyncDirection.MONDAY_TO_NPD,
                SyncDirection.NONE,
            ):
                logger.debug(
                    "sync_contact_skipped_direction",
                    contact_id=str(contact_id),
                    sync_direction=contact.sync_direction.value,
                )
                return

            # Build column values for Monday.com
            column_values = _build_contact_column_values(contact)

            # Create MondayService instance with our db session
            monday_service = MondayService(db)

            try:
                if contact.monday_id:
                    # Update existing Monday item
                    await monday_service.update_item(
                        board_id=settings.monday_contacts_board_id,
                        item_id=contact.monday_id,
                        column_values=column_values,
                    )
                    logger.info(
                        "contact_synced_to_monday_updated",
                        contact_id=str(contact_id),
                        monday_id=contact.monday_id,
                    )
                else:
                    # Create new Monday item
                    result_item = await monday_service.create_item(
                        board_id=settings.monday_contacts_board_id,
                        item_name=contact.name,
                        column_values=column_values,
                    )
                    # Store the Monday item ID on the contact
                    contact.monday_id = result_item.get("id")
                    logger.info(
                        "contact_synced_to_monday_created",
                        contact_id=str(contact_id),
                        monday_id=contact.monday_id,
                    )

                # Update sync status on success
                contact.sync_status = RecordSyncStatus.SYNCED
                contact.monday_last_synced = datetime.now(UTC)
                await db.commit()

                logger.info(
                    "sync_contact_to_monday_completed",
                    contact_id=str(contact_id),
                    monday_id=contact.monday_id,
                )

            except MondayAPIError as api_error:
                # API call failed - enqueue for retry
                await db.rollback()
                error_msg = str(api_error)
                logger.error(
                    "sync_contact_to_monday_api_failed",
                    contact_id=str(contact_id),
                    error=error_msg,
                )

                # Determine operation type
                operation = (
                    SyncQueueOperation.UPDATE
                    if contact.monday_id
                    else SyncQueueOperation.CREATE
                )

                # Enqueue for retry
                try:
                    # Import here to avoid circular imports
                    from app.services.sync_queue_service import SyncQueueService

                    async with async_session_maker() as queue_db:
                        queue_service = SyncQueueService(queue_db)
                        await queue_service.enqueue(
                            entity_type="contact",
                            entity_id=contact_id,
                            direction=SyncQueueDirection.TO_MONDAY,
                            operation=operation,
                            error_message=error_msg,
                        )
                        await queue_db.commit()

                    logger.info(
                        "sync_contact_queued_for_retry",
                        contact_id=str(contact_id),
                    )
                except SQLAlchemyError as queue_error:
                    logger.exception(
                        "failed_to_queue_contact_sync",
                        contact_id=str(contact_id),
                        error=str(queue_error),
                    )

                # Still update sync status to PENDING
                try:
                    async with async_session_maker() as error_db:
                        result = await error_db.execute(
                            select(Contact).where(Contact.id == contact_id)
                        )
                        contact = result.scalar_one_or_none()
                        if contact:
                            contact.sync_status = RecordSyncStatus.PENDING
                            await error_db.commit()
                except SQLAlchemyError as inner_error:
                    logger.exception(
                        "failed_to_update_contact_sync_status",
                        contact_id=str(contact_id),
                        error=str(inner_error),
                    )
            finally:
                await monday_service.close()

        except Exception as e:
            logger.exception(
                "sync_contact_to_monday_failed",
                contact_id=str(contact_id),
                error=str(e),
            )


async def sync_organization_to_monday(organization_id: UUID) -> None:
    """Sync an organization to Monday.com in the background.

    This function is designed to be called from FastAPI BackgroundTasks.
    It creates its own database session since the original request session
    is closed when this runs.

    The sync respects the organization's sync_enabled flag and sync_direction setting.
    On success, updates sync_status to SYNCED and monday_last_synced timestamp.
    On failure, sets sync_status to PENDING and logs the error (does not raise).

    Args:
        organization_id: The UUID of the organization to sync
    """
    logger.info(
        "sync_organization_to_monday_started",
        organization_id=str(organization_id),
    )

    # Check if Monday.com is configured with an organizations board
    if not settings.is_monday_configured:
        logger.debug(
            "sync_organization_skipped_monday_not_configured",
            organization_id=str(organization_id),
        )
        return

    if not settings.monday_organizations_board_id:
        logger.debug(
            "sync_organization_skipped_no_board_id",
            organization_id=str(organization_id),
        )
        return

    async with async_session_maker() as db:
        try:
            # Fetch the organization
            result = await db.execute(
                select(Organization).where(Organization.id == organization_id)
            )
            org = result.scalar_one_or_none()

            if not org:
                logger.error(
                    "organization_not_found_for_sync",
                    organization_id=str(organization_id),
                )
                return

            # Check if sync is enabled for this organization
            if not org.sync_enabled:
                logger.debug(
                    "sync_organization_skipped_disabled",
                    organization_id=str(organization_id),
                )
                return

            # Check sync direction - skip if sync is from Monday to NPD only
            if org.sync_direction in (SyncDirection.MONDAY_TO_NPD, SyncDirection.NONE):
                logger.debug(
                    "sync_organization_skipped_direction",
                    organization_id=str(organization_id),
                    sync_direction=org.sync_direction.value,
                )
                return

            # Build column values for Monday.com
            column_values = _build_organization_column_values(org)

            # Create MondayService instance with our db session
            monday_service = MondayService(db)

            try:
                if org.monday_id:
                    # Update existing Monday item
                    await monday_service.update_item(
                        board_id=settings.monday_organizations_board_id,
                        item_id=org.monday_id,
                        column_values=column_values,
                    )
                    logger.info(
                        "organization_synced_to_monday_updated",
                        organization_id=str(organization_id),
                        monday_id=org.monday_id,
                    )
                else:
                    # Create new Monday item
                    result_item = await monday_service.create_item(
                        board_id=settings.monday_organizations_board_id,
                        item_name=org.name,
                        column_values=column_values,
                    )
                    # Store the Monday item ID on the organization
                    org.monday_id = result_item.get("id")
                    logger.info(
                        "organization_synced_to_monday_created",
                        organization_id=str(organization_id),
                        monday_id=org.monday_id,
                    )

                # Update sync status on success
                org.sync_status = RecordSyncStatus.SYNCED
                org.monday_last_synced = datetime.now(UTC)
                await db.commit()

                logger.info(
                    "sync_organization_to_monday_completed",
                    organization_id=str(organization_id),
                    monday_id=org.monday_id,
                )

            except MondayAPIError as api_error:
                # API call failed - enqueue for retry
                await db.rollback()
                error_msg = str(api_error)
                logger.error(
                    "sync_organization_to_monday_api_failed",
                    organization_id=str(organization_id),
                    error=error_msg,
                )

                # Determine operation type
                operation = (
                    SyncQueueOperation.UPDATE
                    if org.monday_id
                    else SyncQueueOperation.CREATE
                )

                # Enqueue for retry
                try:
                    # Import here to avoid circular imports
                    from app.services.sync_queue_service import SyncQueueService

                    async with async_session_maker() as queue_db:
                        queue_service = SyncQueueService(queue_db)
                        await queue_service.enqueue(
                            entity_type="organization",
                            entity_id=organization_id,
                            direction=SyncQueueDirection.TO_MONDAY,
                            operation=operation,
                            error_message=error_msg,
                        )
                        await queue_db.commit()

                    logger.info(
                        "sync_organization_queued_for_retry",
                        organization_id=str(organization_id),
                    )
                except SQLAlchemyError as queue_error:
                    logger.exception(
                        "failed_to_queue_organization_sync",
                        organization_id=str(organization_id),
                        error=str(queue_error),
                    )

                # Still update sync status to PENDING
                try:
                    async with async_session_maker() as error_db:
                        result = await error_db.execute(
                            select(Organization).where(
                                Organization.id == organization_id
                            )
                        )
                        org = result.scalar_one_or_none()
                        if org:
                            org.sync_status = RecordSyncStatus.PENDING
                            await error_db.commit()
                except SQLAlchemyError as inner_error:
                    logger.exception(
                        "failed_to_update_organization_sync_status",
                        organization_id=str(organization_id),
                        error=str(inner_error),
                    )
            finally:
                await monday_service.close()

        except Exception as e:
            logger.exception(
                "sync_organization_to_monday_failed",
                organization_id=str(organization_id),
                error=str(e),
            )
