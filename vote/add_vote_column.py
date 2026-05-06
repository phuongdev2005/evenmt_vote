"""
Add vote tracking column to login_cookies table.
"""

import sqlite3
from pathlib import Path

DB_FILE = Path("vote/login_cookies.sqlite3")

def add_vote_column():
    """Add voted_at column to track when account voted."""
    with sqlite3.connect(DB_FILE) as conn:
        # Add voted_at column
        conn.execute(
            """
            ALTER TABLE login_cookies 
            ADD COLUMN voted_at TEXT NULL
            """
        )
        print("✓ Added voted_at column")

        # Add voted_for column to track who they voted for
        conn.execute(
            """
            ALTER TABLE login_cookies 
            ADD COLUMN voted_for TEXT NULL
            """
        )
        print("✓ Added voted_for column")

        # Check current accounts
        rows = conn.execute(
            """
            SELECT email, status, voted_at, voted_for 
            FROM login_cookies 
            WHERE status='success'
            """
        ).fetchall()
        
        print(f"\nFound {len(rows)} successful accounts:")
        for row in rows:
            email, status, voted_at, voted_for = row
            vote_status = "✓ Voted" if voted_at else "○ Not voted"
            vote_target = f" for {voted_for}" if voted_for else ""
            print(f"  {email} - {vote_status}{vote_target}")

if __name__ == "__main__":
    add_vote_column()
