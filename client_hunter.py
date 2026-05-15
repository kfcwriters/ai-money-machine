#!/usr/bin/env python3
"""
Client Hunter – Finds emails via Google Scholar (no scraping institute sites).
Targets junior Indian medical researchers.
"""

import os
import sys
import time
import logging
from scholarly import scholarly
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

# ========== CONFIG ==========
DELAY_BETWEEN_EMAILS = 5
MAX_RESULTS = 30
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== CREDENTIALS (same as before) ==========
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    logger.error("Missing Google API credentials")
    sys.exit(1)

def get_gmail_service():
    creds = Credentials(token=None, refresh_token=REFRESH_TOKEN,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

def send_email(to, subject, html_content):
    service = get_gmail_service()
    message = MIMEText(html_content, "html")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}
    result = service.users().messages().send(userId="me", body=body).execute()
    logger.info(f"✅ Sent to {to}")
    return result

# ========== GOOGLE SCHOLAR SCRAPER ==========
def find_junior_medical_researchers(keyword="medical writing", max_results=MAX_RESULTS):
    """Search Google Scholar for Indian authors with low citations."""
    search_query = scholarly.search_author(f'{keyword} India')
    emails = []
    for _ in range(max_results):
        try:
            author = next(search_query)
            # Check if email exists and citations low
            if 'email' in author and author['email']:
                citations = author.get('citedby', 999)
                if citations < 50:  # junior researcher
                    emails.append(author['email'])
                    logger.info(f"Found: {author.get('name')} - {author['email']} ({citations} cites)")
        except StopIteration:
            break
        except Exception as e:
            logger.warning(f"Scholar error: {e}")
    return list(set(emails))

# ========== EMAIL CONTENT ==========
def get_email_html():
    return """
    <html>
    <body>
    <p>Dear Researcher,</p>
    <p>Publishing in English journals can be challenging. I offer affordable medical writing/editing (₹1000/page).</p>
    <p>Free sample available. Reply for details.</p>
    <p>Best,<br>Medical Writer</p>
    </body>
    </html>
    """

# ========== MAIN ==========
def main():
    logger.info("Starting Google Scholar hunt...")
    emails = find_junior_medical_researchers("medical research", max_results=20)
    logger.info(f"Found {len(emails)} junior researcher emails.")
    
    if not emails:
        logger.info("No emails found. Exiting.")
        return
    
    subject = "Affordable medical writing support for Indian researchers"
    html = get_email_html()
    
    for idx, email in enumerate(emails, 1):
        logger.info(f"Sending {idx}/{len(emails)} to {email}")
        send_email(email, subject, html)
        time.sleep(DELAY_BETWEEN_EMAILS)

if __name__ == "__main__":
    main()
