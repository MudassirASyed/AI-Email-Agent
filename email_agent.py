import os
import json
import base64
import pickle
from io import BytesIO
from datetime import datetime

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


def classify_email(subject: str, sender: str, body: str) -> dict:
    """
    Better classification - returns dict with category and reason.
    Categories: 'personal', 'work', 'important', 'ignore'
    """
    
    sender_lower = sender.lower()
    subject_lower = subject.lower()
    
    # 1. IMMEDIATE IGNORE RULES (no LLM call needed)
    ignore_keywords = [
        'no-reply', 'noreply', 'newsletter', 'unsubscribe',
        'promotion', 'offer', 'discount', 'sale', 'deal',
        'weekly digest', 'monthly digest', 'receipt', 'invoice',
        'payment confirmed', 'order confirmed', 'tracking number',
        'do-not-reply', 'mailer-daemon'
    ]
    
    for keyword in ignore_keywords:
        if keyword in sender_lower or keyword in subject_lower:
            return {'category': 'ignore', 'reason': f'Matched keyword: {keyword}'}
    
    # 2. PERSONAL/WORK KEYWORDS
    personal_keywords = ['meeting', 'catch up', 'lunch', 'dinner', 'party', 'birthday']
    work_keywords = ['project', 'deadline', 'client', 'report', 'urgent', 'asap', 'review']
    
    for keyword in personal_keywords:
        if keyword in subject_lower or keyword in body[:500].lower():
            return {'category': 'personal', 'reason': f'Matched: {keyword}'}
    
    for keyword in work_keywords:
        if keyword in subject_lower or keyword in body[:500].lower():
            return {'category': 'work', 'reason': f'Matched: {keyword}'}
    
    # 3. Use LLM for complex cases
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": """Classify this email into EXACTLY one category: 
                    - personal: Friends, family, social events
                    - work: Job, colleagues, clients, projects
                    - ignore: Newsletters, promotions, receipts, spam, automated emails
                    
                    Return ONLY the category name (one word)."""
                },
                {
                    "role": "user",
                    "content": f"Subject: {subject}\nFrom: {sender}\nBody: {body[:800]}"
                }
            ],
            temperature=0.1  # Low temperature for consistent classification
        )
        category = response.choices[0].message.content.strip().lower()
        
        if category not in ['personal', 'work', 'ignore']:
            category = 'ignore'
            
        return {'category': category, 'reason': 'LLM classification'}
        
    except Exception as e:
        print(f"LLM classification failed: {e}")
        return {'category': 'ignore', 'reason': 'Fallback due to error'}


def generate_ai_reply(body: str, sender: str, category: str) -> str:
    """Generate AI reply based on category."""
    
    # Different prompts based on category
    if category == 'personal':
        system_prompt = "Write a friendly, casual email reply. Be warm and personable."
    else:  # work
        system_prompt = "Write a professional, concise email reply. Be polite and efficient."
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Reply to this email:\n\n{body[:1500]}"}
        ]
    )
    return response.choices[0].message.content.strip()


def fetch_important_emails(max_results: int = 20) -> list[dict]:
    """Fetch only important emails (personal + work)."""
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
        subject = ""
        sender = ""
        
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
        classification = classify_email(subject, sender, body)
        
        # Skip ignored emails
        if classification['category'] == 'ignore':
            continue
        
        emails.append({
            "subject": subject,
            "sender": sender,
            "body": body,
            "category": classification['category'],
            "classification_reason": classification['reason'],
            "thread_id": msg.get('threadId'),
            "message_id": msg['id']
        })
    
    return emails


def send_email_reply(to_email: str, subject: str, body: str, thread_id: str = None):
    """Send Gmail reply."""
    service = get_gmail_service()
    
    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = f"Re: {subject}"
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_data = {'raw': raw}
    
    if thread_id:
        message_data['threadId'] = thread_id
    
    sent_msg = service.users().messages().send(
        userId='me',
        body=message_data
    ).execute()
    
    return sent_msg


def mark_as_read(message_id: str):
    """Mark email as read (for autonomous mode)."""
    service = get_gmail_service()
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


def auto_process_emails():
    """
    Autonomous function - can be called by cron job.
    Processes emails without user intervention.
    """
    print(f"[{datetime.now()}] Auto-processing emails...")
    
    emails = fetch_important_emails(max_results=10)
    
    results = []
    for email in emails:
        try:
            # Generate reply
            reply = generate_ai_reply(email['body'], email['sender'], email['category'])
            
            # Send automatically (for trusted senders)
            # Or you can save as draft: modify this based on your preference
            send_email_reply(
                to_email=email['sender'],
                subject=email['subject'],
                body=reply,
                thread_id=email['thread_id']
            )
            
            # Mark as read
            mark_as_read(email['message_id'])
            
            results.append({
                'subject': email['subject'],
                'sender': email['sender'],
                'status': 'replied'
            })
            
            print(f"  ✅ Replied to: {email['subject']}")
            
        except Exception as e:
            print(f"  ❌ Failed: {email['subject']} - {e}")
            results.append({
                'subject': email['subject'],
                'sender': email['sender'],
                'status': 'failed',
                'error': str(e)
            })
    
    print(f"[{datetime.now()}] Processed {len(results)} emails")
    return results


# For testing autonomously
if __name__ == "__main__":
    auto_process_emails()