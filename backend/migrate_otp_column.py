#!/usr/bin/env python3
"""
Add otp_email column to flipkart_users table
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

async def migrate_otp_column():
    """Add otp_email column to flipkart_users table"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Check if column exists
        result = await conn.fetchval(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'flipkart_users' 
            AND column_name = 'otp_email'
            """
        )
        
        if result:
            print("✅ otp_email column already exists")
        else:
            print("➕ Adding otp_email column...")
            await conn.execute(
                "ALTER TABLE flipkart_users ADD COLUMN otp_email VARCHAR(100)"
            )
            print("✅ otp_email column added successfully")
        
        # Also make password column nullable if not already
        print("🔧 Making password column nullable...")
        await conn.execute(
            "ALTER TABLE flipkart_users ALTER COLUMN password DROP NOT NULL"
        )
        print("✅ Password column is now nullable")
        
        # Show current table structure
        print("\n📊 Current flipkart_users table structure:")
        columns = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'flipkart_users'
            ORDER BY ordinal_position
            """
        )
        
        for column in columns:
            print(f"  - {column['column_name']}: {column['data_type']} (nullable: {column['is_nullable']})")
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_otp_column())




