"""
Login -> get cookies -> save to SQLite DB -> vote for Elle Beauty Awards.
Dung GemLogin giong open_profiles.py, 5 profile song song.
"""

import argparse
import asyncio
import ctypes
import ctypes.wintypes
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from colorama import Fore, Style, init
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
# Hỗ trợ biến môi trường cho Docker (database riêng trong container)
DB_FILE = Path(os.getenv("DB_FILE_PATH", str(SCRIPT_DIR / "vote_cookies.sqlite3")))
ACCOUNT_FILE = SCRIPT_DIR / "smsaccount.txt"

LOGIN_URL = "https://events.elle.vn/login?returnTo=%2Felle-beauty-awards-2026%2Fnhan-vat"
VOTE_URL = "https://events.elle.vn/elle-beauty-awards-2026/nhan-vat"
NEXT_ACTION_ID = "288bd3262db6e09085c5f3f89856bb17fb9abf1a"
MANUAL_CAPTCHA_TIMEOUT = 180
NUM_PROFILES = 5

# Window layout for 5 profiles (3 columns x 2 rows)
SCREEN_WIDTH = 1536
SCREEN_HEIGHT = 824
WINDOW_COLS = 3
WINDOW_WIDTH = SCREEN_WIDTH // WINDOW_COLS
WINDOW_HEIGHT = SCREEN_HEIGHT // 2

init()


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


configure_stdio()

PROJECT_DIR = SCRIPT_DIR.parent
VOTE_DIR = PROJECT_DIR / "vote"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(VOTE_DIR) not in sys.path:
    sys.path.insert(0, str(VOTE_DIR))

try:
    from gemlogin import close_profile, create_profile, get_profiles, start_profile
except ImportError:
    try:
        from vote.gemlogin import close_profile, create_profile, get_profiles, start_profile
    except ImportError:
        from sms_tool.gemlogin import close_profile, create_profile, get_profiles, start_profile


# =================== DB ===================

def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_cookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                current_url TEXT NOT NULL,
                cookies_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                target_id TEXT NOT NULL,
                voted_at TEXT NOT NULL,
                UNIQUE(email, target_id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_votes_email ON votes(email)")


def save_login_cookies(profile_id: str, email: str, status: str, current_url: str, cookies: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    cookies_json = json.dumps(cookies, ensure_ascii=False)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO login_cookies (profile_id, email, status, current_url, cookies_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                profile_id = excluded.profile_id,
                status = excluded.status,
                current_url = excluded.current_url,
                cookies_json = excluded.cookies_json,
                updated_at = excluded.updated_at
            """,
            (profile_id, email, status, current_url, cookies_json, now, now),
        )


def mark_as_voted(email: str, target_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO votes (email, target_id, voted_at) VALUES (?, ?, ?)",
            (email, target_id, now),
        )
    print(f"{Fore.GREEN}  Marked {email} as voted for {target_id}{Style.RESET_ALL}")


# =================== Accounts ===================

def load_accounts() -> list[tuple[str, str]]:
    if not ACCOUNT_FILE.exists():
        return []
    accounts = []
    for line in ACCOUNT_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        parts = line.split("|")
        email = parts[0].strip()
        password = parts[1].strip() if len(parts) > 1 else email
        accounts.append((email, password))
    return accounts


def remove_account_from_file(email: str) -> None:
    if not ACCOUNT_FILE.exists():
        return
    with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().split("|")[0].strip() != email:
                f.write(line)


# =================== Login helpers ===================

def is_logged_in_url(url: str) -> bool:
    return ("nhan-vat" in url or "elle-beauty-awards" in url) and "login" not in url


async def get_one_tab(context) -> Page:
    pages = context.pages
    page = pages[0] if pages else await context.new_page()
    for extra_page in list(context.pages)[1:]:
        try:
            await extra_page.close()
        except Exception:
            pass
    return page


async def reset_browser_state(context, page: Page) -> None:
    await context.clear_cookies()
    try:
        cdp_session = await context.new_cdp_session(page)
        await cdp_session.send("Storage.clearDataForOrigin", {"origin": "https://events.elle.vn", "storageTypes": "all"})
    except Exception:
        pass


async def try_click_turnstile_frame(page: Page) -> bool:
    try:
        for frame in page.frames:
            if "challenges.cloudflare" in frame.url or "turnstile" in frame.url:
                fe = await frame.frame_element()
                box = await fe.bounding_box()
                if box and box.get("y", 0) > 0:
                    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    return True
    except Exception:
        pass
    return False


async def wait_for_turnstile_token(page: Page, timeout: int = MANUAL_CAPTCHA_TIMEOUT) -> bool:
    last_click = -1
    for i in range(timeout * 5):
        token = await page.evaluate(
            """() => {
                const el = document.querySelector('[name="cf-turnstile-response"]');
                return el ? el.value : '';
            }"""
        )
        if token and len(token) > 10:
            return True
        if i - last_click >= 0:
            await try_click_turnstile_frame(page)
            last_click = i
        await asyncio.sleep(0.2)
    return False


async def login_account(page: Page, email: str, password: str) -> dict:
    result = {"email": email, "status": "unknown", "url": ""}
    try:
        print(f"{Fore.CYAN}Opening login page...{Style.RESET_ALL}")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    except PlaywrightTimeoutError:
        print(f"{Fore.YELLOW}Page load timed out, continuing.{Style.RESET_ALL}")

    if is_logged_in_url(page.url):
        result.update(status="success", url=page.url)
        return result

    try:
        await page.evaluate("() => window.scrollTo(0, window.innerHeight * 0.5)")
        await asyncio.sleep(0.5)
        await page.evaluate("() => window.scrollBy(0, 1100)")
        await asyncio.sleep(1)
    except Exception:
        pass

    try:
        await page.locator('input[name="identifier"]').wait_for(timeout=15000)
        await page.fill('input[name="identifier"]', email)
        await page.fill('input[name="password"]', password)
    except Exception as exc:
        if is_logged_in_url(page.url):
            result.update(status="success", url=page.url)
            return result
        result.update(status="form_not_found", error=str(exc))
        return result

    try:
        await page.wait_for_selector('iframe[src*="challenges.cloudflare"], [data-sitekey], [name="cf-turnstile-response"]', timeout=10000)
    except Exception:
        pass

    print(f"{Fore.YELLOW}Auto-solving Turnstile CAPTCHA...{Style.RESET_ALL}")
    if not await wait_for_turnstile_token(page):
        result.update(status="captcha_timeout", url=page.url)
        return result
    print(f"{Fore.GREEN}Turnstile token detected.{Style.RESET_ALL}")

    try:
        await page.click('button[type="submit"]', timeout=10000)
    except Exception as exc:
        result.update(status="submit_failed", error=str(exc), url=page.url)
        return result

    await asyncio.sleep(2)
    result["url"] = page.url
    result["status"] = "success" if is_logged_in_url(page.url) else "login_failed"
    return result


# =================== Vote ===================

def to_dict(cookies_list: list) -> dict:
    return {c["name"]: c["value"] for c in cookies_list if c.get("name") and c.get("value")}


async def submit_vote(client: httpx.AsyncClient, target_type: str, target_id: str) -> dict:
    body = json.dumps([target_type, target_id, "/elle-beauty-awards-2026/nhan-vat"])
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
    try:
        resp = await client.post(VOTE_URL, content=body, headers=headers, timeout=30)
        return {"success": resp.status_code == 200, "status": resp.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def vote_one_account(email: str, cookies_list: list, target_id: str, target_type: str = "celebrity") -> dict:
    cookies = to_dict(cookies_list)
    try:
        async with httpx.AsyncClient(cookies=cookies, follow_redirects=True, timeout=30) as client:
            result = await submit_vote(client, target_type, target_id)
            if result.get("success") and result.get("status") == 200:
                mark_as_voted(email, target_id)
                print(f"{Fore.GREEN}[{email}] Vote OK{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}[{email}] Vote FAIL {result.get('status', 'err')}{Style.RESET_ALL}")
            return result
    except Exception as e:
        print(f"{Fore.RED}[{email}] Vote ERROR {e}{Style.RESET_ALL}")
        return {"success": False, "error": str(e)}


# =================== Window management ===================

def get_window_geometry(profile_num: int, total_profiles: int) -> tuple[tuple[int, int], tuple[int, int]]:
    index = profile_num - 1
    col = index % WINDOW_COLS
    row = index // WINDOW_COLS
    x = col * WINDOW_WIDTH
    y = row * WINDOW_HEIGHT
    return (x, y), (WINDOW_WIDTH, WINDOW_HEIGHT)


def set_window_bounds_hwnd(hwnd: int, x: int, y: int, width: int, height: int) -> None:
    SW_RESTORE = 9
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    ctypes.windll.user32.MoveWindow(hwnd, x, y, width, height, True)


def find_all_gemlogin_windows() -> list[tuple[int, str, int, int]]:
    windows: list[tuple[int, str, int, int]] = []

    def enum_cb(hwnd, _):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        title_lower = title.lower()
        if "gemlogin" in title_lower and not title_lower.startswith("gemlogin -"):
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 200:
                windows.append((hwnd, title, w, h))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return windows


_resized_lock = asyncio.Lock()
_resized_hwnds: set[int] = set()


async def set_window_bounds_async(x: int, y: int, width: int, height: int) -> None:
    await asyncio.sleep(2)
    async with _resized_lock:
        windows = find_all_gemlogin_windows()
        target = None
        for hwnd, title, w, h in windows:
            if hwnd not in _resized_hwnds and w > 500:
                target = hwnd
                break
        if target:
            set_window_bounds_hwnd(target, x, y, width, height)
            _resized_hwnds.add(target)
            print(f"{Fore.GREEN}Window {target} resized to ({x},{y}) {width}x{height}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Warning: No unresized GemLogin window found{Style.RESET_ALL}")


# =================== Profile runner ===================

async def run_profile_tasks(client, profile_id: str, accounts: list[tuple[str, str]], profile_num: int, total_profiles: int, target_id: str) -> dict:
    stats = {"success": 0, "failed": 0, "total": len(accounts)}
    print(f"{Fore.CYAN}Starting profile {profile_num}: {profile_id}{Style.RESET_ALL}")

    window_pos, window_size = get_window_geometry(profile_num, total_profiles)
    ws_url = await start_profile(client, profile_id, window_position=window_pos, window_size=window_size)
    if not ws_url:
        print(f"{Fore.RED}[Profile {profile_num}] Could not start profile{Style.RESET_ALL}")
        return stats

    completed = 0
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await get_one_tab(context)
            await set_window_bounds_async(window_pos[0], window_pos[1], window_size[0], window_size[1])

            for index, (email, password) in enumerate(accounts, start=1):
                print(f"\n{Fore.MAGENTA}[Profile {profile_num}] {'=' * 40}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}[Profile {profile_num}] Account {index}/{len(accounts)}: {email}{Style.RESET_ALL}")
                await reset_browser_state(context, page)

                result = await login_account(page, email, password)
                cookies = await context.cookies()
                current_url = result.get("url") or page.url

                color = Fore.GREEN if result["status"] == "success" else Fore.RED
                print(f"{color}[Profile {profile_num}] Login: {result['status']}{Style.RESET_ALL}")

                if result["status"] == "success":
                    save_login_cookies(profile_id, email, "success", current_url, cookies)
                    remove_account_from_file(email)
                    print(f"{Fore.CYAN}[Profile {profile_num}] Saved {len(cookies)} cookies{Style.RESET_ALL}")

                    # Vote immediately after login
                    await vote_one_account(email, cookies, target_id)
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

                completed += 1
                await reset_browser_state(context, page)
    except Exception as exc:
        stats["failed"] += len(accounts) - completed
        print(f"{Fore.RED}[Profile {profile_num}] Error: {type(exc).__name__}: {exc}{Style.RESET_ALL}")
    finally:
        await close_profile(client, profile_id)

    print(f"{Fore.GREEN}[Profile {profile_num}] Done ({stats['success']}/{stats['total']} success){Style.RESET_ALL}")
    return stats


# =================== Main ===================

async def run_all(target_id: str, limit: int = 0):
    _resized_hwnds.clear()
    init_db()

    accounts = load_accounts()
    if not accounts:
        print(f"{Fore.RED}No accounts found in {ACCOUNT_FILE}{Style.RESET_ALL}")
        return

    if limit > 0:
        accounts = accounts[:limit]

    print(f"{Fore.CYAN}Found {len(accounts)} accounts. Using {NUM_PROFILES} parallel profiles.{Style.RESET_ALL}")

    async with httpx.AsyncClient() as client:
        profiles = await get_profiles(client)

        if len(profiles) < NUM_PROFILES:
            to_create = NUM_PROFILES - len(profiles)
            print(f"{Fore.YELLOW}Need {NUM_PROFILES} profiles, have {len(profiles)}. Creating {to_create} more...{Style.RESET_ALL}")
            for _ in range(to_create):
                new_id = await create_profile(client)
                if new_id:
                    profiles.append({"id": new_id})
                    print(f"{Fore.GREEN}Created profile: {new_id}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to create profile{Style.RESET_ALL}")
                    break

        chunk_size = (len(accounts) + NUM_PROFILES - 1) // NUM_PROFILES
        chunks = [accounts[i:i + chunk_size] for i in range(0, len(accounts), chunk_size)]

        tasks = []
        for i in range(NUM_PROFILES):
            if i < len(chunks) and chunks[i]:
                profile = profiles[i]
                profile_id = str(profile.get("id") or profile.get("profile_id") or profile)
                task = run_profile_tasks(client, profile_id, chunks[i], i + 1, NUM_PROFILES, target_id)
                tasks.append(task)

        results = await asyncio.gather(*tasks)

    total_success = sum(r["success"] for r in results if isinstance(r, dict))
    total_failed = sum(r["failed"] for r in results if isinstance(r, dict))
    print(f"\n{Fore.GREEN}SUMMARY: {total_success} success, {total_failed} failed{Style.RESET_ALL}")


def check_status():
    if not DB_FILE.exists():
        print("No database found.")
        return
    with sqlite3.connect(DB_FILE) as conn:
        total = conn.execute("SELECT COUNT(*) FROM login_cookies WHERE status='success'").fetchone()[0]
        voted = conn.execute("SELECT COUNT(DISTINCT email) FROM votes").fetchone()[0]
        print(f"Total success logins: {total} | Voted: {voted}")


async def vote_from_db(target_id: str, limit: int = 0):
    init_db()
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            """
            SELECT email, cookies_json FROM login_cookies
            WHERE status='success'
            AND email NOT IN (SELECT email FROM votes WHERE target_id=?)
            """,
            (target_id,)
        ).fetchall()
    if not rows:
        print("No unvoted accounts found in DB.")
        return
    accounts = [(row[0], json.loads(row[1])) for row in rows]
    if limit > 0:
        accounts = accounts[:limit]
    for email, cookies in accounts:
        await vote_one_account(email, cookies, target_id)
        await asyncio.sleep(0.5)


async def main():
    parser = argparse.ArgumentParser(description="Login and vote for Elle Beauty Awards (GemLogin, 5 profiles)")
    parser.add_argument("--target", default="69e1fe40de1b6fbcd4b30990", help="Target candidate ID")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of accounts (0 = all)")
    parser.add_argument("--check", action="store_true", help="Check status only")
    parser.add_argument("--vote-only", action="store_true", help="Vote from DB without re-login")
    args = parser.parse_args()

    if args.check:
        check_status()
        return

    if args.vote_only:
        await vote_from_db(args.target, args.limit)
    else:
        await run_all(args.target, args.limit)


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopped.{Style.RESET_ALL}")
