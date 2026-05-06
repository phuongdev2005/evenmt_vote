"""
Check vote status of all accounts.
"""

import sqlite3
from pathlib import Path
from colorama import Fore, Style, init

init()

DB_FILE = Path("vote/login_cookies.sqlite3")

def check_vote_status():
    """Check which accounts have voted and which haven't."""
    with sqlite3.connect(DB_FILE) as conn:
        # Get all successful accounts with vote status
        rows = conn.execute(
            """
            SELECT email, voted_at, voted_for, updated_at 
            FROM login_cookies 
            WHERE status='success'
            ORDER BY voted_at DESC, updated_at DESC
            """
        ).fetchall()
        
        if not rows:
            print(f"{Fore.RED}No accounts found!{Style.RESET_ALL}")
            return
        
        voted_accounts = []
        unvoted_accounts = []
        
        for row in rows:
            email, voted_at, voted_for, updated_at = row
            account_info = {
                "email": email,
                "voted_at": voted_at,
                "voted_for": voted_for,
                "updated_at": updated_at
            }
            
            if voted_at:
                voted_accounts.append(account_info)
            else:
                unvoted_accounts.append(account_info)
        
        # Summary
        total = len(rows)
        voted_count = len(voted_accounts)
        unvoted_count = len(unvoted_accounts)
        
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}VOTE STATUS SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"Total accounts: {total}")
        print(f"✓ Voted: {voted_count}")
        print(f"○ Not voted: {unvoted_count}")
        print(f"Success rate: {voted_count/total*100:.1f}%")
        
        # Show voted accounts
        if voted_accounts:
            print(f"\n{Fore.GREEN}✓ VOTED ACCOUNTS ({len(voted_accounts)}):{Style.RESET_ALL}")
            for acc in voted_accounts[:10]:  # Show first 10
                vote_time = acc["voted_at"][:19] if acc["voted_at"] else "Unknown"
                vote_target = acc["voted_for"] or "Unknown"
                print(f"  {acc['email']}")
                print(f"    Voted at: {vote_time}")
                print(f"    Voted for: {vote_target}")
            
            if len(voted_accounts) > 10:
                print(f"  ... and {len(voted_accounts) - 10} more")
        
        # Show unvoted accounts
        if unvoted_accounts:
            print(f"\n{Fore.YELLOW}○ NOT VOTED ACCOUNTS ({len(unvoted_accounts)}):{Style.RESET_ALL}")
            for acc in unvoted_accounts[:10]:  # Show first 10
                last_login = acc["updated_at"][:19] if acc["updated_at"] else "Unknown"
                print(f"  {acc['email']} (last login: {last_login})")
            
            if len(unvoted_accounts) > 10:
                print(f"  ... and {len(unvoted_accounts) - 10} more")

if __name__ == "__main__":
    check_vote_status()
