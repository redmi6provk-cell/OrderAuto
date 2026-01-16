#!/usr/bin/env python3
"""
Test Gmail IMAP connection and OTP fetching
"""

import asyncio
from services.gmail_service import gmail_service

async def test_gmail_connection():
    """Test Gmail IMAP connection"""
    print("🔍 Testing Gmail IMAP connection...")
    
    try:
        if gmail_service.test_connection():
            print("✅ Gmail IMAP connection successful!")
            return True
        else:
            print("❌ Gmail IMAP connection failed!")
            return False
    except Exception as e:
        print(f"❌ Gmail IMAP connection error: {e}")
        return False

def test_otp_extraction():
    """Test OTP extraction from sample email text"""
    print("\n🔍 Testing OTP extraction...")
    
    sample_texts = [
        "Your OTP is 123456. Please use this code to verify your account.",
        "Verification code: 789012",
        "Your Flipkart OTP: 456789",
        "Use 321654 to complete your login",
        "Security code 987654 for account verification",
    ]
    
    for text in sample_texts:
        otp = gmail_service.extract_otp_from_text(text)
        print(f"Text: '{text[:50]}...' -> OTP: {otp}")
    
    print("✅ OTP extraction test completed!")

if __name__ == "__main__":
    print("🚀 Testing Gmail Service...")
    
    # Test OTP extraction (synchronous)
    test_otp_extraction()
    
    # Test Gmail connection (asynchronous)
    asyncio.run(test_gmail_connection())
    
    print("\n🎉 Gmail service test completed!")
    print("\n📧 Gmail Configuration:")
    print(f"   Email: {gmail_service.gmail_email}")
    print(f"   App Password: {'*' * len(gmail_service.gmail_password) if gmail_service.gmail_password else 'Not set'}")




