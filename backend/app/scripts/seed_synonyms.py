"""Seed script for common technology synonyms.

Run with: python -m app.scripts.seed_synonyms
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.database import async_session_maker
from app.models import Tag, TagType
from app.services.tag_synonym_service import TagSynonymService

# Common technology synonyms - each group contains synonymous terms
# First term in each group is the "canonical" form (typically the acronym)
TECHNOLOGY_SYNONYMS = [
    ["BLE", "Bluetooth Low Energy", "Bluetooth LE"],
    ["Wi-Fi", "WiFi", "Wireless LAN", "WLAN"],
    ["IoT", "Internet of Things"],
    ["ML", "Machine Learning"],
    ["AI", "Artificial Intelligence"],
    ["NFC", "Near Field Communication"],
    ["GPS", "Global Positioning System"],
    ["USB", "Universal Serial Bus"],
    ["API", "Application Programming Interface"],
    ["SDK", "Software Development Kit"],
    ["UI", "User Interface"],
    ["UX", "User Experience"],
    ["UWB", "Ultra-Wideband"],
    ["LTE", "Long Term Evolution"],
    ["5G", "Fifth Generation"],
    ["PCB", "Printed Circuit Board"],
    ["OTA", "Over-the-Air"],
    ["RTOS", "Real-Time Operating System"],
    ["MCU", "Microcontroller Unit"],
    ["SoC", "System on Chip"],
    ["UART", "Universal Asynchronous Receiver-Transmitter"],
    ["SPI", "Serial Peripheral Interface"],
    ["I2C", "Inter-Integrated Circuit"],
]

# Initialize logger at module level for use in helper functions
logger = get_logger(__name__)


async def ensure_tag_exists(
    db: AsyncSession, name: str, tag_type: TagType
) -> tuple[Tag, bool]:
    """Get existing tag or create new one if missing.

    Args:
        db: Database session
        name: Tag name
        tag_type: Tag type (e.g., TECHNOLOGY)

    Returns:
        Tuple of (Tag, was_created: bool)
    """
    result = await db.execute(select(Tag).where(Tag.name == name, Tag.type == tag_type))
    tag = result.scalar_one_or_none()

    if tag is None:
        tag = Tag(name=name, type=tag_type, created_by=None)
        db.add(tag)
        await db.flush()
        logger.info("tag_created", name=name, type=tag_type.value)
        return tag, True

    return tag, False


async def seed_synonyms() -> None:
    """Seed common technology synonyms into the database.

    This function is idempotent - it can be run multiple times safely.
    Existing synonyms are skipped gracefully.
    """
    # Configure logging for standalone script
    configure_logging()

    async with async_session_maker() as db:
        service = TagSynonymService(db)
        tags_created = 0
        synonyms_created = 0
        synonyms_skipped = 0

        for synonym_group in TECHNOLOGY_SYNONYMS:
            # Ensure all tags in the group exist
            tags: list[Tag] = []
            for name in synonym_group:
                tag, was_created = await ensure_tag_exists(db, name, TagType.TECHNOLOGY)
                if was_created:
                    tags_created += 1
                tags.append(tag)

            # Create synonym relationships between all pairs in the group
            # For a group [A, B, C], create: A~B, A~C, B~C
            for i, tag1 in enumerate(tags):
                for tag2 in tags[i + 1 :]:
                    result = await service.add_synonym(
                        tag_id=tag1.id,
                        synonym_tag_id=tag2.id,
                        confidence=1.0,  # Manual/system-created
                        created_by=None,  # System-created
                    )
                    if result:
                        synonyms_created += 1
                    else:
                        synonyms_skipped += 1

        await db.commit()

        logger.info(
            "synonyms_seeded",
            tags_created=tags_created,
            synonyms_created=synonyms_created,
            synonyms_skipped=synonyms_skipped,
        )


if __name__ == "__main__":
    asyncio.run(seed_synonyms())
