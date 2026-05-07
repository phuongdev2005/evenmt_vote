"""
Check database and account status for sms_tool.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_FILE = SCRIPT_DIR / "vote_cookies.sqlite3"
ACCOUNT_FILE = SCRIPT_DIR / "smsaccount.txt"
FAILED_FILE = SCRIPT_DIR / "failed_sms.txt"
RESULTS_FILE = SCRIPT_DIR / "results_sms.txt"


def count_accounts() -> int:
    if not ACCOUNT_FILE.exists():
        return 0
    with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def count_lines(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    with open(filepath, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def check_db():
    print(f"{'='*60}")
    print("SMS TOOL STATUS CHECK")
    print(f"{'='*60}")

    # File counts
    print("\n--- FILES ---")
    print(f"  smsaccount.txt  : {count_accounts()} accounts pending")
    print(f"  failed_sms.txt  : {count_lines(FAILED_FILE)} failed")
    print(f"  results_sms.txt : {count_lines(RESULTS_FILE)} registered OK")

    if not DB_FILE.exists():
        print(f"\n  Database not found: {DB_FILE}")
        return

    with sqlite3.connect(DB_FILE) as conn:
        # Login stats
        print("\n--- LOGIN COOKIES ---")
        total = conn.execute("SELECT COUNT(*) FROM login_cookies").fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM login_cookies WHERE status='success'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM login_cookies WHERE status!='success'").fetchone()[0]
        print(f"  Total records : {total}")
        print(f"  Success       : {success}")
        print(f"  Failed        : {failed}")

        # Vote stats
        print("\n--- VOTES ---")
        total_votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        unique_voters = conn.execute("SELECT COUNT(DISTINCT email) FROM votes").fetchone()[0]
        print(f"  Total votes   : {total_votes}")
        print(f"  Unique voters : {unique_voters}")

        # Pending (login success but not voted)
        print("\n--- PENDING (login OK, not voted) ---")
        rows = conn.execute(
            """
            SELECT email FROM login_cookies
            WHERE status='success'
            AND email NOT IN (SELECT DISTINCT email FROM votes)
            """
        ).fetchall()
        print(f"  Count: {len(rows)}")
        if rows:
            print("  Accounts:")
            for row in rows:
                print(f"    - {row[0]}")

        # Vote details by target
        print("\n--- VOTE BY TARGET ---")
        targets = conn.execute(
            "SELECT target_id, COUNT(*) FROM votes GROUP BY target_id"
        ).fetchall()
        for target_id, cnt in targets:
            print(f"  {target_id}: {cnt} votes")

        # Recent votes
        print("\n--- LAST 10 VOTES ---")
        rows = conn.execute(
            "SELECT email, target_id, voted_at FROM votes ORDER BY voted_at DESC LIMIT 10"
        ).fetchall()
        for email, target_id, voted_at in rows:
            print(f"  {voted_at} | {email} -> {target_id}")

        # Recent logins
        print("\n--- LAST 10 LOGINS ---")
        rows = conn.execute(
            "SELECT email, status, updated_at FROM login_cookies ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
        for email, status, updated_at in rows:
            marker = "OK" if status == "success" else "FAIL"
            print(f"  {updated_at} | {email} [{marker}]")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    check_db()
