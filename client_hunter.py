#!/usr/bin/env python3
"""
Client Hunter – Targets Indian researchers and junior medical writers.
Uses Gmail API with refresh token (same credentials as YouTube).
"""

import os
import sys
import re
import time
import base64
import logging
import dns.resolver
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ========== CONFIGURATION ==========
DELAY_BETWEEN_EMAILS = 3       # seconds between emails
MAX_RETRIES = 3
RETRY_DELAY = 5                # seconds

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== CREDENTIALS (from environment) ==========
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    logger.error("Missing Google API credentials. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    sys.exit(1)

# ========== GMAIL AUTHENTICATION ==========
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

# ========== EMAIL VALIDATION (Syntax + MX) ==========
def is_valid_email_syntax(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def has_mx_record(email):
    """Check if domain has an MX record (can receive email)."""
    domain = email.split('@')[1]
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.LifetimeTimeout):
        return False

def is_valid_email(email):
    """Full validation: syntax + MX + not obviously fake."""
    if not is_valid_email_syntax(email):
        return False
    # Skip common placeholder domains
    blocked = {'example.com', 'test.com', 'localhost', 'domain.com', 'example.org'}
    if email.split('@')[1].lower() in blocked:
        return False
    # MX check (optional – can be disabled if DNS is slow)
    # if not has_mx_record(email):
    #     return False
    return True

# ========== TARGETING LOGIC ==========
SENIOR_KEYWORDS = ['director', 'head', 'senior', 'lead', 'principal', 'manager', 'vp', 'president', 'executive', 'chief']

def is_target_researcher(email, context_text=""):
    """
    Return True if the contact is an Indian researcher or a newcomer.
    Skips senior roles if context_text contains senior keywords.
    """
    domain = email.split('@')[1].lower()
    local = email.split('@')[0].lower()
    
    # 1. Indian academic/government domains
    if any(domain.endswith(suffix) for suffix in ['.ac.in', '.edu.in', '.nic.in', '.gov.in']):
        return True
    
    # 2. Gmail / Yahoo / Outlook with research indicators in local part
    if domain in ['gmail.com', 'yahoo.com', 'outlook.com']:
        if any(word in local for word in ['dr', 'phd', 'research', 'lab', 'clinic', 'student', 'med', 'health']):
            # Check context for seniority (if provided)
            if context_text and any(kw in context_text.lower() for kw in SENIOR_KEYWORDS):
                logger.debug(f"Skipping senior researcher with research email: {email}")
                return False
            return True
    
    # 3. .edu domains (international students / researchers)
    if domain.endswith('.edu'):
        return True
    
    # 4. If we have context and it contains junior indicators
    if context_text:
        if any(kw in context_text.lower() for kw in ['junior', 'associate', 'intern', 'trainee', 'student']):
            return True
    
    return False

# ========== SEND EMAIL WITH RETRY ==========
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

# ========== YOUR SCRAPING FUNCTIONS (replace with your actual) ==========
def find_contact_pages():
    """
    Returns a list of URLs to scrape for emails.
    Example: list of Indian university faculty pages.
    """
    # Placeholder – replace with your logic
    return [
        "https://www.aiims.edu/en/faculty.html",
        "https://www.iisc.ac.in/faculty/",
    ]

def extract_emails_from_page(url):
    """
    Scrapes a page and returns a list of (email, context_text) tuples.
    Context can be the surrounding text (e.g., job title, department).
    """
    import requests
    from bs4 import BeautifulSoup
    emails = []
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.content, 'html.parser')
        text = soup.get_text()
        # Find all email-like strings
        found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        for email in set(found):
            # Simple context: first 200 chars around email? (optional)
            context = text[max(0, text.find(email)-200):text.find(email)+200] if email in text else ""
            emails.append((email, context))
        return emails
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return []

# ========== MAIN ORCHESTRATION ==========
def main():
    logger.info("=== Client Hunter Started ===")
    
    # Step 1: Find contact pages
    pages = find_contact_pages()
    logger.info(f"Found {len(pages)} contact pages.")
    
    # Step 2: Extract emails with context
    all_candidates = []   # list of (email, context)
    for page in pages:
        candidates = extract_emails_from_page(page)
        logger.info(f"Extracted {len(candidates)} candidates from {page}")
        all_candidates.extend(candidates)
    
    # Step 3: Deduplicate by email
    unique = {}
    for email, ctx in all_candidates:
        if email not in unique:
            unique[email] = ctx
    logger.info(f"Unique email candidates: {len(unique)}")
    
    # Step 4: Filter
    valid_targets = []
    for email, ctx in unique.items():
        if not is_valid_email(email):
            logger.debug(f"Skipping invalid email: {email}")
            continue
        if not is_target_researcher(email, ctx):
            logger.debug(f"Skipping non-target: {email}")
            continue
        valid_targets.append((email, ctx))
    
    logger.info(f"Valid targets after filtering: {len(valid_targets)}")
    
    # Step 5: Prepare email content
    subject = "Affordable medical writing support for Indian researchers"
    html_template = """
    <html>
    <body>
    <p>Dear Researcher,</p>
    <p>I understand the pressure to publish in high‑impact journals while English is not your first language.</p>
    <p>I provide <strong>high‑quality medical writing, editing, and manuscript formatting</strong> at rates suitable for Indian budgets.</p>
    <p>Let me help you get your paper publication‑ready without spending a fortune.</p>
    <p><a href="https://your-portfolio-link.com">See samples</a> or reply to this email for a free quote.</p>
    <p>Best regards,<br>Your Name</p>
    <hr>
    <p style="font-size:12px;">Reply with "unsubscribe" to stop receiving emails.</p>
    </body>
    </html>
    """
    
    # Step 6: Send emails with delay
    for idx, (email, ctx) in enumerate(valid_targets, 1):
        logger.info(f"Sending {idx}/{len(valid_targets)} to {email}")
        send_email(email, subject, html_template)
        if idx < len(valid_targets):
            time.sleep(DELAY_BETWEEN_EMAILS)
    
    logger.info("=== Client Hunter Finished ===")

if __name__ == "__main__":
    main()
