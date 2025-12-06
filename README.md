# email-transparency-bot
Automated bot that forwards organizational emails to public Bluesky accounts for transparency.

## Overview

This bot monitors a single email inbox (with multiple aliases) and automatically posts received emails to corresponding Bluesky accounts. Perfect for making organizational communications transparent and accessible.

## Features

- ✉️ Monitors single Proton Mail inbox via IMAP
- 🔀 Routes emails based on recipient alias
- 🦋 Posts to corresponding Bluesky accounts
- 📝 Tracks processed emails to avoid duplicates
- ⚙️ Simple configuration via environment variables

## Setup

### 1. Prerequisites

- Python 3.8+
- Proton Mail account with Bridge (for IMAP access)
- Bluesky accounts for each organization you're monitoring

### 2. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Proton Bridge

1. Download and install [Proton Bridge](https://proton.me/mail/bridge)
2. Start Proton Bridge and sign in with your account
3. Note the IMAP server and port (usually `127.0.0.1:1143`)
4. Copy the Bridge password (not your regular Proton password)

### 4. Set Up Email Aliases

In your Proton Mail account, set up aliases for each organization:
- Use a service like SimpleLogin (built into Proton) or ProtonMail's alias feature
- Example: `dnc@openemailproject.simplelogin.com`, `rnc@openemailproject.simplelogin.com`

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```
EMAIL_SERVER=127.0.0.1
EMAIL_PORT=1143
EMAIL_USERNAME=openemailproject@proton.me
EMAIL_PASSWORD=your_proton_bridge_password

# Add an ALIAS line for each organization
ALIAS_DNC=dnc@openemailproject.simplelogin.com|dnc-transparency.bsky.social|bluesky_password
ALIAS_RNC=rnc@openemailproject.simplelogin.com|rnc-transparency.bsky.social|bluesky_password
```

### 6. Run the Bot

```bash
python bot.py
```

The bot will:
1. Connect to your email inbox
2. Check for new emails
3. Match recipient aliases to Bluesky accounts
4. Post email content to the appropriate Bluesky account

## Usage

### One-time Run

```bash
python bot.py
```

### Continuous Monitoring (Cron)

Add to your crontab to run every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path as needed)
*/5 * * * * cd /path/to/email-transparency-bot && /path/to/venv/bin/python bot.py >> logs/bot.log 2>&1
```

### Running as a Service (systemd)

Create `/etc/systemd/system/email-transparency-bot.service`:

```ini
[Unit]
Description=Email Transparency Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/email-transparency-bot
Environment="PATH=/path/to/email-transparency-bot/venv/bin"
ExecStart=/path/to/email-transparency-bot/venv/bin/python bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Adding New Organizations

1. Create a new Bluesky account for the organization
2. Set up a new email alias in Proton Mail
3. Add a new `ALIAS_*` line to your `.env` file:

```
ALIAS_NEWORG=neworg@openemailproject.simplelogin.com|neworg-transparency.bsky.social|password
```

4. Restart the bot

## Security Notes

- Never commit your `.env` file to git
- Use strong, unique passwords for each Bluesky account
- Consider using app-specific passwords where supported
- The `.gitignore` is configured to exclude sensitive files

## Troubleshooting

**"Login failed"**: Make sure you're using the Proton Bridge password, not your regular Proton password

**"No matching alias found"**: Check that the email's recipient field matches exactly with your configured aliases

**"Bluesky post failed"**: Verify your Bluesky credentials and that the account isn't rate-limited

## License

See LICENSE file. 
