# import os
# import base64
# from googleapiclient.discovery import build
# from google_auth_oauthlib.flow import InstalledAppFlow
# from groq import Groq
# import pickle
# from dotenv import load_dotenv

# SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# def classify_email(body):
#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=[
#             {
#                 "role": "system",
#                 "content": "Classify emails into: Support, Spam, Newsletter, Personal, Job. Return only one word."
#             },
#             {
#                 "role": "user",
#                 "content": body[:1000]
#             }
#         ]
#     )

#     return response.choices[0].message.content
# def main():
#     creds = None

#     if os.path.exists('token.pickle'):
#         with open('token.pickle', 'rb') as token:
#             creds = pickle.load(token)

#     if not creds or not creds.valid:
#         flow = InstalledAppFlow.from_client_secrets_file(
#             'credentials.json', SCOPES
#         )
#         creds = flow.run_local_server(port=0)

#         with open('token.pickle', 'wb') as token:
#             pickle.dump(creds, token)

#     service = build('gmail', 'v1', credentials=creds)

#     results = service.users().messages().list(
#         userId='me', maxResults=5
#     ).execute()

#     messages = results.get('messages', [])

#     if not messages:
#         print('No messages found.')
#     else:
#         print('Last 5 emails:')
#         for message in messages:
#             msg = service.users().messages().get(
#                 userId='me', id=message['id']
#             ).execute()

#             headers = msg['payload']['headers']
#             subject = ""
#             sender = ""

#             for header in headers:
#                 if header['name'] == 'Subject':
#                     subject = header['value']
#                 if header['name'] == 'From':
#                     sender = header['value']

#             # Extract body
#             body = ""
#             parts = msg['payload'].get('parts')

#             if parts:
#                 for part in parts:
#                     if part['mimeType'] == 'text/plain':
#                         data = part['body'].get('data')
#                         if data:
#                             body = base64.urlsafe_b64decode(data).decode('utf-8')
#             else:
#                 data = msg['payload']['body'].get('data')
#                 if data:
#                     body = base64.urlsafe_b64decode(data).decode('utf-8')
#             category = classify_email(body)

            
#             print("Subject:", subject)
#             print("From:", sender)
#             print("Body:", body[:200])
#             print("Category:", category)
#             print("-" * 50)


# if __name__ == '__main__':
#     main()