import asyncio
import asyncpg
import os
import sys

# DATABASE_URL = "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation"
# Try to get from environment first
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

async def migrate():
    print(f"Connecting to {DATABASE_URL}...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    try:
        # 1. Add automation_mode to automation_sessions
        print("Checking automation_sessions for automation_mode...")
        has_mode = await conn.fetchval("""
            SELECT count(*) FROM information_schema.columns 
            WHERE table_name = 'automation_sessions' AND column_name = 'automation_mode'
        """)
        if not has_mode:
            print("Adding automation_mode to automation_sessions...")
            await conn.execute("ALTER TABLE automation_sessions ADD COLUMN automation_mode VARCHAR(50) DEFAULT 'GROCERY'")
            print("✅ Column added.")
        else:
            print("✅ Column already exists.")

        # 2. Add automation_mode to flipkart_orders
        print("Checking flipkart_orders for automation_mode...")
        has_mode_orders = await conn.fetchval("""
            SELECT count(*) FROM information_schema.columns 
            WHERE table_name = 'flipkart_orders' AND column_name = 'automation_mode'
        """)
        if not has_mode_orders:
            print("Adding automation_mode to flipkart_orders...")
            await conn.execute("ALTER TABLE flipkart_orders ADD COLUMN automation_mode VARCHAR(50) DEFAULT 'GROCERY'")
            print("✅ Column added.")
        else:
            print("✅ Column already exists.")

        # 3. Update automation_type constraint in automation_sessions
        print("Updating automation_sessions_automation_type_check constraint...")
        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'automation_sessions_automation_type_check' 
                    AND table_name = 'automation_sessions'
                ) THEN
                    ALTER TABLE automation_sessions DROP CONSTRAINT automation_sessions_automation_type_check;
                END IF;
            END$$;
        """)
        
        # New constraint focused on actions, NOT marketplaces
        await conn.execute("""
            ALTER TABLE automation_sessions ADD CONSTRAINT automation_sessions_automation_type_check 
            CHECK (automation_type IN ('login_test', 'full_automation', 'add_address', 'add_coupon', 'remove_addresses', 'clear_cart'))
        """)
        print("✅ Constraint updated.")

        print("\n🚀 Migration successful!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
