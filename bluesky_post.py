from atproto import Client, models
import re
import time

def post_to_bluesky(handle: str, password: str, sender: str, subject: str, body: str) -> bool:
    client = Client()
    client.login(handle, password)
    post_text = f"📧 From: {sender}\n\nSubject: {subject}\n\n{body}"
    post_text = re.sub(r'^[ \t]+', '', post_text, flags=re.MULTILINE)  # Remove leading spaces/tabs from each line
    # Remove lines that are only whitespace (including invisible Unicode chars)
    post_text = re.sub(r'^[\s\u200b-\u200d\ufeff\u00ad͏‌]+$', '', post_text, flags=re.MULTILINE)
    # Collapse 3+ newlines to 2
    post_text = re.sub(r'\n{3,}', '\n\n', post_text)
    post_text = post_text.strip()  # Remove leading/trailing whitespace
    post_chunks(post_text, client)
    return True

def post_chunks(post_text, client):
    chunks: list[str] = split_text(post_text)
    root_post = client.send_post(text=chunks[0])
    root_ref = models.create_strong_ref(root_post)
    parent_ref = root_ref
    for chunk in chunks[1:]:
        time.sleep(5) # wait 5 seconds between posts
        reply_to = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=root_ref)
        parent_post = client.send_post(text=chunk, reply_to=reply_to)
        parent_ref = models.create_strong_ref(parent_post)

    print(f"✓ Posted thread with {len(chunks)} parts.")

def split_text(full_text, max_chunk=300) -> list[str]:
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
