"""
API Vote cho Elle Beauty Awards 2026.
Dựa trên captured request từ DevTools.
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
from colorama import Fore, Style, init

init()

DB_FILE = Path("vote/login_cookies.sqlite3")
VOTE_URL = "https://events.elle.vn/elle-beauty-awards-2026/nhan-vat"

# Action ID cho vote - có thể thay đổi theo thời gian
NEXT_ACTION_ID = "288bd3262db6e09085c5f3f89856bb17fb9abf1a"


def load_all_unvoted_accounts():
    """Load all success accounts that haven't voted yet."""
    if not DB_FILE.exists():
        return []
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT email, cookies_json FROM login_cookies WHERE status='success' AND voted_at IS NULL"
        ).fetchall()
    return [(row[0], json.loads(row[1])) for row in rows]


def to_dict(cookies_list):
    return {c["name"]: c["value"] for c in cookies_list if c.get("name") and c.get("value")}


def mark_as_voted(email: str, target_id: str):
    """Mark account as voted in database."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            UPDATE login_cookies 
            SET voted_at = ?, voted_for = ?
            WHERE email = ?
            """,
            (now, target_id, email)
        )
        print(f"{Fore.GREEN}✓ Marked {email} as voted for {target_id}{Style.RESET_ALL}")


async def submit_vote(
    client: httpx.AsyncClient,
    target_type: str = "celebrity",
    target_id: str = "69e1fe40de1b6fbcd4b30990",
    return_url: str = "/elle-beauty-awards-2026/nhan-vat"
) -> dict:
    """
    Submit vote qua Next.js Server Action.

    Args:
        target_type: Loại đối tượng (celebrity, affiliate, ...)
        target_id: ID của candidate (từ vote_api_from_js.json)
        return_url: URL redirect sau khi vote
    """
    body = json.dumps([target_type, target_id, return_url])

    headers = {
        "accept": "text/x-component",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
        "cache-control": "no-cache",
        "content-type": "text/plain;charset=UTF-8",
        "next-action": NEXT_ACTION_ID,
        "next-router-state-tree": '%5B%22%22%2C%7B%22children%22%3A%5B%5B%22slug%22%2C%22elle-beauty-awards-2026%22%2C%22d%22%5D%2C%7B%22children%22%3A%5B%22nhan-vat%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2C%22%2Felle-beauty-awards-2026%2Fnhan-vat%22%2C%22refresh%22%5D%7D%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D',
        "origin": "https://events.elle.vn",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://events.elle.vn/elle-beauty-awards-2026/nhan-vat",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    }

    print(f"\n{Fore.MAGENTA}=== Submitting Vote ==={Style.RESET_ALL}")
    print(f"{Fore.CYAN}Target: {target_type} - {target_id}{Style.RESET_ALL}")

    try:
        resp = await client.post(
            VOTE_URL,
            content=body,
            headers=headers,
            timeout=30
        )

        if resp.status_code == 200:
            return {"success": True, "status": resp.status_code}
        else:
            return {"success": False, "status": resp.status_code}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def vote_one_account(email: str, cookies_list: list, target_id: str, target_type: str = "celebrity") -> dict:
    """Vote for a single account."""
    cookies = to_dict(cookies_list)

    try:
        async with httpx.AsyncClient(
            cookies=cookies,
            follow_redirects=True,
            timeout=30
        ) as client:
            result = await submit_vote(
                client,
                target_type=target_type,
                target_id=target_id,
                return_url="/elle-beauty-awards-2026/nhan-vat"
            )
            
            if result.get("success") and result.get("status") == 200:
                mark_as_voted(email, target_id)
                print(f"{Fore.GREEN}[{email}] ✓{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}[{email}] ✗ {result.get('status', 'err')}{Style.RESET_ALL}")
            
            return result
    except Exception as e:
        print(f"{Fore.RED}[{email}] ✗ {e}{Style.RESET_ALL}")
        return {"success": False, "error": str(e)}


def check_vote_counts():
    """Print summary of voted vs unvoted accounts."""
    with sqlite3.connect(DB_FILE) as conn:
        total = conn.execute("SELECT COUNT(*) FROM login_cookies WHERE status='success'").fetchone()[0]
        voted = conn.execute("SELECT COUNT(*) FROM login_cookies WHERE status='success' AND voted_at IS NOT NULL").fetchone()[0]
        unvoted = conn.execute("SELECT COUNT(*) FROM login_cookies WHERE status='success' AND voted_at IS NULL").fetchone()[0]
    print(f"Total success: {total} | Voted: {voted} | Unvoted: {unvoted}")
    return {"total": total, "voted": voted, "unvoted": unvoted}


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit number of accounts to test (0 = all)")
    parser.add_argument("--target", default="69e1fa8da51bd7bcd50c5b2e", help="Target candidate ID")
    parser.add_argument("--check", action="store_true", help="Check vote counts only")
    parser.add_argument("--email", help="Vote specific email only")
    args = parser.parse_args()

    if args.check:
        check_vote_counts()
        return

    target_id = args.target

    if args.email:
        # Vote specific email
        import sqlite3
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute(
                "SELECT email, cookies_json FROM login_cookies WHERE email=? AND status='success'",
                (args.email,)
            ).fetchone()
        if not row:
            print(f"{Fore.RED}Account {args.email} not found or not logged in!{Style.RESET_ALL}")
            return
        accounts = [(row[0], json.loads(row[1]))]
    else:
        accounts = load_all_unvoted_accounts()
        if not accounts:
            print(f"{Fore.YELLOW}No unvoted accounts found!{Style.RESET_ALL}")
            return

    if args.limit > 0:
        accounts = accounts[:args.limit]

    print(f"{Fore.CYAN}Found {len(accounts)} accounts to vote{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Target: {target_id}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")

    results = []
    for email, cookies_list in accounts:
        result = await vote_one_account(email, cookies_list, target_id)
        results.append({"email": email, "result": result})
        await asyncio.sleep(1)  # Rate limit between votes

    # Summary
    success_count = sum(1 for r in results if r["result"].get("success") and r["result"].get("status") == 200)
    print(f"\n{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Total: {len(results)} | Success: {success_count} | Failed: {len(results) - success_count}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}")

    # Save results
    with open("vote_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": len(results),
            "success": success_count,
            "votes": results
        }, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())
