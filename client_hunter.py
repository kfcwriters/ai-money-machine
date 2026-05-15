#!/usr/bin/env python3
import os
import pickle
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

# Your credentials (REPLACE AFTER TESTING)
CLIENT_ID = "921929857185-3oteean76en7tshu5ne5ktioqsocg6o2.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REFRESH_TOKEN = "1//04DR5kXoXvo9_CgYIARAAGAQSNwF-L9Ir8Pl8wGCejfJCtB4uzKe5NW-2P_OiXgTnEgpohrA7cGlh0s2wKmFztLLGEdO2_ZniqJg"

def get_gmail_service():
    """Return a Gmail service object using refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

def send_email_via_gmail(to, subject, html_content):
    """Send an email using Gmail API."""
    service = get_gmail_service()
    message = MIMEText(html_content, "html")
    message["to"] = to
    message["subject"] = subject
    # Encode in base64
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}
    result = service.users().messages().send(userId="me", body=body).execute()
    print(f"Email sent to {to} – Message ID: {result['id']}")
    return result

# Example usage (your existing main logic)
def main():
    # Your client hunting logic here (scraping etc.)
    # For demonstration, just a test email
    test_email = "test@example.com"
    html = "<p>Hello, we offer medical writing support...</p>"
    send_email_via_gmail(test_email, "Medical writing support for your team", html)

if __name__ == "__main__":
    main()
