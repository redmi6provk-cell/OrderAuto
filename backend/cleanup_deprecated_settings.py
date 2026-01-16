#!/usr/bin/env python3
"""
Cleanup script to remove deprecated address-related settings from system_settings table.
These settings have been moved to the dedicated addresses table.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

DEPRECATED_SETTINGS = [
    'address_template',
    'office_no_min', 
    'office_no_max',
    'name_postfix',
    'phone_prefix',
    'pincode'
]

async def cleanup_deprecated_settings():
    """Remove deprecated address settings from system_settings table"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("🧹 Cleaning up deprecated address settings from system_settings table...")
        
        # Check if any deprecated settings exist
        existing_settings = await conn.fetch('''
            SELECT setting_key FROM system_settings 
            WHERE setting_key = ANY($1)
        ''', DEPRECATED_SETTINGS)
        
        if existing_settings:
            print(f"Found {len(existing_settings)} deprecated settings to remove:")
            for setting in existing_settings:
                print(f"  - {setting['setting_key']}")
            
            # Remove deprecated settings
            deleted_count = await conn.execute('''
                DELETE FROM system_settings 
                WHERE setting_key = ANY($1)
            ''', DEPRECATED_SETTINGS)
            
            print(f"✅ Removed {deleted_count.split()[-1]} deprecated settings successfully!")
        else:
            print("✅ No deprecated settings found. Database is already clean!")
        
        # Show remaining settings
        remaining_settings = await conn.fetch('SELECT setting_key FROM system_settings ORDER BY setting_key')
        print(f"\n📋 Remaining system settings ({len(remaining_settings)}):")
        for setting in remaining_settings:
            print(f"  - {setting['setting_key']}")
            
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        return False
        
    return True

if __name__ == "__main__":
    success = asyncio.run(cleanup_deprecated_settings())
    if success:
        print("\n🎉 Cleanup completed successfully!")
        print("Address settings are now properly managed in the addresses table.")
    else:
        print("\n💥 Cleanup failed!")
