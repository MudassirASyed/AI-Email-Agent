import os
import streamlit as st
import threading
import time
from dotenv import load_dotenv
from email_agent import (
    fetch_important_emails,
    generate_ai_reply,
    send_email_reply,
    get_logged_in_user,
    auto_process_emails
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
if 'processed_ids' not in st.session_state:
    st.session_state['processed_ids'] = set()
if 'replies' not in st.session_state:
    st.session_state['replies'] = {}
if 'auto_mode' not in st.session_state:
    st.session_state['auto_mode'] = False

# Logged-in user
user_email = get_logged_in_user()
st.info(f"👤 Logged in as: **{user_email}**")

# Sidebar - Mode Selection
st.sidebar.header("🤖 Agent Mode")

mode = st.sidebar.radio(
    "Select Mode",
    ["Manual (Review & Approve)", "Autonomous (Auto-reply)"],
    help="Manual: You review each reply. Autonomous: AI replies automatically"
)

if mode == "Autonomous (Auto-reply)":
    st.session_state['auto_mode'] = True
    st.sidebar.success("⚡ Autonomous Mode ACTIVE")
    st.sidebar.info("AI will auto-reply to personal/work emails")
    
    # Auto-run button
    if st.sidebar.button("🔄 Run Auto-Process Now"):
        with st.spinner("Processing emails autonomously..."):
            results = auto_process_emails()
            st.sidebar.success(f"Processed {len(results)} emails")
            st.rerun()
    
    # Schedule info
    st.sidebar.markdown("---")
    st.sidebar.caption("For 24/7 automation, deploy with cron job:")
    st.sidebar.code("""# Run every 30 minutes
*/30 * * * * cd /path/to/project && python -c "from email_agent import auto_process_emails; auto_process_emails()" > /dev/null 2>&1
""")
else:
    st.session_state['auto_mode'] = False
    st.sidebar.info("👀 Manual Mode - You control replies")

# Description
st.markdown("""
### What this agent does:
- ✅ Filters out newsletters, promotions, receipts (only personal + work)
- ✅ Classifies emails into Personal / Work
- ✅ Generates AI replies
- ✅ Autonomous mode for 24/7 automation
""")

# Load emails button
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("📥 Load Emails", use_container_width=True):
        emails = fetch_important_emails(max_results=15)
        st.session_state['emails'] = emails
        st.session_state['processed_ids'] = set()
        st.session_state['replies'] = {}
        
        # Filter already processed
        for email in emails:
            if email.get('processed', False):
                st.session_state['processed_ids'].add(email['thread_id'])
        
        st.success(f"Loaded {len(emails)} important emails")
        st.rerun()

with col2:
    st.caption("Shows only Personal & Work emails (automatically filters newsletters/spam)")

# Display emails
emails_to_show = [
    email for email in st.session_state['emails']
    if email['thread_id'] not in st.session_state['processed_ids']
]

if not emails_to_show and st.session_state['emails']:
    st.info("✅ All emails processed! Click 'Load Emails' for new ones.")
elif not emails_to_show:
    st.info("👈 Click 'Load Emails' to fetch your important emails")

for email in emails_to_show:
    thread_id = email['thread_id']
    
    # Category badge
    category_color = "#4CAF50" if email['category'] == 'personal' else "#2196F3"
    
    with st.expander(
        f"📩 {email['subject']} | From: {email['sender']} | "
        f"<span style='background:{category_color}; color:white; padding:2px 8px; border-radius:12px; font-size:12px;'>{email['category'].upper()}</span>",
        expanded=False
    ):
        st.write(f"**Body:**\n{email['body'][:600]}...")
        st.caption(f"📌 Classification reason: {email.get('classification_reason', 'N/A')}")
        
        if st.session_state['auto_mode']:
            st.info("🤖 Autonomous mode active - this email will be processed automatically")
            # Auto-process in background
            if st.button(f"⚡ Process Now", key=f"auto_{thread_id}"):
                reply = generate_ai_reply(email['body'], email['sender'], email['category'])
                send_email_reply(email['sender'], email['subject'], reply, thread_id)
                st.session_state['processed_ids'].add(thread_id)
                st.success("Reply sent automatically!")
                st.rerun()
        else:
            # Manual mode
            col1, col2 = st.columns(2)
            
            if col1.button("🤖 Generate Reply", key=f"gen_{thread_id}"):
                st.session_state['replies'][thread_id] = generate_ai_reply(
                    email['body'], email['sender'], email['category']
                )
            
            if col2.button("⏭️ Skip", key=f"skip_{thread_id}"):
                st.session_state['processed_ids'].add(thread_id)
                st.rerun()
            
            # Show reply editor if generated
            if thread_id in st.session_state['replies']:
                reply_text = st.text_area(
                    "✏️ Edit Reply",
                    value=st.session_state['replies'][thread_id],
                    height=200,
                    key=f"textarea_{thread_id}"
                )
                
                col_send, col_cancel = st.columns(2)
                if col_send.button("📤 Approve & Send", key=f"send_{thread_id}"):
                    send_email_reply(email['sender'], email['subject'], reply_text, thread_id)
                    st.session_state['processed_ids'].add(thread_id)
                    del st.session_state['replies'][thread_id]
                    st.success("Reply sent!")
                    st.rerun()
                
                if col_cancel.button("❌ Cancel", key=f"cancel_{thread_id}"):
                    del st.session_state['replies'][thread_id]
                    st.rerun()

# Logout
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()