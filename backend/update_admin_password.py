#!/usr/bin/env python3
"""
Script to update admin password with a fresh hash
"""

import asyncio
import asyncpg
import os
from passlib.context import CryptContext

# Same configuration as in auth.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

async def update_admin_password():
    """Update admin password with a fresh hash"""
    
    # Parse DATABASE_URL for connection
    url_parts = DATABASE_URL.replace("postgresql://", "").split("/")
    db_name = url_parts[1] if len(url_parts) > 1 else "flipkart_automation"
    host_part = url_parts[0].split("@")
    user_pass = host_part[0].split(":")
    host_port = host_part[1].split(":")
    
    user = user_pass[0] if len(user_pass) > 0 else "flipkart_admin"
    password = user_pass[1] if len(user_pass) > 1 else "flipkart_secure_2024"
    host = host_port[0] if len(host_port) > 0 else "localhost"
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    
    try:
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=db_name
        )
        
        # Generate a fresh password hash for "admin123"
        new_password = "admin123"
        new_hash = get_password_hash(new_password)
        
        print(f"🔐 Generating new password hash for '{new_password}'")
        print(f"   New Hash: {new_hash}")
        
        # Update the admin user's password
        result = await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = CURRENT_TIMESTAMP WHERE username = 'admin'",
            new_hash
        )
        
        if result == "UPDATE 1":
            print("✅ Admin password updated successfully!")
            
            # Verify the update worked
            admin_user = await conn.fetchrow(
                "SELECT username, password_hash FROM users WHERE username = 'admin'"
            )
            
            if admin_user:
                print(f"✅ Verification - Updated hash: {admin_user['password_hash']}")
                
                # Test the new hash
                from passlib.context import CryptContext
                test_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
                is_valid = test_context.verify(new_password, admin_user['password_hash'])
                print(f"✅ Password verification test: {'PASSED' if is_valid else 'FAILED'}")
            
        else:
            print("❌ Failed to update admin password!")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error updating admin password: {e}")

if __name__ == "__main__":
    asyncio.run(update_admin_password())
