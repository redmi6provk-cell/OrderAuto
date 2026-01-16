#!/usr/bin/env python3
"""
Add simplified test data for OTP-based Flipkart automation system
No OTP storage - just email addresses for Flipkart accounts
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

async def add_simple_test_data():
    """Add simplified test data"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Clear existing test data
        print("Clearing existing test data...")
        await conn.execute("DELETE FROM flipkart_users")
        await conn.execute("DELETE FROM flipkart_products WHERE id > 0")
        
        # Add simple Flipkart accounts (just email, no password, no OTP storage)
        print("Adding simplified Flipkart accounts...")
        
        test_accounts = [
            "testaccount1@example.com",
            "testaccount2@example.com", 
            "automation.test@flipkart.com"
        ]
        
        for email in test_accounts:
            await conn.execute(
                """
                INSERT INTO flipkart_users (email, is_active, created_by)
                VALUES ($1, $2, 1)
                """,
                email, True
            )
        
        print(f"✅ Added {len(test_accounts)} simplified Flipkart accounts")
        
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
                "product_link": "https://www.flipkart.com/realme-narzo-70-pro-5g-glass-green-128-gb-8-gb-ram/p/itm987654321",
                "product_name": "Realme Narzo 70 Pro 5G (Glass Green, 128 GB)",
                "quantity": 2,
                "price_cap": 25000.00,
                "is_active": True
            }
        ]
        
        for product in test_products:
            await conn.execute(
                """
                INSERT INTO flipkart_products (product_link, product_name, quantity, price_cap, is_active, created_by)
                VALUES ($1, $2, $3, $4, $5, 1)
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
        
        products = await conn.fetch("SELECT id, product_name, price_cap, quantity, is_active FROM flipkart_products")
        print(f"Products: {len(products)}")
        for product in products:
            print(f"  - ID: {product['id']}, Name: {product['product_name'][:50]}..., Cap: ₹{product['price_cap']}, Qty: {product['quantity']}")
        
        print("\n🎉 Simplified test data added successfully!")
        print("\n📧 OTP Configuration:")
        print("   Gmail: vkkykh@kanuvk.com")
        print("   App Password: vwqf vvqo jltp vtwk")
        print("\n🔄 Login Flow:")
        print("   1. Use Flipkart email to start login")
        print("   2. OTP automatically fetched from vkkykh@kanuvk.com")
        print("   3. OTP used immediately for login")
        print("   4. Cookies saved to flipkart_users table")
        print("\nYou can now test:")
        print("  - POST /api/automation/start-automation")
        
    except Exception as e:
        print(f"❌ Error adding test data: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_simple_test_data())




