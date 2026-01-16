import asyncio
import asyncpg
from database import DATABASE_URL

async def update_schema():
    """
    This script drops and recreates the automation_sessions table
    to update its schema, including the new 'add_address' automation type.
    
    WARNING: This will delete all existing data in the automation_sessions table.
    """
    print("Connecting to the database...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Dropping the old 'automation_sessions' table (if it exists)...")
    await conn.execute("DROP TABLE IF EXISTS automation_sessions CASCADE;")
    
    print("Recreating the 'automation_sessions' table with the new schema...")
    await conn.execute('''
        CREATE TABLE automation_sessions (
            id SERIAL PRIMARY KEY,
            batch_session_id VARCHAR(100) UNIQUE NOT NULL,
            automation_type VARCHAR(50) NOT NULL CHECK (automation_type IN ('login_test', 'full_automation', 'add_address', 'add_coupon')),
            started_by INTEGER REFERENCES users(id),
            status VARCHAR(50) DEFAULT 'running' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
            batch_size INTEGER NOT NULL,
            total_accounts INTEGER NOT NULL,
            total_batches INTEGER NOT NULL,
            completed_batches INTEGER DEFAULT 0,
            account_range_start INTEGER,
            account_range_end INTEGER,
            total_jobs INTEGER DEFAULT 0,
            completed_jobs INTEGER DEFAULT 0,
            failed_jobs INTEGER DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            config JSONB,
            error_message TEXT
        );
    ''')
    
    print("Creating indexes on the new table...")
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(status);')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_batch_session_id ON automation_sessions(batch_session_id);')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_automation_type ON automation_sessions(automation_type);')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_by ON automation_sessions(started_by);')

    print("✅ Schema update complete!")
    await conn.close()

async def update_automation_type_constraint():
    """
    Non-destructive migration: Update automation_sessions.automation_type check constraint
    to include the new 'add_coupon' type without dropping data.
    """
    print("Connecting to the database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Altering check constraint on automation_sessions.automation_type to include 'add_coupon'...")
        # Drop existing constraint if present
        await conn.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'automation_sessions_automation_type_check'
                      AND table_name = 'automation_sessions'
                ) THEN
                    ALTER TABLE automation_sessions
                    DROP CONSTRAINT automation_sessions_automation_type_check;
                END IF;
            END$$;
            """
        )

        # Add updated constraint including 'add_coupon'
        await conn.execute(
            """
            ALTER TABLE automation_sessions
            ADD CONSTRAINT automation_sessions_automation_type_check
            CHECK (automation_type IN ('login_test', 'full_automation', 'add_address', 'add_coupon'));
            """
        )
        print("✅ Constraint updated successfully.")
    finally:
        await conn.close()

async def make_account_range_columns_nullable():
    """
    Non-destructive migration: ensure automation_sessions.account_range_start and
    automation_sessions.account_range_end are NULLABLE to support custom email selection.
    """
    print("Connecting to the database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Dropping NOT NULL on automation_sessions.account_range_start (if present)...")
        await conn.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'automation_sessions'
                      AND column_name = 'account_range_start'
                ) THEN
                    BEGIN
                        ALTER TABLE automation_sessions
                        ALTER COLUMN account_range_start DROP NOT NULL;
                    EXCEPTION WHEN others THEN
                        -- Ignore if constraint not present
                        NULL;
                    END;
                END IF;
            END$$;
            """
        )

        print("Dropping NOT NULL on automation_sessions.account_range_end (if present)...")
        await conn.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'automation_sessions'
                      AND column_name = 'account_range_end'
                ) THEN
                    BEGIN
                        ALTER TABLE automation_sessions
                        ALTER COLUMN account_range_end DROP NOT NULL;
                    EXCEPTION WHEN others THEN
                        -- Ignore if constraint not present
                        NULL;
                    END;
                END IF;
            END$$;
            """
        )
        print("✅ account_range_start and account_range_end are now nullable.")
    finally:
        await conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--update-constraint":
            asyncio.run(update_automation_type_constraint())
        elif sys.argv[1] == "--make-range-nullable":
            asyncio.run(make_account_range_columns_nullable())
        else:
            asyncio.run(update_schema())
    else:
        asyncio.run(update_schema())

