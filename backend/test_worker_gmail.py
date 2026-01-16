#!/usr/bin/env python3
"""
Test script to verify Gmail service works within automation worker context
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))

async def test_gmail_in_worker_context():
    """Test Gmail service in the same context as the automation worker"""
    print("=== Testing Gmail Service in Worker Context ===")
    
    try:
        # Import the same way the worker does
        from services.automation_tasks.authentication_handler import AuthenticationHandler
        from services.automation_tasks.browser_manager import BrowserManager
        from services.gmail_service import gmail_service
        
        print("✓ Successfully imported authentication handler and Gmail service")
        
        # Check Gmail service configuration
        print(f"Gmail Email: {'✓' if gmail_service.gmail_email else '✗'}")
        print(f"Gmail Password: {'✓' if gmail_service.gmail_password else '✗'}")
        
        if gmail_service.gmail_email:
            print(f"Configured email: {gmail_service.gmail_email}")
        
        # Test Gmail connection
        print("\nTesting Gmail connection...")
        if gmail_service.test_connection():
            print("✓ Gmail connection successful!")
            
            # Test fetching recent emails (not specifically OTP)
            print("\nTesting email search functionality...")
            try:
                mail = gmail_service.connect()
                mail.select('inbox')
                
                # Search for recent emails
                result, messages = mail.search(None, 'ALL')
                if result == 'OK' and messages[0]:
                    email_count = len(messages[0].split())
                    print(f"✓ Found {email_count} emails in inbox")
                else:
                    print("✗ No emails found or search failed")
                
                mail.close()
                mail.logout()
                
            except Exception as e:
                print(f"✗ Error testing email search: {e}")
            
            return True
        else:
            print("✗ Gmail connection failed")
            return False
            
    except Exception as e:
        print(f"✗ Error in worker context test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Gmail Service Worker Context Test")
    print("=" * 40)
    
    result = asyncio.run(test_gmail_in_worker_context())
    
    if result:
        print("\n✅ Gmail service works correctly in worker context!")
        print("The OTP fetching should now work during automation.")
    else:
        print("\n❌ Gmail service still has issues in worker context")
        sys.exit(1)
