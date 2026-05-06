"""
Vote API cho tất cả accounts.
"""

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
from colorama import Fore, Style, init

init()

DB_FILE = Path("vote/login_cookies.sqlite3")
VOTE_URL = "https://events.elle.vn/elle-beauty-awards-2026/nhan-vat"
NEXT_ACTION_ID = "288bd3262db6e09085c5f3f89856bb17fb9abf1a"


def load_all_accounts():
    if not DB_FILE.exists():
        return []
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT email, cookies_json FROM login_cookies WHERE status='success' ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def to_dict(cookies_list):
    return {c["name"]: c["value"] for c in cookies_list if c.get("name") and c.get("value")}


async def submit_vote(client: httpx.AsyncClient, target_type: str, target_id: str) -> dict:
    """Submit vote."""
    body = json.dumps([target_type, target_id, "/elle-beauty-awards-2026/nhan-vat"])

    headers = {
        "accept": "text/x-component",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "vi-VN,vi;q=0.9",
        "cache-control": "no-cache",
        "content-type": "text/plain;charset=UTF-8",
        "next-action": NEXT_ACTION_ID,
        "origin": "https://events.elle.vn",
        "pragma": "no-cache",
        "referer": "https://events.elle.vn/elle-beauty-awards-2026/nhan-vat",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        resp = await client.post(VOTE_URL, content=body, headers=headers, timeout=30)
        return {
            "success": resp.status_code == 200,
            "status": resp.status_code,
            "response_preview": resp.text[:200] if resp.status_code == 200 else resp.text[:300]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def vote_with_account(client: httpx.AsyncClient, email: str, cookies: dict, target_id: str) -> dict:
    """Vote với một account."""
    print(f"\n{Fore.CYAN}[{email}]{Style.RESET_ALL}")
    print(f"  Cookie vote_sid: {cookies.get('vote_sid', 'N/A')[:20]}...")

    # Update client cookies
    client.cookies.update(cookies)

    result = await submit_vote(client, "celebrity", target_id)

    if result["success"]:
        print(f"  {Fore.GREEN}✓ Vote submitted{Style.RESET_ALL}")
    else:
        print(f"  {Fore.RED}✗ Failed: {result.get('status', result.get('error'))}{Style.RESET_ALL}")

    return {"email": email, **result}


async def main():
    accounts = load_all_accounts()
    if not accounts:
        print(f"{Fore.RED}No accounts found!{Style.RESET_ALL}")
        return

    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Vote API - {len(accounts)} accounts ready{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")

    # Target: Kim Tuyến (có thể đổi sang ID khác)
    target_id = "69e1fe40de1b6fbcd4b30990"
    print(f"\nTarget ID: {target_id}")

    results = []

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        for account in accounts:
            email = account["email"]
            cookies = to_dict(json.loads(account["cookies_json"]))

            result = await vote_with_account(client, email, cookies, target_id)
            results.append(result)

            await asyncio.sleep(1)  # Rate limiting

    # Summary
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Summary:{Style.RESET_ALL}")
    success = sum(1 for r in results if r.get("success"))
    failed = len(results) - success
    print(f"  {Fore.GREEN}Success: {success}{Style.RESET_ALL}")
    print(f"  {Fore.RED}Failed: {failed}{Style.RESET_ALL}")

    # Save
    with open("vote_all_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "target_id": target_id,
            "results": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n{Fore.GREEN}Saved to vote_all_results.json{Style.RESET_ALL}")


if __name__ == "__main__":
    asyncio.run(main())
