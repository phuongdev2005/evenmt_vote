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
    round_num = 0
    while True:
        remaining = count_accounts()
        if remaining == 0:
            print(f"\n{Fore.GREEN}✓ All accounts processed!{Style.RESET_ALL}")
            break
        
        round_num += 1
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Round {round_num}: {remaining} accounts remaining{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        result = subprocess.run(
            [sys.executable, SCRIPT],
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode != 0:
            print(f"{Fore.YELLOW}Script exited with error, retrying in 5s...{Style.RESET_ALL}")
            import time
            time.sleep(5)

if __name__ == "__main__":
    main()
