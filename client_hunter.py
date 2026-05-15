#!/usr/bin/env python3
"""
Client Hunter – Finds junior medical researchers via OpenAlex API.
Targets authors with Indian affiliations, low works count, and a non‑empty email.
"""

import os
import sys
import time
import base64
import logging
import re
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import pyalex
from pyalex import Authors

# ========== CONFIGURATION ==========
DELAY_BETWEEN_EMAILS = 5
MAX_RETRIES = 3
RETRY_DELAY = 5
MAX_AUTHORS = 50
MAX_WORKS_THRESHOLD = 10   # Authors with ≤10 works considered "junior"

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== CREDENTIALS ==========
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    logger.error("Missing Google API credentials. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    sys.exit(1)

# ========== GMAIL AUTH ==========
def get_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

def send_email(to, subject, html_content):
    service = get_gmail_service()
    message = MIMEText(html_content, "html")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}
    for attempt in range(MAX_RETRIES):
        try:
            result = service.users().messages().send(userId="me", body=body).execute()
            logger.info(f"✅ Sent to {to} – ID: {result['id']}")
            return result
        except HttpError as e:
            if e.resp.status in [429, 500, 503]:
                wait = RETRY_DELAY * (attempt + 1)
                logger.warning(f"Retry {attempt+1} for {to} after {wait}s (HTTP {e.resp.status})")
                time.sleep(wait)
            else:
                logger.error(f"Non-retryable error for {to}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error for {to}: {e}")
            raise
    logger.error(f"Failed to send to {to} after {MAX_RETRIES} attempts.")
    return None

# ========== EMAIL VALIDATION ==========
def is_valid_email_syntax(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_email(email):
    if not email or not is_valid_email_syntax(email):
        return False
    blocked = {'example.com', 'test.com', 'localhost', 'domain.com', 'example.org', 'fake.com'}
    if email.split('@')[1].lower() in blocked:
        return False
    return True

# ========== OPENALEX API ==========
def configure_openalex():
    # Replace with your email to get polite pool access
    pyalex.config.email = "your-email@example.com"

def find_junior_medical_researchers():
    """Query OpenAlex for Indian authors with low works count, then filter those with email."""
    configure_openalex()
    # Only use valid filter fields (works_count and country code)
    filters = {
        "last_known_institutions.country_code": "IN",
        "works_count": f"1-{MAX_WORKS_THRESHOLD}",
    }
    try:
        # Fetch authors (up to MAX_AUTHORS)
        authors = Authors().filter(**filters).get(per_page=MAX_AUTHORS)
        emails = []
        for author in authors:
            email = author.get("email", "")
            if email and is_valid_email(email):
                # Additional check: ensure works count is within threshold (already filtered)
                works_count = author.get("works_count", 0)
                emails.append(email)
                logger.info(f"Found: {author.get('display_name')} ({email}) – works: {works_count}")
        return list(set(emails))
    except Exception as e:
        logger.error(f"OpenAlex query failed: {e}")
        return []

# ========== EMAIL CONTENT ==========
def get_email_subject():
    return "Medical writing support for Indian researchers (budget-friendly)"

def get_email_html():
    return """
    <html>
    <body>
    <p>Dear Colleague,</p>
    <p>If English is not your first language, getting published in international journals can be tough.</p>
    <p>I provide <strong>medical writing, editing, and formatting services at rates that fit Indian research budgets</strong> (starting at just ₹1000 per page).</p>
    <p>Let me help you turn your manuscript into a publication‑ready paper.</p>
    <p><a href="https://your-portfolio.com">View samples</a> or reply for a free quote.</p>
    <p>Best regards,<br>Your Name</p>
    <hr>
    <p style="font-size:12px;">Reply with "unsubscribe" to stop receiving emails.</p>
    </body>
    </html>
    """

# ========== MAIN ==========
def main():
    logger.info("=== Client Hunter Started (OpenAlex API) ===")
    emails = find_junior_medical_researchers()
    logger.info(f"Found {len(emails)} valid email candidates.")
    if not emails:
        logger.info("No emails found. Exiting.")
        return
    subject = get_email_subject()
    html = get_email_html()
    for idx, email in enumerate(emails, 1):
        logger.info(f"Sending {idx}/{len(emails)} to {email}")
        send_email(email, subject, html)
        if idx < len(emails):
            time.sleep(DELAY_BETWEEN_EMAILS)
    logger.info("=== Client Hunter Finished ===")

if __name__ == "__main__":
    main()
