#!/usr/bin/env python3
"""
Migration script to update automation_sessions table schema
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

async def migrate_automation_sessions():
    """Migrate automation_sessions table to new schema"""
    
    print("🔄 Starting automation_sessions table migration...")
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Check if table exists and get current structure
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'automation_sessions')"
        )
        
        if table_exists:
            print("📋 Found existing automation_sessions table")
            
            # Drop and recreate the table with new schema
            print("🗑️ Dropping existing table...")
            await conn.execute("DROP TABLE IF EXISTS automation_sessions CASCADE;")
        
        # Create new automation_sessions table
        print("🆕 Creating new automation_sessions table...")
        await conn.execute('''
            CREATE TABLE automation_sessions (
                id SERIAL PRIMARY KEY,
                batch_session_id VARCHAR(100) UNIQUE NOT NULL,
                automation_type VARCHAR(50) NOT NULL CHECK (automation_type IN ('login_test', 'full_automation')),
                started_by INTEGER REFERENCES users(id),
                status VARCHAR(50) DEFAULT 'running' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
                batch_size INTEGER NOT NULL,
                total_accounts INTEGER NOT NULL,
                total_batches INTEGER NOT NULL,
                completed_batches INTEGER DEFAULT 0,
                account_range_start INTEGER NOT NULL,
                account_range_end INTEGER NOT NULL,
                total_jobs INTEGER DEFAULT 0,
                completed_jobs INTEGER DEFAULT 0,
                failed_jobs INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                config JSONB,
                error_message TEXT
            );
        ''')
        
        # Create indexes
        print("📊 Creating indexes...")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_sessions_batch_session_id ON automation_sessions(batch_session_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_sessions_automation_type ON automation_sessions(automation_type);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_by ON automation_sessions(started_by);")
        
        await conn.close()
        
        print("✅ automation_sessions table migration completed successfully!")
        print("📊 New schema includes:")
        print("   - batch_session_id (unique identifier for batch runs)")
        print("   - automation_type ('login_test' or 'full_automation')")
        print("   - batch_size, total_accounts, total_batches")
        print("   - account_range_start, account_range_end")
        print("   - job tracking (total_jobs, completed_jobs, failed_jobs)")
        print("   - batch progress (completed_batches)")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_automation_sessions())




