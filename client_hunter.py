#!/usr/bin/env python3
import os
import sys
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ---------- Load credentials from environment variables ----------
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
    print("ERROR: Missing Google API credentials. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    sys.exit(1)

# ---------- Gmail authentication ----------
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

# ---------- Send email ----------
def send_email_via_gmail(to, subject, html_content):
    service = get_gmail_service()
    message = MIMEText(html_content, "html")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}
    result = service.users().messages().send(userId="me", body=body).execute()
    print(f"✅ Email sent to {to} – Message ID: {result['id']}")
    return result

# ========== YOUR EXISTING CLIENT HUNTER LOGIC GOES BELOW ==========
# For example, the functions that scrape contact pages and send emails.
# Keep your original `main()` and scraping code – just replace the
# authentication part with the above.

def main():
    # Example: your existing code that finds contact pages and emails
    # ...
    # When you need to send an email, call:
    # send_email_via_gmail(email_addr, subject, html)
    pass

if __name__ == "__main__":
    main()
