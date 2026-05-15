#!/usr/bin/env python3
"""
Client Hunter - Scrapes contact pages and sends personalized emails via Gmail API.
Uses environment variables for credentials.
"""

import os
import sys
import re
import time
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ========== CONFIGURATION ==========
# Email validation settings
BLOCKED_DOMAINS = {
    'example.com', 'test.com', 'localhost', 'domain.com',
    'example.org', 'example.net', 'invalid.com', 'fake.com'
}
ROLE_PATTERNS = re.compile(r'^(admin|info|support|sales|contact|webmaster|noreply|no-reply)@', re.IGNORECASE)

# Rate limiting – seconds between emails (Gmail API allows ~250 per 100 seconds, but safe is 1 per second)
DELAY_BETWEEN_EMAILS = 2  # 2 seconds between each email

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== LOAD CREDENTIALS ==========
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    logger.error("Missing Google API credentials. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    sys.exit(1)

# ========== GMAIL AUTHENTICATION ==========
def get_gmail_service():
    """Return authenticated Gmail API service."""
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

# ========== EMAIL VALIDATION ==========
def is_valid_email(email):
    """Check if email is real and not a role/fake address."""
    if not email or not isinstance(email, str):
        return False
    
    # Basic format check
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False
    
    # Block common fake domains
    domain = email.split('@')[-1].lower()
    if domain in BLOCKED_DOMAINS:
        logger.debug(f"Skipping blocked domain: {domain}")
        return False
    
    # Block role-based addresses
    if ROLE_PATTERNS.match(email):
        logger.debug(f"Skipping role-based address: {email}")
        return False
    
    return True

# ========== SEND EMAIL WITH RETRY ==========
def send_email_via_gmail(to, subject, html_content, retries=MAX_RETRIES):
    """Send email using Gmail API with retry logic."""
    service = get_gmail_service()
    
    # Create message
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["subject"] = subject
    # Attach HTML part
    msg_text = MIMEText(html_content, "html")
    message.attach(msg_text)
    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    body = {"raw": raw_message}
    
    for attempt in range(retries):
        try:
            result = service.users().messages().send(userId="me", body=body).execute()
            logger.info(f"✅ Email sent to {to} – ID: {result['id']}")
            return result
        except HttpError as e:
            if e.resp.status in [429, 500, 503]:
                wait = RETRY_DELAY * (attempt + 1)
                logger.warning(f"Retry {attempt+1}/{retries} for {to} after {wait}s due to {e.resp.status}")
                time.sleep(wait)
            else:
                logger.error(f"Non-retryable error for {to}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error for {to}: {e}")
            raise
    
    logger.error(f"Failed to send email to {to} after {retries} attempts.")
    return None

# ========== YOUR SCRAPING LOGIC GOES HERE ==========
def find_contact_pages():
    """Your existing function to find contact pages."""
    # Replace with your actual scraping code
    # Returns a list of URLs or emails
    logger.info("Searching for contact pages...")
    # Example:
    # return ["https://example.com/contact"]
    return []

def extract_emails_from_page(url):
    """Your existing function to extract emails from a page."""
    logger.info(f"Extracting emails from {url}")
    # Replace with your actual extraction logic
    # Returns a list of email strings
    return []

def send_bulk_emails():
    """Main orchestration – validates emails, sends with delay."""
    contact_pages = find_contact_pages()
    all_emails = set()
    
    for page in contact_pages:
        emails = extract_emails_from_page(page)
        all_emails.update(emails)
    
    logger.info(f"Found {len(all_emails)} total email candidates.")
    
    valid_emails = [email for email in all_emails if is_valid_email(email)]
    logger.info(f"Valid emails: {len(valid_emails)}")
    
    for idx, email in enumerate(valid_emails, 1):
        subject = "Medical writing support for your team"
        html = f"""
        <html>
          <body>
            <p>Hello,</p>
            <p>I help medical practices increase patient engagement through professional medical writing and SEO content.</p>
            <p>Would you like a free sample article tailored to your specialty?</p>
            <p>Best regards,<br>Your Name</p>
            <p style="font-size:12px; color:#666;">If you no longer wish to receive emails, reply with "unsubscribe".</p>
          </body>
        </html>
        """
        logger.info(f"Sending {idx}/{len(valid_emails)} to {email}")
        send_email_via_gmail(email, subject, html)
        # Delay between emails to respect rate limits
        if idx < len(valid_emails):
            time.sleep(DELAY_BETWEEN_EMAILS)

# ========== MAIN ==========
def main():
    """Entry point."""
    logger.info("=== Client Hunter Started ===")
    send_bulk_emails()
    logger.info("=== Client Hunter Finished ===")

if __name__ == "__main__":
    main()
