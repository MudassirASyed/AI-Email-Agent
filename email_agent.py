import os
import json
import base64
import pickle
from io import BytesIO

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from groq import Groq
from dotenv import load_dotenv
from email.mime.text import MIMEText

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_gmail_service():
    """Authenticate using ENV secrets and return Gmail service."""
    
    # Load token from ENV (base64 encoded pickle)
    token_b64 = os.getenv("GMAIL_TOKEN")
    if not token_b64:
        raise Exception("GMAIL_TOKEN missing in environment variables")

    token_bytes = base64.b64decode(token_b64)
    creds = pickle.load(BytesIO(token_bytes))

    return build('gmail', 'v1', credentials=creds)


def get_logged_in_user():
    """Return logged-in Gmail email address."""
    service = get_gmail_service()
    profile = service.users().getProfile(userId='me').execute()
    return profile.get('emailAddress')


def classify_email_body(body: str) -> str:
    """Classify email body."""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "Classify emails into: Support, Spam, Newsletter, Personal, Job. Return only one word."
            },
            {
                "role": "user",
                "content": body[:1000]
            }
        ]
    )
    return response.choices[0].message.content.strip()


def generate_ai_reply(body: str) -> str:
    """Generate AI reply."""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "Write a professional short email reply."
            },
            {
                "role": "user",
                "content": body[:1000]
            }
        ]
    )
    return response.choices[0].message.content.strip()


def fetch_latest_emails(max_results: int = 10) -> list[dict]:
    """Fetch latest emails from Inbox."""
    service = get_gmail_service()

    results = service.users().messages().list(
        userId='me',
        maxResults=max_results,
        labelIds=['INBOX']
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for msg_data in messages:
        msg = service.users().messages().get(
            userId='me',
            id=msg_data['id']
        ).execute()

        headers = msg['payload']['headers']
        subject, sender = "", ""

        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            if header['name'] == 'From':
                sender = header['value']

        # Extract body
        body = ""
        parts = msg['payload'].get('parts')

        if parts:
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
        else:
            data = msg['payload']['body'].get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')

        # Classify
        category = classify_email_body(body)

        # Filter unwanted
        lower_sender = sender.lower()
        if "no-reply" in lower_sender or category in ["Spam", "Newsletter"]:
            continue

        emails.append({
            "subject": subject,
            "sender": sender,
            "body": body,
            "category": category,
            "thread_id": msg.get('threadId')
        })

    return emails


def send_email_reply(to_email: str, subject: str, body: str, thread_id: str = None):
    """Send Gmail reply."""
    service = get_gmail_service()

    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    message_data = {'raw': raw}

    if thread_id:
        message_data['threadId'] = thread_id

    sent_msg = service.users().messages().send(
        userId='me',
        body=message_data
    ).execute()

    return sent_msg