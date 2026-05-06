"""
Export voted/unvoted accounts to txt files.
Usage: python vote/export_accounts.py
"""

import sqlite3
from pathlib import Path

DB_FILE = Path("vote/login_cookies.sqlite3")
VOTED_FILE = Path("vote/voted_accounts.txt")
UNVOTED_FILE = Path("vote/unvoted_accounts.txt")


def export_accounts():
    if not DB_FILE.exists():
        print("Database not found!")
        return

    with sqlite3.connect(DB_FILE) as conn:
        voted_rows = conn.execute(
            "SELECT email FROM login_cookies WHERE status='success' AND voted_at IS NOT NULL ORDER BY email"
        ).fetchall()
        unvoted_rows = conn.execute(
            "SELECT email FROM login_cookies WHERE status='success' AND voted_at IS NULL ORDER BY email"
        ).fetchall()

    # Write voted accounts
    with open(VOTED_FILE, "w", encoding="utf-8") as f:
        for row in voted_rows:
            f.write(row[0] + "\n")

    # Write unvoted accounts
    with open(UNVOTED_FILE, "w", encoding="utf-8") as f:
        for row in unvoted_rows:
            f.write(row[0] + "\n")

    print(f"Voted accounts: {len(voted_rows)} -> {VOTED_FILE}")
    print(f"Unvoted accounts: {len(unvoted_rows)} -> {UNVOTED_FILE}")


if __name__ == "__main__":
    export_accounts()
