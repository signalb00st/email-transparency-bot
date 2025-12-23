"""
Bluesky Posting Utilities
------------------------

Provides functions to format and post email content as threaded posts to Bluesky using the atproto API.

Features:
    - Authenticates and posts to Bluesky using provided handle and password
    - Formats email content for posting, including sender, subject, date, and body
    - Splits long content into chunks and posts as a threaded conversation
    - Handles errors and logs actions to both console and rotating log file

Usage:
    Import and call post_to_bluesky(handle, password, sender, subject, date, body)
    Returns the number of posts made (0 on failure).

Required Arguments:
    handle (str): Bluesky account handle
    password (str): Bluesky account password
    sender (str): Email sender
    subject (str): Email subject
    date (str): Email sent date
    body (str): Email body text

Dependencies:
    - Python 3.11+
    - atproto
    - logging

Notes:
    - Designed to be called from the main bot script after extracting email content.
    - Uses a 5-second delay between posts to avoid rate limits.

Author: Randy Weaver
License: MIT
"""
from atproto import Client, models
import re
import time
import logging
logger = logging.getLogger(__name__)

def post_to_bluesky(handle: str, password: str, sender: str, subject: str, date: str, body: str) -> int:
    """Format and post email content as a threaded conversation to Bluesky.

    Authenticates with Bluesky using the provided handle and password, formats the email
    content, and posts it as a thread (splitting into multiple posts if needed).

    Args:
        handle (str): Bluesky account handle.
        password (str): Bluesky account password.
        sender (str): Email sender address.
        subject (str): Email subject line.
        date (str): Email sent date/time.
        body (str): Email body text.

    Returns:
        int: Number of posts made (0 on failure).

    Raises:
        Exception: If client initialization, login, formatting, or posting fails.
    """
    logger = logging.getLogger(__name__)
    try:
        client = Client()
        client.login(handle, password)
    except Exception as e:
        logger.error(f"Failed to initialize or login Bluesky client for {handle}: {e}")
        raise
    try:
        post_text = f"📧 From: {sender}\nSubject: {subject}\nSent: {date}\n{body}"
        post_text = re.sub(r'^[ \t]+', '', post_text, flags=re.MULTILINE)  # Remove leading spaces/tabs from each line
        # Remove lines that are only whitespace (including invisible Unicode chars)
        post_text = re.sub(r'^[\s\u200b-\u200d\ufeff\u00ad͏‌]+$', '', post_text, flags=re.MULTILINE)
        # Collapse 3+ newlines to 2
        post_text = re.sub(r'\n{3,}', '\n\n', post_text)
        post_text = post_text.strip()  # Remove leading/trailing whitespace
    except Exception as e:
        logger.error(f"Failed to format post text for {handle}: {e}")
        raise
    return post_chunks(post_text, client)

def post_chunks(post_text, client):
    """Post a long text to Bluesky as a threaded conversation.

    Splits the input text into chunks, posts the first chunk as the root post,
    and replies to it with subsequent chunks to form a thread. Waits 5 seconds
    between posts to avoid rate limits. Logs actions and errors.

    Args:
        post_text (str): The full text to post.
        client (Client): Authenticated Bluesky API client.

    Returns:
        int: Number of posts made.

    Raises:
        Exception: If posting fails or if there is no content to post.
    """
    chunks: list[str] = split_text(post_text)
    if not chunks:
        logger.error("No content to post.")
        raise ValueError("No content to post.")
    try:
        root_post = client.send_post(text=chunks[0])
        root_ref = models.create_strong_ref(root_post)
        parent_ref = root_ref
        for chunk in chunks[1:]:
            time.sleep(5) # wait 5 seconds between posts
            reply_to = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
            parent_post = client.send_post(text=chunk, reply_to=reply_to)
            parent_ref = models.create_strong_ref(parent_post)
        logger.info(f"✓ Posted thread with {len(chunks)} parts.")
        return len(chunks)
    except Exception as e:
        logger.error(f"Error posting thread: {e}")
        raise

def split_text(full_text, max_chunk=300) -> list[str]:
    """Split a long text into chunks suitable for posting.

    Breaks the input text into chunks of up to max_chunk characters, attempting to split
    at word boundaries when possible. Returns a list of chunked strings.

    Args:
        full_text (str): The full text to split.
        max_chunk (int, optional): Maximum chunk size in characters (default: 300).

    Returns:
        list[str]: List of chunked strings.
    """
    chunks = []
    start = 0
    while start < len(full_text):
        # Get a chunk
        end = start + max_chunk
        chunk = full_text[start:end]
        # Try to break at word boundary
        if end < len(full_text):
            last_space = chunk.rfind(' ') + 1
            if last_space > max_chunk - 50:
                end = start + last_space
                chunk = full_text[start:end]
        chunks.append(chunk.strip())
        start = end
    return chunks
