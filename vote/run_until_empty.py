"""
Run open_profiles.py repeatedly until account.txt is empty.
Usage: python vote/run_until_empty.py
"""

import subprocess
import sys
from pathlib import Path
from colorama import Fore, Style, init

init()

ACCOUNT_FILE = Path("vote/account.txt")
SCRIPT = "vote/open_profiles.py"

def count_accounts():
    if not ACCOUNT_FILE.exists():
        return 0
    with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
        return sum(1 for line in f if line.strip())

def main():
    remaining = count_accounts()
    if remaining == 0:
        print(f"\n{Fore.GREEN}✓ No accounts to process!{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Processing {remaining} accounts in one run{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")

    subprocess.run(
        [sys.executable, SCRIPT],
        cwd=Path(__file__).parent.parent
    )

if __name__ == "__main__":
    main()
