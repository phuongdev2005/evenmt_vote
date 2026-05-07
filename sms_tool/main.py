"""
Full workflow: register accounts -> login -> save cookies -> vote.
Runs register.py first, then vote.py.
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def run_register(count: int, api_key: str, domain: str, password: str) -> bool:
    """Step 1: Register accounts via SmailPro."""
    print(f"\n{'='*60}")
    print("STEP 1: REGISTER ACCOUNTS")
    print(f"{'='*60}")
    cmd = [
        sys.executable, str(SCRIPT_DIR / "register.py"),
        "--count", str(count),
        "--api-key", api_key,
        "--domain", domain,
    ]
    if password:
        cmd += ["--password", password]
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    return result.returncode == 0


def run_vote(target: str, limit: int = 0) -> bool:
    """Step 2: Login and vote."""
    print(f"\n{'='*60}")
    print("STEP 2: LOGIN AND VOTE")
    print(f"{'='*60}")
    cmd = [
        sys.executable, str(SCRIPT_DIR / "vote.py"),
        "--target", target,
    ]
    if limit > 0:
        cmd += ["--limit", str(limit)]
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    return result.returncode == 0


def run_vote_only(target: str, limit: int = 0) -> bool:
    """Vote from existing DB without re-login."""
    print(f"\n{'='*60}")
    print("VOTE ONLY (from DB)")
    print(f"{'='*60}")
    cmd = [
        sys.executable, str(SCRIPT_DIR / "vote.py"),
        "--target", target,
        "--vote-only",
    ]
    if limit > 0:
        cmd += ["--limit", str(limit)]
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Full workflow: register -> login -> vote")
    parser.add_argument("--count", type=int, default=5, help="Number of accounts to register")
    parser.add_argument("--api-key", default="9cb5fe11b14da95a62d63efbf8a0e86cfe52483672801c8beefa334f04a628bb", help="SmailPro API key")
    parser.add_argument("--domain", default="gmail.com", help="Email domain")
    parser.add_argument("--password", default="", help="Fixed password")
    parser.add_argument("--target", default="69e1fe40de1b6fbcd4b30990", help="Target candidate ID")
    parser.add_argument("--limit", type=int, default=0, help="Limit accounts to vote (0=all)")
    parser.add_argument("--vote-only", action="store_true", help="Skip register, vote existing accounts only")
    parser.add_argument("--loop", action="store_true", help="Run in infinite loop")
    parser.add_argument("--register-only", action="store_true", help="Only register, skip vote")
    args = parser.parse_args()

    if args.loop:
        print(f"{'='*60}")
        print("RUNNING IN INFINITE LOOP (Ctrl+C to stop)")
        print(f"{'='*60}")
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'#'*60}")
            print(f"# ITERATION {iteration}")
            print(f"{'#'*60}")
            try:
                if not args.vote_only:
                    run_register(args.count, args.api_key, args.domain, args.password)
                if not args.register_only:
                    run_vote(args.target, args.limit)
            except KeyboardInterrupt:
                print("\nStopped by user.")
                break
    else:
        if not args.vote_only:
            run_register(args.count, args.api_key, args.domain, args.password)
        if not args.register_only:
            if args.vote_only:
                run_vote_only(args.target, args.limit)
            else:
                run_vote(args.target, args.limit)

    print(f"\n{'='*60}")
    print("WORKFLOW COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
