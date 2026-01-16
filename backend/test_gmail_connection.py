#!/usr/bin/env python3
"""
Test script to verify Gmail service configuration and connection
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

def test_environment_variables():
    """Test if environment variables are loaded correctly"""
    print("=== Testing Environment Variables ===")
    
    gmail_email = os.getenv("GMAIL_EMAIL")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    
    print(f"GMAIL_EMAIL: {'✓ Found' if gmail_email else '✗ Missing'}")
    print(f"GMAIL_APP_PASSWORD: {'✓ Found' if gmail_password else '✗ Missing'}")
    
    if gmail_email:
        print(f"Email: {gmail_email}")
    if gmail_password:
        print(f"App Password: {gmail_password[:4]}...{gmail_password[-4:]} (masked)")
    
    return bool(gmail_email and gmail_password)

def test_gmail_service():
    """Test Gmail service initialization and connection"""
    print("\n=== Testing Gmail Service ===")
    
    try:
        from services.gmail_service import gmail_service
        
        print("Gmail service imported successfully")
        print(f"Service email: {gmail_service.gmail_email}")
        print(f"Service password configured: {'Yes' if gmail_service.gmail_password else 'No'}")
        
        # Test connection
        print("Testing Gmail connection...")
        if gmail_service.test_connection():
            print("✓ Gmail connection successful!")
            return True
        else:
            print("✗ Gmail connection failed")
            return False
            
    except Exception as e:
        print(f"✗ Error testing Gmail service: {e}")
        return False

if __name__ == "__main__":
    print("Gmail Service Configuration Test")
    print("=" * 40)
    
    # Test 1: Environment variables
    env_ok = test_environment_variables()
    
    if not env_ok:
        print("\n❌ Environment variables not configured properly")
        print("Please check your .env file in the backend directory")
        sys.exit(1)
    
    # Test 2: Gmail service
    service_ok = test_gmail_service()
    
    if service_ok:
        print("\n✅ Gmail service configured and working correctly!")
    else:
        print("\n❌ Gmail service has issues")
        sys.exit(1)
