# email-transparency-bot

Automated bot that monitors email aliases and posts received emails to corresponding public Bluesky accounts for organizational transparency.

## Overview

This bot enables organizations to make their email communications transparent by automatically forwarding emails to public Bluesky accounts. One email inbox with multiple aliases can route to different Bluesky accounts based on the recipient.

## Features

- Monitors single email inbox via IMAP
- Routes emails based on recipient alias
- Posts full email content to Bluesky as threaded posts
- Tracks processed emails to prevent duplicates
- Simple configuration via environment variables

## Use Cases

- Political organizations publishing incoming communications
- Transparency initiatives for public accountability
- Open government email disclosure
- Any organization committed to communication transparency

## How It Works

1. Bot connects to email inbox via IMAP
2. Checks for new emails sent to configured aliases
3. Matches email recipient to corresponding Bluesky account
4. Posts email content as a public Bluesky thread
5. Marks email as processed to avoid reposting

## Stack

- Python 3.8+
- IMAP for email monitoring
- [atproto](https://github.com/MarshalX/atproto) for Bluesky integration
- Works with Proton Mail via Proton Bridge

## License

See LICENSE file.
