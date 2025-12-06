#!/usr/bin/env python3
import email
import imaplib
import json
import os
import re
import time
from atproto import Client, models
from dotenv import load_dotenv

PROCESSED_FILE = 'processed_emails.txt'

def save_emails_to_file(emails, filename='emails_cache.json'):
    """Save email data to a JSON file for offline testing"""
    with open(filename, 'w') as f:
        json.dump(emails, f, indent=2)
    print(f"✓ Saved {len(emails)} emails to {filename}")

def load_emails_from_file(filename='emails_cache.json'):
    """Load email data from JSON file"""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def load_processed_ids():
    """Load the set of already processed email IDs"""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE,'r') as f:
            return set(line.strip() for line in f)
    return set()
    
def save_processed_id(email_id):
    """Save an email ID as processed"""
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{email_id}\n")

def clean_email_text(text):
    """Remove HTML artifacts and clean up email text"""
    # Remove image references like ![Alt text][1]
    text = re.sub(r'!\[.*?\]\[\d+\]', '', text)
    # Remove link references like [1]: url
    text = re.sub(r'\[\d+\]:\s*https?://\S+', '', text)
    # Remove multiple blank lines
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text

def load_alias_mappings():
    """Load all ALIAS_* mappings from .env"""
    mappings = {}
    for key, value in os.environ.items():
        if key.startswith('ALIAS_'):
            try:
                alias_email, bsky_handle, bsky_password = value.split('|')
                mappings[alias_email.lower()] = {
                    'handle': bsky_handle,
                    'password': bsky_password,
                    'org_name': key.replace('ALIAS_', '')
                }
            except ValueError:
                print(f"Warning: Invalid format for {key}")
    return mappings

# Get the alias mappings from .env, the emails will be checked against these
alias_mappings = load_alias_mappings()

EMAIL_SERVER = os.getenv('EMAIL_SERVER')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

print("Connecting to Gmail...")
mail = imaplib.IMAP4_SSL(EMAIL_SERVER, EMAIL_PORT)
mail.login(EMAIL_USERNAME, EMAIL_PASSWORD)
print("✓ Connected successfully!")

# Select inbox
mail.select('INBOX')

# Search for all emails
status, messages = mail.search(None, 'ALL')
email_ids = messages[0].split()

print(f"Found {len(email_ids)} emails in inbox")

#Show the last 3 email IDs
print(f"Last 3 email IDs: {email_ids[-3:]}")

processed_ids = load_processed_ids()

# Fetch and display email details
for email_id in email_ids[-5:]:
    email_id_str = email_id.decode()

    # Skip if already processed
    if email_id_str in processed_ids:
        print(f"\n--- Email {email_id_str} ---")
        print("→ Already processed, skipping")
        continue

    status, msg_data = mail.fetch(email_id, '(RFC822)')
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    subject = msg['Subject']
    to_addr = msg['To']
    from_addr = msg['From']

    print(f"\n--- Email {email_id_str} ---")
    print(f"To: {to_addr}")
    print(f"From: {from_addr}")
    print(f"Subject: {subject}")

    # Check if this email matches any configured alias
    matched_alias = None
    for alias_email, config in alias_mappings.items():
        if alias_email in to_addr.lower():
            matched_alias = (alias_email, config)
            break

    # If email is a match, post it!
    if matched_alias:
        alias_email, config = matched_alias
        print(f"→ This is a {config['org_name']} email!")

        # Extract body text
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    body = clean_email_text(body)
                    print(f"Body preview: {body[:200]}...")
                    break
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            body = clean_email_text(body)
            print(f"Body preview: {body[:200]}...")

        # Post to Bluesky using config['handle'] and config['password']
        client = Client()
        client.login(config['handle'], config['password'])

        print("Posting to Bluesky...")
        post_header = f"📧 From: {from_addr}\nSubject: {subject}\n\n"
        full_text = post_header + body

        # Split into chunks (Bluesky allows ~300 chars)
        max_chunk = 280
        chunks = []
        start = 0

        while start < len(full_text):
            # Get a chunk
            end = start + max_chunk
            chunk = full_text[start:end]
            
            # Try to break at word boundary
            if end < len(full_text):
                last_space = chunk.rfind(' ')
                if last_space > max_chunk - 50:
                    end = start + last_space
                    chunk = full_text[start:end]
            
            chunks.append(chunk.strip())
            start = end

        # Post as thread
        # First post
        try:
            root_post = client.send_post(text=chunks[0])

            # Reply to first post with remaining chunks
            parent_ref = models.create_strong_ref(root_post)
            for chunk in chunks[1:]:
                time.sleep(5) # wait 5 seconds between posts
                reply_to = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=parent_ref)
                parent_post = client.send_post(text=chunk, reply_to=reply_to)
                parent_ref = models.create_strong_ref(parent_post)

            print(f"✓ Posted thread with {len(chunks)} parts to {config['handle']}")
            save_processed_id(email_id_str)

        except Exception as e:
            print(f"✗ Failed to post: {e}")
    else:
        print("→ Skipping (no matching alias)")

mail.close()
mail.logout()
