import os
import base64
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from groq import Groq
from dotenv import load_dotenv
from email.mime.text import MIMEText

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


def get_logged_in_user():
    """Return logged-in Gmail email address."""
    service = get_gmail_service()
    profile = service.users().getProfile(userId='me').execute()
    return profile.get('emailAddress')


def classify_email_body(body: str) -> str:
    """Classify an email body into a category."""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system",
             "content": "Classify emails into: Support, Spam, Newsletter, Personal, Job. Return only one word."},
            {"role": "user", "content": body[:1000]}
        ]
    )
    return response.choices[0].message.content


def generate_ai_reply(body: str) -> str:
    """Generate AI reply for the email body."""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Write a professional short email reply."},
            {"role": "user", "content": body[:1000]}
        ]
    )
    return response.choices[0].message.content


def fetch_latest_emails(max_results: int = 10) -> list[dict]:
    """Fetch last `max_results` emails from Inbox, ignoring no-reply/newsletter/spam."""
    service = get_gmail_service()
    results = service.users().messages().list(
        userId='me', 
        maxResults=max_results,
        labelIds=['INBOX']  # only Inbox, ignore sent messages
    ).execute()
    messages = results.get('messages', [])

    emails = []
    for msg_data in messages:
        msg = service.users().messages().get(userId='me', id=msg_data['id']).execute()
        headers = msg['payload']['headers']
        subject, sender = "", ""
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            if header['name'] == 'From':
                sender = header['value']

        # Extract plain text body
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

        # Classify and filter
        category = classify_email_body(body)
        lower_sender = sender.lower()
        if ("no-reply" in lower_sender or category in ["Spam", "Newsletter"]):
            continue

        emails.append({
            "subject": subject,
            "sender": sender,
            "body": body,
            "category": category,
            "thread_id": msg.get('threadId')
        })

    return emails

def send_email_reply(to_email: str, subject: str, body: str, thread_id: str = None) -> dict:
    """Send a reply email via Gmail."""
    service = get_gmail_service()
    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_data = {'raw': raw}
    if thread_id:
        message_data['threadId'] = thread_id

    sent_msg = service.users().messages().send(userId='me', body=message_data).execute()
    return sent_msg