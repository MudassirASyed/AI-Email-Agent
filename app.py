import os
import streamlit as st
from dotenv import load_dotenv
from email_agent import (
    fetch_latest_emails,
    generate_ai_reply,
    send_email_reply,
    get_logged_in_user
)

load_dotenv()

# -----------------------------
# 🔐 AUTHENTICATION
# -----------------------------
APP_PASSWORD = os.getenv("APP_PASSWORD")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.set_page_config(page_title="AI Email Agent", layout="centered")
    st.title("🔐 AI Email Agent Login")

    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")

    st.stop()

# -----------------------------
# MAIN APP
# -----------------------------
st.set_page_config(page_title="AI Email Agent", layout="wide")
st.title("📧 AI Email Agent")

# Initialize session state
if 'emails' not in st.session_state:
    st.session_state['emails'] = []
if 'skip_flags' not in st.session_state:
    st.session_state['skip_flags'] = {}
if 'sent_flags' not in st.session_state:
    st.session_state['sent_flags'] = {}
if 'replies' not in st.session_state:
    st.session_state['replies'] = {}

# Logged-in user
user_email = get_logged_in_user()
st.info(f"Logged in as: {user_email}")

# Description
st.markdown("""
### What this agent does:
- Classifies incoming emails
- Generates AI replies
- Lets you approve/edit responses
- Prevents replying to newsletters/spam
""")

# Load emails
if st.button("📥 Load Emails"):
    emails = fetch_latest_emails(max_results=10)
    st.session_state['emails'] = emails
    st.session_state['skip_flags'] = {}
    st.session_state['sent_flags'] = {}
    st.session_state['replies'] = {}
    st.success(f"Loaded {len(emails)} emails")

# Filter emails
emails_to_show = [
    email for email in st.session_state['emails']
    if not st.session_state['sent_flags'].get(email['thread_id'], False)
    and not st.session_state['skip_flags'].get(email['thread_id'], False)
    and email['sender'].lower() != user_email.lower()
]

# Display emails
for email in emails_to_show:
    thread_id = email['thread_id']

    with st.expander(
        f"📩 {email['subject']} | From: {email['sender']} | Category: {email['category']}"
    ):
        st.write(email['body'][:400] + ("..." if len(email['body']) > 400 else ""))

        col1, col2 = st.columns(2)

        # Generate reply
        if col1.button("🤖 Generate AI Reply", key=f"generate_{thread_id}"):
            st.session_state['replies'][thread_id] = generate_ai_reply(email['body'])

        # Skip email
        if col2.button("⏭️ Skip Email", key=f"skip_{thread_id}"):
            st.session_state['skip_flags'][thread_id] = True
            st.rerun()

        # Show reply editor
        if thread_id in st.session_state['replies']:
            reply_text = st.text_area(
                "AI Suggested Reply",
                value=st.session_state['replies'][thread_id],
                height=200,
                key=f"textarea_{thread_id}"
            )

            col_send, col_skip = st.columns(2)

            # Send email
            if col_send.button("📤 Approve & Send", key=f"send_{thread_id}"):
                send_email_reply(
                    to_email=email['sender'],
                    subject=f"Re: {email['subject']}",
                    body=reply_text,
                    thread_id=thread_id
                )

                st.session_state['sent_flags'][thread_id] = True
                del st.session_state['replies'][thread_id]
                st.success("Reply sent ✅")
                st.rerun()

            # Skip reply
            if col_skip.button("❌ Skip Reply", key=f"skip_reply_{thread_id}"):
                st.session_state['skip_flags'][thread_id] = True
                del st.session_state['replies'][thread_id]
                st.rerun()

# Logout button
st.sidebar.button(
    "Logout",
    on_click=lambda: st.session_state.update({"authenticated": False})
)