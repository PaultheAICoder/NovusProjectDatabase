"""Seed script for structured tags.

Run with: python -m app.scripts.seed_tags
"""

import asyncio

from sqlalchemy import select

from app.database import async_session_maker
from app.models import Tag, TagType

# Structured tags from data-model.md
STRUCTURED_TAGS = {
    TagType.TECHNOLOGY: [
        "Wi-Fi",
        "Bluetooth",
        "BLE",
        "Zigbee",
        "NFC",
        "Cellular",
        "Thread",
        "Matter",
        "LoRa",
        "Z-Wave",
        "UWB",
        "5G",
        "LTE",
        "GPS",
    ],
    TagType.DOMAIN: [
        "Wearable",
        "Smart Home",
        "Automotive",
        "Enterprise",
        "Consumer",
        "Healthcare",
        "Industrial",
        "Retail",
        "Agriculture",
    ],
    TagType.TEST_TYPE: [
        "Interop",
        "Performance",
        "Certification",
        "Environmental",
        "Build/Bring-up",
        "Protocol",
        "Stress",
        "Regression",
        "Security",
    ],
}


async def seed_tags() -> None:
    """Seed structured tags into the database."""
    async with async_session_maker() as db:
        created = 0
        skipped = 0

        for tag_type, tag_names in STRUCTURED_TAGS.items():
            for name in tag_names:
                # Check if tag already exists
                result = await db.execute(
                    select(Tag).where(Tag.name == name, Tag.type == tag_type)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    skipped += 1
                    continue

                tag = Tag(
                    name=name,
                    type=tag_type,
                    created_by=None,  # System-created
                )
                db.add(tag)
                created += 1

        await db.commit()
        print(f"Seeded {created} tags, skipped {skipped} existing tags")


if __name__ == "__main__":
    asyncio.run(seed_tags())
