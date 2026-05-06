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


def load_cookies(specific_email: str = None):
    if not DB_FILE.exists():
        return None, None
    with sqlite3.connect(DB_FILE) as conn:
        if specific_email:
            # Get specific account
            row = conn.execute(
                "SELECT email, cookies_json FROM login_cookies WHERE email=? AND status='success'",
                (specific_email,)
            ).fetchone()
        else:
            # Get a random successful account that hasn't voted
            rows = conn.execute(
                "SELECT email, cookies_json FROM login_cookies WHERE status='success' AND voted_at IS NULL ORDER BY RANDOM() LIMIT 1"
            ).fetchall()
            row = rows[0] if rows else None
    if not row:
        return None, None
    return row[0], json.loads(row[1])


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

        print(f"{Fore.YELLOW}Status: {resp.status_code}{Style.RESET_ALL}")
        print(f"Headers: {dict(resp.headers)}")

        if resp.status_code == 200:
            print(f"{Fore.GREEN}✓ Vote API call succeeded!{Style.RESET_ALL}")
            try:
                content = resp.text
                print(f"Response: {content[:500]}")
                return {"success": True, "status": resp.status_code, "response": content}
            except Exception as e:
                print(f"{Fore.RED}Error reading response: {e}{Style.RESET_ALL}")
                return {"success": True, "status": resp.status_code, "error": str(e)}
        else:
            print(f"{Fore.RED}✗ Vote failed with status {resp.status_code}{Style.RESET_ALL}")
            return {"success": False, "status": resp.status_code, "response": resp.text[:300]}

    except Exception as e:
        print(f"{Fore.RED}Exception: {e}{Style.RESET_ALL}")
        return {"success": False, "error": str(e)}


async def main():
    # Use random account
    email, cookies_list = load_cookies()
    if not cookies_list:
        print(f"{Fore.RED}No cookies found!{Style.RESET_ALL}")
        return

    cookies = to_dict(cookies_list)
    print(f"{Fore.CYAN}Account: {email}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}vote_sid: {cookies.get('vote_sid', 'NOT FOUND')}{Style.RESET_ALL}")

    # Test with specific celebrity ID
    target_id = "69e1fa8da51bd7bcd50c5b2e"

    results = []

    async with httpx.AsyncClient(
        cookies=cookies,
        follow_redirects=True,
        timeout=30
    ) as client:
        result = await submit_vote(
            client,
            target_type="celebrity",
            target_id=target_id,
            return_url="/elle-beauty-awards-2026/nhan-vat"
        )
        results.append({
            "target_id": target_id,
            "result": result
        })
        
        # Mark as voted if successful
        if result.get("success") and result.get("status") == 200:
            mark_as_voted(email, target_id)
        
        await asyncio.sleep(2)

    # Save results
    with open("vote_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "account": email,
            "votes": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n{Fore.GREEN}Results saved to vote_results.json{Style.RESET_ALL}")


if __name__ == "__main__":
    asyncio.run(main())
