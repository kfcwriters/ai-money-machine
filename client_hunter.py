#!/usr/bin/env python3
"""
Client Hunter – Targets non-premium Indian researchers and junior medical writers.
Uses Gmail API with refresh token (same credentials as YouTube).
"""

import os
import sys
import re
import time
import base64
import logging
import html
import dns.resolver
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ========== CONFIGURATION ==========
DELAY_BETWEEN_EMAILS = 3       # seconds between emails
MAX_RETRIES = 3
RETRY_DELAY = 5                # seconds
REQUEST_TIMEOUT = 15           # seconds for HTTP requests

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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

# ========== EMAIL VALIDATION ==========
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
    blocked = {'example.com', 'test.com', 'localhost', 'domain.com', 'example.org', 'fake.com'}
    if email.split('@')[1].lower() in blocked:
        return False
    # Optional MX check (can be disabled if DNS is slow)
    # if not has_mx_record(email):
    #     return False
    return True

# ========== TARGETING LOGIC ==========
PREMIUM_DOMAINS = {
    'aiims', 'iisc', 'iit', 'iim', 'nit', 'iiit', 'iiser', 'niser',
    'tifr', 'barc', 'icmr', 'csir', 'dbt', 'dst', 'ugc', 'instituteofscience'
}

SENIOR_KEYWORDS = ['director', 'head', 'senior', 'lead', 'principal', 'manager', 'vp', 'president', 'executive', 'chief']

def is_premium_institute(domain):
    domain_lower = domain.lower()
    for premium in PREMIUM_DOMAINS:
        if premium in domain_lower:
            return True
    return False

def is_target_researcher(email, context_text=""):
    """
    Return True if the contact is from a non-premium institution
    and likely a junior researcher / faculty member who needs writing help.
    """
    domain = email.split('@')[1].lower()
    local = email.split('@')[0].lower()
    
    # 1. Skip premium institutes immediately
    if is_premium_institute(domain):
        logger.debug(f"Skipping premium institute email: {email}")
        return False
    
    # 2. Accept Indian academic/government domains (non-premium)
    if any(domain.endswith(suffix) for suffix in ['.ac.in', '.edu.in', '.nic.in', '.gov.in']):
        return True
    
    # 3. Accept generic domains (gmail, yahoo, outlook) if they contain research indicators
    if domain in ['gmail.com', 'yahoo.com', 'outlook.com']:
        if any(word in local for word in ['dr', 'phd', 'research', 'lab', 'clinic', 'student', 'med', 'health']):
            # Check context for seniority (if provided)
            if context_text and any(kw in context_text.lower() for kw in SENIOR_KEYWORDS):
                logger.debug(f"Skipping senior researcher: {email}")
                return False
            return True
    
    # 4. Accept .edu domains (international, but could still be junior)
    if domain.endswith('.edu'):
        return True
    
    # 5. If we have context and it contains junior indicators
    if context_text:
        if any(kw in context_text.lower() for kw in ['junior', 'associate', 'intern', 'trainee', 'student', 'lecturer', 'assistant professor']):
            return True
    
    return False

# ========== EMAIL EXTRACTION (with HTML decoding) ==========
def extract_emails_from_page(url):
    """
    Scrapes a page and returns a list of (email, context_text) tuples.
    Decodes HTML entities and searches for mailto links and visible text.
    """
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        email_set = set()
        
        # Method 1: mailto links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href[7:].split('?')[0]
                email_set.add(email)
        
        # Method 2: HTML elements with email class/id
        for selector in ['[class*=email]', '[id*=email]', '.email', '#email']:
            for elem in soup.select(selector):
                text = html.unescape(elem.get_text(strip=True))
                found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                email_set.update(found)
        
        # Method 3: Entire visible text
        text = html.unescape(soup.get_text())
        all_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        email_set.update(all_emails)
        
        # Return as list of tuples with empty context (can be enhanced later)
        return [(email, "") for email in email_set]
    
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return []

# ========== TARGET URL LIST (non-premium Indian institutions) ==========
def find_contact_pages():
    """
    Returns a list of URLs to scrape for emails.
    These are faculty/staff pages from tier-2/3 colleges.
    """
    return [
        # State government medical colleges
        "https://www.gmc.edu.in/faculty",
        "https://www.svims.edu.in/faculty",
        "https://www.mgmmedicalcollege.com/faculty",
        "https://www.rguhs.ac.in/faculty",
        # Private medical colleges (non-premium)
        "https://www.kims.ac.in/faculty",
        "https://www.dypatil.edu/medical/faculty",
        "https://www.bharatividyapeeth.edu/medical/faculty",
        # Nursing / pharmacy colleges
        "https://www.jsuniversity.edu.in/nursing-faculty",
        "https://www.srmist.edu.in/faculty/nursing",
        "https://www.manipal.edu/nursing/faculty",
        # State universities (general)
        "https://www.unipune.ac.in/faculty",
        "https://www.caluniv.ac.in/faculty",
        "https://www.alagappauniversity.ac.in/faculty",
        # PhD scholar directories
        "https://www.shodhganga.inflibnet.ac.in/universities",
        "https://www.phdstudent.in/universities",
    ]

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

# ========== MAIN ORCHESTRATION ==========
def main():
    logger.info("=== Client Hunter Started ===")
    
    # Step 1: Get target URLs
    pages = find_contact_pages()
    logger.info(f"Found {len(pages)} contact pages.")
    
    # Step 2: Extract emails from each page
    all_candidates = []
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
    
    # Step 4: Filter valid and targeted emails
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
    
    # Step 5: No emails found – exit gracefully
    if not valid_targets:
        logger.info("No valid targets found. Exiting.")
        return
    
    # Step 6: Send emails
    subject = get_email_subject()
    html = get_email_html()
    
    for idx, (email, ctx) in enumerate(valid_targets, 1):
        logger.info(f"Sending {idx}/{len(valid_targets)} to {email}")
        send_email(email, subject, html)
        if idx < len(valid_targets):
            time.sleep(DELAY_BETWEEN_EMAILS)
    
    logger.info("=== Client Hunter Finished ===")

if __name__ == "__main__":
    main()
