#!/usr/bin/env python3
"""
Authorize Google Sheets access for tarsdabot@gmail.com
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
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
    print("=" * 60)
    
    # Load credentials
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_data = json.load(f)
    
    # Create flow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        SCOPES
    )
    
    # Run local server for callback
    print("\nOpening browser for authorization...")
    print("Please authorize with tarsdabot@gmail.com\n")
    
    creds = flow.run_local_server(
        port=0,
        success_message="✅ Authorization successful! You can close this window."
    )
    
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
    print("You can now use sheets_sync.py to log signals!")

if __name__ == '__main__':
    main()