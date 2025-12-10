import base64
import html2text
import os
import pickle
import re
from bluesky_post import post_to_bluesky
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

#  @@@@@@@   @@@@@@   @@@  @@@   @@@@@@   @@@@@@@   @@@@@@   @@@  @@@  @@@@@@@   @@@@@@   
# @@@@@@@@  @@@@@@@@  @@@@ @@@  @@@@@@@   @@@@@@@  @@@@@@@@  @@@@ @@@  @@@@@@@  @@@@@@@   
# !@@       @@!  @@@  @@!@!@@@  !@@         @@!    @@!  @@@  @@!@!@@@    @@!    !@@       
# !@!       !@!  @!@  !@!!@!@!  !@!         !@!    !@!  @!@  !@!!@!@!    !@!    !@!       
# !@!       @!@  !@!  @!@ !!@!  !!@@!!      @!!    @!@!@!@!  @!@ !!@!    @!!    !!@@!!    
# !!!       !@!  !!!  !@!  !!!   !!@!!!     !!!    !!!@!!!!  !@!  !!!    !!!     !!@!!!   
# :!!       !!:  !!!  !!:  !!!       !:!    !!:    !!:  !!!  !!:  !!!    !!:         !:!  
# :!:       :!:  !:!  :!:  !:!      !:!     :!:    :!:  !:!  :!:  !:!    :!:        !:!   
#  ::: :::  ::::: ::   ::   ::  :::: ::      ::    ::   :::   ::   ::     ::    :::: ::   
#  :: :: :   : :  :   ::    :   :: : :       :      :   : :  ::    :      :     :: : :                                                                                        

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# @@@@@@@@  @@@  @@@  @@@  @@@   @@@@@@@  @@@@@@@  @@@   @@@@@@   @@@  @@@                      
# @@@@@@@@  @@@  @@@  @@@@ @@@  @@@@@@@@  @@@@@@@  @@@  @@@@@@@@  @@@@ @@@                      
# @@!       @@!  @@@  @@!@!@@@  !@@         @@!    @@!  @@!  @@@  @@!@!@@@                      
# !@!       !@!  @!@  !@!!@!@!  !@!         !@!    !@!  !@!  @!@  !@!!@!@!                      
# @!!!:!    @!@  !@!  @!@ !!@!  !@!         @!!    !!@  @!@  !@!  @!@ !!@!                      
# !!!!!:    !@!  !!!  !@!  !!!  !!!         !!!    !!!  !@!  !!!  !@!  !!!                      
# !!:       !!:  !!!  !!:  !!!  :!!         !!:    !!:  !!:  !!!  !!:  !!!                      
# :!:       :!:  !:!  :!:  !:!  :!:         :!:    :!:  :!:  !:!  :!:  !:!                      
#  ::       ::::: ::   ::   ::   ::: :::     ::     ::  ::::: ::   ::   ::                      
#  :         : :  :   ::    :    :: :: :     :     :     : :  :   ::    :                       

# @@@@@@@   @@@@@@@@  @@@@@@@@  @@@  @@@  @@@  @@@  @@@@@@@  @@@   @@@@@@   @@@  @@@   @@@@@@   
# @@@@@@@@  @@@@@@@@  @@@@@@@@  @@@  @@@@ @@@  @@@  @@@@@@@  @@@  @@@@@@@@  @@@@ @@@  @@@@@@@   
# @@!  @@@  @@!       @@!       @@!  @@!@!@@@  @@!    @@!    @@!  @@!  @@@  @@!@!@@@  !@@       
# !@!  @!@  !@!       !@!       !@!  !@!!@!@!  !@!    !@!    !@!  !@!  @!@  !@!!@!@!  !@!       
# @!@  !@!  @!!!:!    @!!!:!    !!@  @!@ !!@!  !!@    @!!    !!@  @!@  !@!  @!@ !!@!  !!@@!!    
# !@!  !!!  !!!!!:    !!!!!:    !!!  !@!  !!!  !!!    !!!    !!!  !@!  !!!  !@!  !!!   !!@!!!   
# !!:  !!!  !!:       !!:       !!:  !!:  !!!  !!:    !!:    !!:  !!:  !!!  !!:  !!!       !:!  
# :!:  !:!  :!:       :!:       :!:  :!:  !:!  :!:    :!:    :!:  :!:  !:!  :!:  !:!      !:!   
#  :::: ::   :: ::::   ::        ::   ::   ::   ::     ::     ::  ::::: ::   ::   ::  :::: ::   
# :: :  :   : :: ::    :        :    ::    :   :       :     :     : :  :   ::    :   :: : :    

def fetch_messages_by_label(service, label: str):
    """
    Get messages with a certain label. 
    
    :param label: email label (e.g., INBOX)
    :type label: str
    """
    results = service.users().messages().list(userId='me', labelIds=[label]).execute()
    messages = results.get('messages', [])
    return messages

def load_alias_mappings(env_path: str = ".env") -> dict:
    alias_dict = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("ALIAS_") and "=" in line:
                key, value = line.split("=", 1)
                parts = value.split("|")
                if len(parts) == 3:
                    email_alias, bluesky_handle, bluesky_password = parts
                    alias_dict[email_alias] = {
                        "handle": bluesky_handle,
                        "password": bluesky_password
                    }
    return alias_dict

def extract_all_text_parts(payload, recipient, parts=None):
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
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'to':
            return header['value']
    return ''

def get_sender(full_message: dict) -> str:
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'from':
            return header['value']
    return ''

def get_subject(full_message: dict) -> str:
    for header in full_message['payload']['headers']:
        if header['name'].lower() == 'subject':
            return header['value']
    return ''

def remove_hidden_blocks(html: str) -> str:
    # Remove <div> or <span> blocks with display:none or visibility:hidden
    pattern = r'<(div|span)[^>]*style=["\'][^"\'>]*(display\s*:\s*none|visibility\s*:\s*hidden)[^"\'>]*["\'][^>]*>.*?</\1>'
    cleaned_html = re.sub(pattern, '', html, flags=re.DOTALL | re.IGNORECASE)
    return cleaned_html

service = get_gmail_service()
aliases = load_alias_mappings()
inbox_messages = fetch_messages_by_label(service, 'INBOX')

for message in inbox_messages:
    full_message = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    
    # check recipient against .env, if match found, post to bluesky
    recipient: str = get_recipient(full_message)
    if recipient in aliases:
        handle = aliases[recipient]["handle"]
        password = aliases[recipient]["password"]

        # post to bluesky
        # get subject and body
        subject: str = get_subject(full_message)
        sender: str = get_sender(full_message)
        body = "\n".join(extract_all_text_parts(full_message['payload'], recipient))
        success = post_to_bluesky(handle, password, sender, subject, body)
        if not success:
            print("✗ Failed to post to Bluesky")
        
        # archive (remove inbox label)
        service.users().messages().modify(userId='me', id=message['id'],body={'removeLabelIds': ['INBOX']}).execute()
    
    else:
        print("→ Skipping (no matching alias)")
        # archive? Not sure...
