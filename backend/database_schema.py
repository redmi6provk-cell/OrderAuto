#!/usr/bin/env python3
"""
Database Schema Creation Script for Flipkart Automation System
Run this script to create all necessary tables in PostgreSQL
"""

import asyncio
import asyncpg
import os
from datetime import datetime
from typing import Optional

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

async def create_database_schema():
    """Create all tables for the Flipkart automation system"""
    
    # Parse DATABASE_URL for connection
    # Format: postgresql://user:password@host:port/database
    url_parts = DATABASE_URL.replace("postgresql://", "").split("/")
    db_name = url_parts[1] if len(url_parts) > 1 else "flipkart_automation"
    host_part = url_parts[0].split("@")
    user_pass = host_part[0].split(":")
    host_port = host_part[1].split(":")
    
    user = user_pass[0] if len(user_pass) > 0 else "flipkart_admin"
    password = user_pass[1] if len(user_pass) > 1 else "flipkart_secure_2024"
    host = host_port[0] if len(host_port) > 0 else "localhost"
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database=db_name
    )
    
    try:
        # Create users table (for internal app users)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create flipkart_users table (Flipkart account credentials)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS flipkart_users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255),  -- Optional, for OTP-based login
                cookies TEXT,
                proxy_config JSONB,
                is_active BOOLEAN DEFAULT TRUE,
                last_login TIMESTAMP,
                login_attempts INTEGER DEFAULT 0,
                otp_email VARCHAR(100), -- Email where OTP is received
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create flipkart_products table (Product configurations)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS flipkart_products (
                id SERIAL PRIMARY KEY,
                product_link VARCHAR(1500) NOT NULL,
                product_name VARCHAR(200),
                quantity INTEGER DEFAULT 1,
                price_cap DECIMAL(10, 2),
                is_active BOOLEAN DEFAULT TRUE,
                check_interval INTEGER DEFAULT 300, -- seconds
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT quantity_positive CHECK (quantity > 0),
                CONSTRAINT price_cap_positive CHECK (price_cap IS NULL OR price_cap > 0)
            );
        ''')
        
        # Create flipkart_orders table (Order tracking)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS flipkart_orders (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES flipkart_products(id),
                flipkart_user_id INTEGER REFERENCES flipkart_users(id),
                product_name VARCHAR(200) NOT NULL,
                order_id VARCHAR(100),
                actual_price DECIMAL(10, 2) NOT NULL,
                quantity INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'placed',
                payment_method VARCHAR(50) DEFAULT 'COD',
                delivery_address TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expected_delivery DATE,
                tracking_id VARCHAR(100),
                notes TEXT,
                automation_mode VARCHAR(50) DEFAULT 'GROCERY',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create automation_sessions table (Track batch automation runs)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS automation_sessions (
                id SERIAL PRIMARY KEY,
                batch_session_id VARCHAR(100) UNIQUE NOT NULL,
                automation_type VARCHAR(50) NOT NULL CHECK (automation_type IN ('login_test', 'full_automation', 'add_address', 'add_coupon', 'remove_addresses', 'clear_cart')),
                automation_mode VARCHAR(50) DEFAULT 'GROCERY',
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
        
        # Create addresses table (Multi-address storage)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS addresses (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                address_template TEXT NOT NULL,
                office_no_min INTEGER NOT NULL DEFAULT 100,
                office_no_max INTEGER NOT NULL DEFAULT 999,
                name_postfix VARCHAR(50) NOT NULL,
                phone_prefix VARCHAR(10) NOT NULL,
                pincode VARCHAR(10) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                is_default BOOLEAN DEFAULT FALSE,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT office_no_range_check CHECK (office_no_min <= office_no_max),
                CONSTRAINT office_no_positive CHECK (office_no_min > 0 AND office_no_max > 0)
            );
        ''')    
        
        # Create system_settings table (Global configuration)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id SERIAL PRIMARY KEY,
                setting_key VARCHAR(100) UNIQUE NOT NULL,
                setting_value TEXT,
                setting_type VARCHAR(50) DEFAULT 'string',
                description TEXT,
                updated_by INTEGER REFERENCES users(id),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create job_queue table (Simple job queue using PostgreSQL)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS job_queue (
                id SERIAL PRIMARY KEY,
                job_type VARCHAR(50) NOT NULL,
                job_data JSONB NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                error_message TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create job_logs table (Track job execution logs)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS job_logs (
                id SERIAL PRIMARY KEY,
                job_id INTEGER REFERENCES job_queue(id) ON DELETE CASCADE,
                log_level VARCHAR(10) NOT NULL,
                message TEXT NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create indexes for better performance
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_flipkart_users_email ON flipkart_users(email);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_flipkart_products_active ON flipkart_products(is_active);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_flipkart_orders_status ON flipkart_orders(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_flipkart_orders_date ON flipkart_orders(order_date);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_batch_session_id ON automation_sessions(batch_session_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_automation_type ON automation_sessions(automation_type);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_automation_mode ON automation_sessions(automation_mode);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_by ON automation_sessions(started_by);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_at ON automation_sessions(started_at);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_job_queue_status ON job_queue(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_job_queue_type ON job_queue(job_type);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_job_queue_priority ON job_queue(priority DESC, created_at ASC);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id);')
        
        # Indexes for addresses table
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_addresses_active ON addresses(is_active);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_addresses_default ON addresses(is_default);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_addresses_created_by ON addresses(created_by);')
        
        # Insert default system settings (keeping non-address related settings)
        await conn.execute('''
            INSERT INTO system_settings (setting_key, setting_value, setting_type, description)
            VALUES 
                ('max_concurrent_sessions', '5', 'integer', 'Maximum number of concurrent automation sessions'),
                ('default_check_interval', '300', 'integer', 'Default product price check interval in seconds'),
                ('max_login_attempts', '3', 'integer', 'Maximum login attempts before account lockout'),
                ('order_timeout', '600', 'integer', 'Order placement timeout in seconds'),
                ('proxy_rotation_enabled', 'true', 'boolean', 'Enable proxy rotation for accounts')
            ON CONFLICT (setting_key) DO NOTHING;
        ''')        
        
        # Create default admin user (password: admin123) first
        await conn.execute('''
            INSERT INTO users (username, password_hash, email, is_admin)
            VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lewFBFlyg5qCvqvC.', 'admin@flipkart-automation.com', true)
            ON CONFLICT (username) DO NOTHING;
        ''')
        
        # Insert default address configuration only if no addresses exist
        address_count = await conn.fetchval('SELECT COUNT(*) FROM addresses;')
        if address_count == 0:
            # Get the admin user ID (should be 1 if just created, or existing ID if already present)
            admin_user_id = await conn.fetchval("SELECT id FROM users WHERE username = 'admin';")
            if admin_user_id:
                await conn.execute('''
                    INSERT INTO addresses (name, description, address_template, office_no_min, office_no_max, 
                                         name_postfix, phone_prefix, pincode, is_default, created_by)
                    VALUES (
                        'Default Mumbai Address',
                        'Default address configuration for Mumbai operations',
                        'Offline no. {office_no} metha chamber, Dana Bunder, Masjid Bandar East, Mumbai',
                        100,
                        999,
                        'Shivshakti',
                        '6000',
                        '400010',
                        true,
                        $1
                    );
                ''', admin_user_id)
                print("✅ Created default address configuration")
            else:
                print("⚠️  Could not create default address: admin user not found")
        
        print("✅ Database schema created successfully!")
        print("📊 Tables created:")
        print("   - users (internal app users)")
        print("   - flipkart_users (Flipkart account credentials)")
        print("   - flipkart_products (product configurations)")
        print("   - flipkart_orders (order tracking)")
        print("   - automation_sessions (batch automation tracking)")
        print("   - addresses (multi-address storage) ✨ NEW")
        print("   - system_settings (global configuration)")
        print("   - job_queue (background job processing)")
        print("   - job_logs (job execution logs)")
        print("\n🏠 Multi-Address System:")
        print("   ✅ Support for multiple address configurations")
        print("   ✅ Each address includes: template, office range, name postfix, phone prefix, pincode")
        print("   ✅ Default address configuration created")
        print("   ✅ Address validation and selection capability")
        print("\n📊 New automation_sessions features:")
        print("   ✅ Batch session tracking with unique batch_session_id")
        print("   ✅ Automation type (login_test/full_automation)")
        print("   ✅ Progress monitoring (jobs/batches completion)")
        print("   ✅ Account range tracking (start/end) - nullable for custom email selection")
        print("   ✅ Support for both range-based and custom email account selection")
        print("   ✅ Batch coordination and status tracking")
        print("   ✅ Job statistics (total/completed/failed)")
        print("\n🔑 Default admin user created:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   Email: admin@flipkart-automation.com")
        print("\n🗄️ Database Details:")
        print(f"   Host: {host}:{port}")
        print(f"   Database: {db_name}")
        print(f"   User: {user}")
        
    except Exception as e:
        print(f"❌ Error creating schema: {e}")
        raise
    finally:
        await conn.close()

async def drop_all_tables():
    """Drop all tables (for development/testing)"""
    url_parts = DATABASE_URL.replace("postgresql://", "").split("/")
    db_name = url_parts[1] if len(url_parts) > 1 else "flipkart_automation"
    host_part = url_parts[0].split("@")
    user_pass = host_part[0].split(":")
    host_port = host_part[1].split(":")
    
    user = user_pass[0] if len(user_pass) > 0 else "flipkart_admin"
    password = user_pass[1] if len(user_pass) > 1 else "flipkart_secure_2024"
    host = host_port[0] if len(host_port) > 0 else "localhost"
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    
    conn = await asyncpg.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database=db_name
    )
    
    try:
        await conn.execute('DROP TABLE IF EXISTS job_logs CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS job_queue CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS automation_sessions CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS flipkart_orders CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS flipkart_products CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS flipkart_users CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS addresses CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS system_settings CASCADE;')
        await conn.execute('DROP TABLE IF EXISTS users CASCADE;')
        print("✅ All tables dropped successfully!")
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        raise
    finally:
        await conn.close()

async def update_automation_sessions_table():
    """Update automation_sessions table with new schema"""
    print("🔄 Updating automation_sessions table schema...")
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Drop existing table
        await conn.execute("DROP TABLE IF EXISTS automation_sessions CASCADE;")
        print("🗑️ Dropped existing automation_sessions table")
        
        # Recreate with new schema
        await conn.execute('''
            CREATE TABLE automation_sessions (
                id SERIAL PRIMARY KEY,
                batch_session_id VARCHAR(100) UNIQUE NOT NULL,
                automation_type VARCHAR(50) NOT NULL CHECK (automation_type IN ('login_test', 'full_automation', 'add_address', 'add_coupon', 'remove_addresses', 'clear_cart')),
                automation_mode VARCHAR(50) DEFAULT 'GROCERY',
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
        
        # Recreate indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(status);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_batch_session_id ON automation_sessions(batch_session_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_automation_type ON automation_sessions(automation_type);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_automation_mode ON automation_sessions(automation_mode);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_by ON automation_sessions(started_by);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_at ON automation_sessions(started_at);')
        
        print("✅ automation_sessions table updated successfully!")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Failed to update automation_sessions table: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        print("🗑️  Dropping all tables...")
        asyncio.run(drop_all_tables())
    elif len(sys.argv) > 1 and sys.argv[1] == "--update-sessions":
        print("🔄 Updating automation_sessions table...")
        asyncio.run(update_automation_sessions_table())
    else:
        print("🚀 Creating database schema...")
        asyncio.run(create_database_schema()) 