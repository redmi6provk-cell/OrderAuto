#!/usr/bin/env python3
"""
Add test data for Flipkart automation system
This script adds sample Flipkart accounts and products for testing
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

async def add_test_data():
    """Add test Flipkart accounts and products"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Add test Flipkart accounts
        print("Adding test Flipkart accounts...")
        
        test_accounts = [
            {
                "email": "test1@example.com",
                "password": "test123",
                "is_active": True
            },
            {
                "email": "test2@example.com", 
                "password": "test456",
                "is_active": True
            }
        ]
        
        for account in test_accounts:
            await conn.execute(
                """
                INSERT INTO flipkart_users (email, password, is_active, created_by)
                VALUES ($1, $2, $3, 1)
                ON CONFLICT (email) DO UPDATE SET
                password = EXCLUDED.password,
                is_active = EXCLUDED.is_active
                """,
                account["email"], account["password"], account["is_active"]
            )
        
        print(f"✅ Added {len(test_accounts)} test Flipkart accounts")
        
        # Add test products
        print("Adding test products...")
        
        test_products = [
            {
                "product_link": "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac6485515ae4",
                "product_name": "Apple iPhone 15 (Black, 128 GB)",
                "quantity": 1,
                "price_cap": 70000.00,
                "is_active": True
            },
            {
                "product_link": "https://www.flipkart.com/samsung-galaxy-s24-ultra-titanium-gray-256-gb-12-gb-ram/p/itm123456789",
                "product_name": "Samsung Galaxy S24 Ultra (Titanium Gray, 256 GB)",
                "quantity": 1,
                "price_cap": 120000.00,
                "is_active": True
            },
            {
                "product_link": "https://www.flipkart.com/lenovo-ideapad-3-ryzen-5-hexa-core-5500u/p/itm987654321",
                "product_name": "Lenovo IdeaPad 3 Ryzen 5 Hexa Core 5500U",
                "quantity": 1,
                "price_cap": 45000.00,
                "is_active": True
            }
        ]
        
        for product in test_products:
            await conn.execute(
                """
                INSERT INTO flipkart_products (product_link, product_name, quantity, price_cap, is_active, created_by)
                VALUES ($1, $2, $3, $4, $5, 1)
                ON CONFLICT DO NOTHING
                """,
                product["product_link"], product["product_name"], 
                product["quantity"], product["price_cap"], product["is_active"]
            )
        
        print(f"✅ Added {len(test_products)} test products")
        
        # Show current data
        print("\n📊 Current data in database:")
        
        accounts = await conn.fetch("SELECT id, email, is_active FROM flipkart_users")
        print(f"Flipkart accounts: {len(accounts)}")
        for account in accounts:
            print(f"  - ID: {account['id']}, Email: {account['email']}, Active: {account['is_active']}")
        
        products = await conn.fetch("SELECT id, product_name, price_cap, is_active FROM flipkart_products")
        print(f"Products: {len(products)}")
        for product in products:
            print(f"  - ID: {product['id']}, Name: {product['product_name'][:50]}..., Cap: ₹{product['price_cap']}")
        
        print("\n🎉 Test data added successfully!")
        print("You can now test the automation endpoints:")
        print("  - POST /api/automation/start-automation")
        
    except Exception as e:
        print(f"❌ Error adding test data: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_test_data())




