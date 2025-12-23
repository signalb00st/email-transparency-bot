"""
Email Transparency Bot
----------------------

Automates the process of fetching emails from Gmail, extracting relevant content, and posting them to Bluesky as threads. Designed for transparency and public archiving of email communications.

Features:
    - Authenticates with Gmail using OAuth2
    - Loads alias mappings and credentials from environment variables (GitHub Secrets)
    - Extracts sender, recipient, subject, date, and body from emails
    - Converts HTML email bodies to plain text
    - Posts email content to Bluesky as threaded posts
    - Archives processed emails
    - Logs all actions and errors to both console and rotating log file

Usage:
    python bot.py
    (or schedule via GitHub Actions / cron)

Required Environment Variables (set as GitHub Secrets):
    EMAIL_USERNAME: Email account username
    EMAIL_PASSWORD: Email account password
    EMAIL_SERVER: Email server address
    EMAIL_PORT: Email server port
    CREDENTIALS_JSON: Gmail API credentials (written to credentials.json)
    ALIAS_*: Alias mappings in the format 'email_alias|bluesky_handle|bluesky_password'

Dependencies:
    - Python 3.11+
    - atproto
    - google-api-python-client
    - google-auth-httplib2
    - google-auth-oauthlib
    - html2text

External Files:
    - credentials.json: Gmail API OAuth2 credentials
    - token.pickle: Gmail API OAuth2 token (auto-generated)

Author: Randy Weaver
License: MIT
"""
import base64
import html2text
import os
import pickle
import re
import logging
from logging.handlers import RotatingFileHandler
from bluesky_post import post_to_bluesky
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
# Configure logging to both console and rotating file
LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'
LOG_FILE = 'bot.log'

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])

# Load email config from environment variables
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_SERVER = os.getenv('EMAIL_SERVER')
EMAIL_PORT = os.getenv('EMAIL_PORT')

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def load_alias_mappings_from_env() -> dict:
    """Load Bluesky alias mappings from environment variables.

    Scans all environment variables for keys starting with 'ALIAS_' and parses their values
    in the format 'email_alias|bluesky_handle|bluesky_password'. Returns a dictionary mapping
    each email alias to its corresponding Bluesky handle and password.

    Returns:
        dict: Mapping of email alias (str) to a dict with 'handle' and 'password' keys.
    """
    alias_dict = {}
    for key, value in os.environ.items():
        if key.startswith('ALIAS_'):
            parts = value.split('|')
            if len(parts) == 3:
                email_alias, bluesky_handle, bluesky_password = parts
                alias_dict[email_alias] = {
                    "handle": bluesky_handle,
                    "password": bluesky_password
                }
    return alias_dict

def fetch_messages_by_label(service, label: str):
    """Retrieve messages from Gmail with the specified label.

    Args:
        service: Authenticated Gmail API service instance.
        label (str): Email label to filter messages (e.g., 'INBOX').

    Returns:
        list: List of message metadata dictionaries.
    """
    results = service.users().messages().list(userId='me', labelIds=[label]).execute()
    messages = results.get('messages', [])
    return messages

def extract_all_text_parts(payload, recipient, parts=None):
    """Recursively extract all text content from an email payload.

    Handles both 'text/plain' and 'text/html' MIME types, converting HTML to plain text.
    Removes hidden HTML blocks and replaces the recipient's email address with a placeholder.
    Returns a list of decoded text parts.

    Args:
        payload (dict): The email payload to process.
        recipient (str): The recipient's email address to be replaced in the text.
        parts (list, optional): Accumulator for extracted text parts (used for recursion).

    Returns:
        list: List of extracted and decoded text strings.
    """
    if parts is None:
        parts = []
    if 'parts' in payload:
        for part in payload['parts']:
            print(f"extracting {payload.get('mimeType')} payload, calling recursively...")
            extract_all_text_parts(part, recipient, parts)
    elif payload.get('mimeType') == 'text/plain':
        print(f"extracting {payload.get('mimeType')} payload, returning...")
        data = payload['body'].get('data', '')
        if data:
            parts.append(base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore'))
    elif payload.get('mimeType') == 'text/html':
        data = payload['body'].get('data', '')
        print(f"extracting {payload.get('mimeType')} payload, returning...")
        if data:
            html_body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            html_body = remove_hidden_blocks(html_body)
            html_body = html_body.replace(recipient, '[open mail project]')
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            h.body_width = 0
            parts.append(h.handle(html_body))
    return parts

def get_gmail_service():
    """Authenticate and return a Gmail API service instance.

    Loads credentials from 'token.pickle' if available and valid, otherwise initiates
    an OAuth flow using 'credentials.json' to obtain new credentials. Credentials are
    refreshed or saved as needed. Returns an authenticated Gmail API service object.

    Returns:
        googleapiclient.discovery.Resource: Authenticated Gmail API service.
    """
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def get_recipient(full_message: dict) -> str:
    """Extract the recipient's email address from a Gmail message.

    Searches the message headers for the 'To' field and returns its value.
    If the 'To' header is not found, returns an empty string.

    Args:
        full_message (dict): The full Gmail message dictionary.

    Returns:
        str: The recipient's email address, or an empty string if not found.
    """
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'to':
            return header['value']
    return ''

def get_sender(full_message: dict) -> str:
    """Extract the sender's email address from a Gmail message.

    Searches the message headers for the 'From' field and returns its value.
    If the 'From' header is not found, returns an empty string.

    Args:
        full_message (dict): The full Gmail message dictionary.

    Returns:
        str: The sender's email address, or an empty string if not found.
    """
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'from':
            return header['value']
    return ''

def get_subject(full_message: dict) -> str:
    """Extract the subject line from a Gmail message.

    Searches the message headers for the 'Subject' field and returns its value.
    If the 'Subject' header is not found, returns an empty string.

    Args:
        full_message (dict): The full Gmail message dictionary.

    Returns:
        str: The subject line, or an empty string if not found.
    """
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'subject':
            return header['value']
    return ''

def get_date(full_message: dict) -> str:
    """Extract the date and time the email was sent from a Gmail message.

    Searches the message headers for the 'Date' field and returns its value.
    If the 'Date' header is not found, returns an empty string.

    Args:
        full_message (dict): The full Gmail message dictionary.

    Returns:
        str: The date and time string, or an empty string if not found.
    """
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'date':
            return header['value']
    return ""

def remove_hidden_blocks(html: str) -> str:
    # Remove <div> or <span> blocks with display:none or visibility:hidden
    """Remove hidden HTML blocks from a string.

    Strips out <div> and <span> elements with CSS styles 'display:none' or 'visibility:hidden'.
    Useful for cleaning up email HTML content before text extraction.

    Args:
        html (str): The HTML string to clean.

    Returns:
        str: The cleaned HTML string with hidden blocks removed.
    """
    pattern = r'<(div|span)[^>]*style=["\'][^"\'>]*(display\s*:\s*none|visibility\s*:\s*hidden)[^"\'>]*["\'][^>]*>.*?</\1>'
    cleaned_html = re.sub(pattern, '', html, flags=re.DOTALL | re.IGNORECASE)
    return cleaned_html

def process_inbox():
    """Main processing loop for the email transparency bot.

    Authenticates with Gmail, loads alias mappings, fetches inbox messages, and processes each message:
    - Extracts recipient, sender, subject, date, and body
    - Posts to Bluesky if recipient matches an alias
    - Archives processed messages
    - Handles and logs errors at each step
    """
    try:
        service = get_gmail_service()
    except Exception as e:
        logging.error(f"Failed to initialize Gmail service: {e}")
        return

    try:
        aliases = load_alias_mappings_from_env()
        inbox_messages = fetch_messages_by_label(service, 'INBOX')
    except Exception as e:
        logging.error(f"Failed to fetch messages or aliases: {e}")
        return

    for message in inbox_messages:
        try:
            full_message = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
        except Exception as e:
            logging.error(f"Failed to fetch full message for ID {message.get('id')}: {e}")
            continue

        try:
            recipient: str = get_recipient(full_message)
            if recipient in aliases:
                handle = aliases[recipient]["handle"]
                password = aliases[recipient]["password"]

                subject: str = get_subject(full_message)
                sender: str = get_sender(full_message)
                date: str = get_date(full_message)
                body = "\n".join(extract_all_text_parts(full_message['payload'], recipient))
                try:
                    num_posts = post_to_bluesky(handle, password, sender, subject, date, body)
                except Exception as e:
                    logging.error(f"Failed to post to Bluesky for {recipient}: {e}")
                    num_posts = 0
                if num_posts == 0:
                    logging.error("✗ Failed to post to Bluesky")
                try:
                    service.users().messages().modify(userId='me', id=message['id'],body={'removeLabelIds': ['INBOX']}).execute()
                except Exception as e:
                    logging.error(f"Failed to archive message {message.get('id')}: {e}")
            else:
                logging.info("→ Skipping (no matching alias)")
        except Exception as e:
            logging.error(f"Error processing message {message.get('id')}: {e}")

if __name__ == "__main__":
    process_inbox()
