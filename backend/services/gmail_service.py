"""
Gmail IMAP Service for OTP Fetching
Connects to Gmail via IMAP to fetch OTP codes from Flipkart emails
"""

import imaplib
import email
import re
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from email.header import decode_header
from dotenv import load_dotenv

# Load environment variables from the correct path
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class GmailOTPService:
    def __init__(self):
        self.gmail_email = os.getenv("GMAIL_EMAIL")
        self.gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        
        # Validate that required credentials are present
        if not self.gmail_email or not self.gmail_password:
            logging.error(f"Gmail credentials missing - GMAIL_EMAIL: {'✓' if self.gmail_email else '✗'}, GMAIL_APP_PASSWORD: {'✓' if self.gmail_password else '✗'}")
            logging.error("Please ensure GMAIL_EMAIL and GMAIL_APP_PASSWORD are set in the .env file")
        
    def connect(self) -> imaplib.IMAP4_SSL:
        """Connect to Gmail IMAP server"""
        try:
            # Validate credentials before attempting connection
            if not self.gmail_email or not self.gmail_password:
                raise ValueError("Gmail credentials (GMAIL_EMAIL, GMAIL_APP_PASSWORD) are not configured")
            
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.gmail_email, self.gmail_password)
            logging.info(f"Successfully connected to Gmail for {self.gmail_email}")
            return mail
        except Exception as e:
            logging.error(f"Failed to connect to Gmail: {e}")
            raise
    
    @staticmethod
    def _extract_recipients(email_message) -> List[str]:
        """Return a list of all recipient addresses from common headers."""
        from email.utils import getaddresses
        headers_to_check = [
            email_message.get('To', ''),
            email_message.get('Delivered-To', ''),
            email_message.get('X-Original-To', ''),
            email_message.get('X-Envelope-To', ''),
            email_message.get('Envelope-To', ''),
        ]
        addrs = []
        for hdr in headers_to_check:
            for _, addr in getaddresses([hdr]):
                if addr:
                    addrs.append(addr.strip())
        return addrs
    
    def extract_otp_from_text(self, text: str) -> Optional[str]:
        """Extract OTP from email text using regex patterns"""
        # Common OTP patterns
        patterns = [
            r'(\d{6})',  # Prefer 6-digit code first (most common)
            r'(?:OTP|otp|code|Code|PIN|pin)[\s:]*(\d{4,8})',  # OTP: 123456
            r'(\d{4,8})[\s]*(?:is your|verification|OTP|otp)',  # 123456 is your OTP
            r'Your[\s]+(?:OTP|otp|code|Code)[\s]*:?[\s]*(\d{4,8})',  # Your OTP: 123456
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                otp = match.group(1)
                # Validate OTP length (usually 4-8 digits)
                if 4 <= len(otp) <= 8:
                    return otp
        
        return None
    
    def fetch_flipkart_otp(self, target_email: str = None, max_wait_time: int = 120) -> Optional[str]:
        """
        Fetch OTP for the exact target email with minimal waiting:
        - Perform one immediate search for the most recent valid message (<=30 min old) addressed to target_email.
        - If not found, wait 4 seconds and try once more.
        - If still not found, stop and return None (no older OTP reuse).
        """
        if not self.gmail_email or not self.gmail_password:
            logging.error("Gmail credentials not configured. Cannot fetch OTP.")
            return None

        def extract_from_message(email_message) -> Optional[str]:
            # Subject first
            subject_raw = email_message.get('Subject', '')
            subject_text = ''
            try:
                decoded = decode_header(subject_raw)
                for frag, enc in decoded:
                    if isinstance(frag, bytes):
                        subject_text += frag.decode(enc or 'utf-8', errors='ignore')
                    else:
                        subject_text += frag
            except Exception:
                subject_text = str(subject_raw)
            if subject_text:
                otp = self.extract_otp_from_text(subject_text)
                if otp:
                    logging.info("Found OTP in subject")
                    return otp
            # Body fallback
            text_content = self.get_email_text_content(email_message)
            if text_content:
                otp = self.extract_otp_from_text(text_content)
                if otp:
                    logging.info(f"Found OTP: {otp}")
                    return otp
            return None

        def find_latest_otp(mail) -> Optional[str]:
            # IMAP SINCE is day-level; we still filter by Date header to ~1 minute below
            since_date = (datetime.now() - timedelta(minutes=1)).strftime('%d-%b-%Y')
            latest: Optional[tuple[datetime, str]] = None  # (date, otp)

            def consider_folder(folder_name: str):
                nonlocal latest
                try:
                    status, _ = mail.select(folder_name)
                    if status != 'OK':
                        return
                except Exception:
                    return

                try:
                    # Broad search by domain to include all flipkart senders
                    result, messages = mail.search(None, f'(FROM "flipkart.com") SINCE {since_date}')
                    if result != 'OK' or not messages or not messages[0]:
                        return
                    message_ids = messages[0].split()
                    # Scan last 20 messages for safety
                    for msg_id in reversed(message_ids[-20:]):
                        try:
                            res, msg_data = mail.fetch(msg_id, '(RFC822)')
                            if res != 'OK':
                                continue
                            email_body = msg_data[0][1]
                            email_message = email.message_from_bytes(email_body)

                            # Must be addressed to target_email exactly
                            if target_email:
                                recipients = [a.lower() for a in self._extract_recipients(email_message)]
                                if target_email.lower() not in recipients:
                                    continue

                            # Recent (<= ~1 minute)
                            email_dt = None
                            try:
                                date_str = email_message.get('Date')
                                if date_str:
                                    parsed = email.utils.parsedate_to_datetime(date_str)
                                    email_dt = parsed
                            except Exception:
                                email_dt = None
                            if not email_dt:
                                continue
                            if datetime.now(email_dt.tzinfo) - email_dt > timedelta(minutes=1):
                                continue

                            # Extract
                            otp = extract_from_message(email_message)
                            if otp:
                                if latest is None or email_dt > latest[0]:
                                    latest = (email_dt, otp)
                        except Exception:
                            continue
                except Exception:
                    return

            try:
                mail = self.connect()
                # Check INBOX then All Mail
                consider_folder('INBOX')
                if latest is None:
                    consider_folder('"[Gmail]/All Mail"')
                    if latest is None:
                        consider_folder('All Mail')

                # Return latest if found
                if latest is not None:
                    mail.close(); mail.logout()
                    return latest[1]

                # Not found: wait 4s and try once more
                time.sleep(4)
                # Try again fresh
                latest = None
                consider_folder('INBOX')
                if latest is None:
                    consider_folder('"[Gmail]/All Mail"')
                    if latest is None:
                        consider_folder('All Mail')

                if latest is not None:
                    mail.close(); mail.logout()
                    return latest[1]

                mail.close(); mail.logout()
                return None
            except Exception as e:
                logging.error(f"Error fetching OTP: {e}")
                try:
                    mail.close(); mail.logout()
                except Exception:
                    pass
                return None

        return find_latest_otp(self.connect())
    
    def get_email_text_content(self, email_message) -> str:
        """Extract text content from email message"""
        text_content = ""
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        try:
                            charset = part.get_content_charset() or 'utf-8'
                            body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            text_content += body + "\n"
                        except:
                            pass
                    elif content_type == "text/html" and "attachment" not in content_disposition and not text_content:
                        try:
                            charset = part.get_content_charset() or 'utf-8'
                            body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            # Simple HTML to text conversion
                            import re
                            body = re.sub('<[^<]+?>', '', body)
                            text_content += body + "\n"
                        except:
                            pass
            else:
                try:
                    payload = email_message.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        text_content = payload.decode(email_message.get_content_charset() or 'utf-8', errors='ignore')
                    else:
                        text_content = str(payload)
                except:
                    pass
        
        except Exception as e:
            logging.warning(f"Error extracting email content: {e}")
        
        return text_content
    
    def test_connection(self) -> bool:
        """Test Gmail IMAP connection"""
        try:
            mail = self.connect()
            mail.select('inbox')
            result, messages = mail.search(None, 'ALL')
            mail.close()
            mail.logout()
            return result == 'OK'
        except Exception as e:
            logging.error(f"Gmail connection test failed: {e}")
            return False


# Global instance
gmail_service = GmailOTPService()
