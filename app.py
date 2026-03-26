import streamlit as st
from email_agent import (
    fetch_latest_emails,
    generate_ai_reply,
    send_email_reply,
    get_logged_in_user
)

st.set_page_config(page_title="AI Email Agent", layout="wide")
st.title("AI Email Agent")

# Initialize session state
if 'emails' not in st.session_state:
    st.session_state['emails'] = []
if 'skip_flags' not in st.session_state:
    st.session_state['skip_flags'] = {}
if 'sent_flags' not in st.session_state:
    st.session_state['sent_flags'] = {}
if 'replies' not in st.session_state:
    st.session_state['replies'] = {}

# Display logged-in user
user_email = get_logged_in_user()
st.info(f"Logged in as: {user_email}")

# App description
st.markdown("""
This AI Email Agent helps you manage your inbox efficiently:

- Automatically classifies incoming emails (Support, Personal, Job, Newsletter, Spam)
- Suggests professional replies using AI
- Lets you **approve, edit, or skip** AI-generated replies
- Ensures no replies are sent to no-reply or newsletter emails
""")

# Load Emails
if st.button("Load Emails"):
    emails = fetch_latest_emails(max_results=10)
    st.session_state['emails'] = emails
    st.session_state['skip_flags'] = {}
    st.session_state['sent_flags'] = {}
    st.session_state['replies'] = {}
    st.success(f"Loaded {len(emails)} emails.")

# Filter emails to display (skip sent, skipped, or own emails)
emails_to_show = [
    email for email in st.session_state['emails']
    if not st.session_state['sent_flags'].get(email['thread_id'], False)
    and not st.session_state['skip_flags'].get(email['thread_id'], False)
    and email['sender'].lower() != user_email.lower()
]

# Display emails
for email in emails_to_show:
    thread_id = email['thread_id']
    with st.expander(f"{email['subject']} - From: {email['sender']} ({email['category']})"):
        st.write(email['body'][:300] + ("..." if len(email['body']) > 300 else ""))

        col1, col2 = st.columns(2)

        # Generate AI Reply
        if st.button("Generate AI Reply", key=f"generate_{thread_id}"):
            st.session_state['replies'][thread_id] = generate_ai_reply(email['body'])

        # Skip Email
        if st.button("Skip Email", key=f"skip_{thread_id}"):
            st.session_state['skip_flags'][thread_id] = True

        # Show AI reply if generated
        if thread_id in st.session_state['replies']:
            reply_text = st.text_area(
                f"AI Suggested Reply for {email['subject']}",
                value=st.session_state['replies'][thread_id],
                height=200,
                key=f"textarea_{thread_id}"
            )

            col_send, col_skip_reply = st.columns(2)
            if col_send.button("Approve & Send", key=f"send_{thread_id}"):
                send_email_reply(
                    to_email=email['sender'],
                    subject=f"Re: {email['subject']}",
                    body=reply_text,
                    thread_id=thread_id
                )
                st.session_state['sent_flags'][thread_id] = True
                del st.session_state['replies'][thread_id]

            if col_skip_reply.button("Skip Reply", key=f"skip_reply_{thread_id}"):
                st.session_state['skip_flags'][thread_id] = True
                del st.session_state['replies'][thread_id]