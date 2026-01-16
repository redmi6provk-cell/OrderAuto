#!/usr/bin/env python3
"""
Test script to verify password hashing and authentication
"""

import asyncio
import asyncpg
import os
from passlib.context import CryptContext

# Same configuration as in auth.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

async def test_admin_credentials():
    """Test the admin credentials from the database"""
    
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
        
        # Get admin user from database
        admin_user = await conn.fetchrow(
            "SELECT username, password_hash, email, is_active, is_admin FROM users WHERE username = 'admin'"
        )
        
        if admin_user:
            print("✅ Admin user found in database:")
            print(f"   Username: {admin_user['username']}")
            print(f"   Email: {admin_user['email']}")
            print(f"   Is Active: {admin_user['is_active']}")
            print(f"   Is Admin: {admin_user['is_admin']}")
            print(f"   Password Hash: {admin_user['password_hash']}")
            
            # Test password verification
            print("\n🔐 Testing password verification:")
            test_passwords = ["admin123", "wrong_password", "admin", "Admin123"]
            
            for test_password in test_passwords:
                is_valid = verify_password(test_password, admin_user['password_hash'])
                status = "✅ VALID" if is_valid else "❌ INVALID"
                print(f"   Password '{test_password}': {status}")
                
            print("\n🆕 Generating new password hash for 'admin123':")
            new_hash = get_password_hash("admin123")
            print(f"   New Hash: {new_hash}")
            is_new_valid = verify_password("admin123", new_hash)
            print(f"   New Hash Verification: {'✅ VALID' if is_new_valid else '❌ INVALID'}")
            
        else:
            print("❌ Admin user not found in database!")
            print("💡 Consider running: python database_schema.py")
            
        await conn.close()
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        print("💡 Make sure PostgreSQL is running and credentials are correct")

if __name__ == "__main__":
    asyncio.run(test_admin_credentials())
