"""
Remove accounts already in database and duplicates from account.txt.
"""

import sqlite3
from pathlib import Path

DB_FILE = Path("vote/login_cookies.sqlite3")
ACCOUNT_FILE = Path("vote/account.txt")

def clean_accounts():
    # Get saved emails from database
    saved_emails = set()
    if DB_FILE.exists():
        with sqlite3.connect(DB_FILE) as conn:
            rows = conn.execute(
                "SELECT email FROM login_cookies WHERE status='success'"
            ).fetchall()
            saved_emails = {row[0] for row in rows}
    
    print(f"Accounts in database: {len(saved_emails)}")
    
    # Read account file
    if not ACCOUNT_FILE.exists():
        print("account.txt not found!")
        return
    
    with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
        all_accounts = [line.strip() for line in f if line.strip()]
    
    original_count = len(all_accounts)
    print(f"Total accounts in file: {original_count}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_accounts = []
    for email in all_accounts:
        if email not in seen:
            seen.add(email)
            unique_accounts.append(email)
    
    duplicates_removed = original_count - len(unique_accounts)
    print(f"Duplicates removed: {duplicates_removed}")
    
    # Remove accounts already in database
    new_accounts = [email for email in unique_accounts if email not in saved_emails]
    db_removed = len(unique_accounts) - len(new_accounts)
    
    print(f"Already in database (removed): {db_removed}")
    print(f"Remaining accounts: {len(new_accounts)}")
    
    # Save back to file
    with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
        for email in new_accounts:
            f.write(email + '\n')
    
    print(f"\nSaved {len(new_accounts)} accounts to {ACCOUNT_FILE}")

if __name__ == "__main__":
    clean_accounts()
