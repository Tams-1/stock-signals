#!/usr/bin/env python3
"""
Authorize Google Sheets access - Manual flow (copy/paste auth code)
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import json

# Scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# Paths
CREDENTIALS_FILE = Path.home() / '.openclaw' / 'credentials' / 'gmail_credentials.json'
TOKEN_FILE = Path.home() / 'sheets_token.json'

def main():
    print("🔐 Authorizing Google Sheets access for tarsdabot@gmail.com")
    print("=" * 70)
    
    # Create flow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        SCOPES
    )
    
    # Generate authorization URL
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    print("\n1️⃣  Open this URL in your browser:\n")
    print(auth_url)
    print("\n" + "=" * 70)
    print("2️⃣  Authorize with tarsdabot@gmail.com")
    print("3️⃣  Copy the authorization code from the URL (code=... parameter)")
    print("=" * 70)
    
    # Get auth code from user
    auth_code = input("\nPaste the authorization code here: ").strip()
    
    # Exchange code for token
    flow.fetch_token(code=auth_code)
    creds = flow.credentials
    
    # Save token
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'expiry': creds.expiry.isoformat() if creds.expiry else None
    }
    
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f, indent=2)
    
    print(f"\n✅ Token saved to: {TOKEN_FILE}")
    print("✅ You can now use sheets_sync.py to log signals!")

if __name__ == '__main__':
    main()