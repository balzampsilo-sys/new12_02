"""Migration: Add slot_interval_minutes to services

This migration adds the ability to define custom slot intervals for each service.
Different services can have different booking intervals (30/60/90/120 minutes).

Date: 2026-02-12
"""

import asyncio
import logging

import aiosqlite

from config import DATABASE_PATH

logging.basicConfig(level=logging.INFO)


async def migrate():
    """Add slot_interval_minutes to services table"""
    logging.info("Starting migration: add slot_interval_minutes to services")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if column already exists
        async with db.execute("PRAGMA table_info(services)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "slot_interval_minutes" in column_names:
                logging.info("✅ Column 'slot_interval_minutes' already exists, skipping")
                return

        # Add the new column with default value 60
        await db.execute(
            "ALTER TABLE services ADD COLUMN slot_interval_minutes INTEGER DEFAULT 60 NOT NULL"
        )
        await db.commit()

        logging.info("✅ Added column 'slot_interval_minutes' with default value 60")

        # Update existing services to have 60-minute intervals (same as duration for backward compatibility)
        await db.execute(
            """
            UPDATE services 
            SET slot_interval_minutes = duration_minutes
            WHERE slot_interval_minutes IS NULL OR slot_interval_minutes = 0
            """
        )
        await db.commit()

        logging.info("✅ Updated existing services with matching intervals")

        # Verify
        async with db.execute("SELECT COUNT(*) FROM services") as cursor:
            count = (await cursor.fetchone())[0]
            logging.info(f"✅ Migration complete! Updated {count} services")


if __name__ == "__main__":
    asyncio.run(migrate())
