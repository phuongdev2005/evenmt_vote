"""
Run a one-profile, one-tab GemLogin login test.

The script uses the first profile from GemLogin and logs in accounts from
account.txt one by one. After each successful attempt it saves cookies to
SQLite, then clears browser cookies and site storage so the next account starts
from a clean state.
"""

import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import httpx
from colorama import Fore, Style, init
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

try:
    from gemlogin import close_profile, get_profiles, start_profile
except ImportError:
    from vote.gemlogin import close_profile, get_profiles, start_profile


init()

LOGIN_URL = "https://events.elle.vn/login?returnTo=%2Felle-beauty-awards-2026%2Fnhan-vat"
SITE_ORIGIN = "https://events.elle.vn"
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
ACCOUNT_FILE = SCRIPT_DIR / "account.txt"
DB_FILE = SCRIPT_DIR / "login_cookies.sqlite3"
PROFILE_INDEX = 0
MAX_ACCOUNTS_PER_RUN = 0  # 0 = no limit, process all accounts in one run
NUM_PROFILES = 6  # Number of parallel profiles
MANUAL_CAPTCHA_TIMEOUT = 180

# Window layout settings
SCREEN_WIDTH = 1536
SCREEN_HEIGHT = 824
WINDOW_COLS = 3
WINDOW_WIDTH = SCREEN_WIDTH // WINDOW_COLS
WINDOW_HEIGHT = SCREEN_HEIGHT // 2

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def is_logged_in_url(url: str) -> bool:
    return ("nhan-vat" in url or "elle-beauty-awards" in url) and "login" not in url


def remove_account_from_file(email: str, file_path: Path = ACCOUNT_FILE) -> None:
    """Remove processed account from account.txt to avoid re-processing."""
    if not file_path.exists():
        return
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.strip() != email:
                f.write(line)


def init_db(db_path: Path = DB_FILE) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_cookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL,
                current_url TEXT NOT NULL,
                cookies_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(profile_id, email)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_login_cookies_email
            ON login_cookies(email)
            """
        )


def save_login_cookies(
    profile_id: str,
    email: str,
    status: str,
    current_url: str,
    cookies: list[dict],
    db_path: Path = DB_FILE,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    cookies_json = json.dumps(cookies, ensure_ascii=False)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO login_cookies (
                profile_id,
                email,
                status,
                current_url,
                cookies_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_id, email) DO UPDATE SET
                status = excluded.status,
                current_url = excluded.current_url,
                cookies_json = excluded.cookies_json,
                updated_at = excluded.updated_at
            """,
            (profile_id, email, status, current_url, cookies_json, now, now),
        )


def get_saved_success_emails(db_path: Path = DB_FILE) -> set[str]:
    if not db_path.exists():
        return set()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT email
            FROM login_cookies
            WHERE status = 'success'
            """
        ).fetchall()

    return {row[0] for row in rows}


def load_accounts(filepath: Path) -> list[str]:
    try:
        return [line.strip() for line in filepath.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        print(f"{Fore.RED}Cannot read {filepath}: {exc}{Style.RESET_ALL}")
        return []


async def get_one_tab(context) -> Page:
    pages = context.pages
    if pages:
        page = pages[0]
    else:
        page = await context.new_page()

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
        await cdp_session.send(
            "Storage.clearDataForOrigin",
            {
                "origin": SITE_ORIGIN,
                "storageTypes": "all",
            },
        )
        await cdp_session.detach()
    except Exception:
        pass

    await context.clear_cookies()


async def wait_for_turnstile_token(page: Page, timeout: int = MANUAL_CAPTCHA_TIMEOUT) -> bool:
    """Wait for Turnstile token, auto-click CF frame if needed."""
    auto_click_interval = 0  # Click every check if no token
    last_click = -1

    for i in range(timeout * 5):  # 5x more checks for faster response
        # Check token
        token = await page.evaluate(
            """() => {
                const el = document.querySelector('[name="cf-turnstile-response"]');
                return el ? el.value : '';
            }"""
        )
        if token and len(token) > 10:
            return True

        # Auto-click CF frame every interval
        if i - last_click >= auto_click_interval:
            await try_click_turnstile_frame(page)
            last_click = i

        await asyncio.sleep(0.2)  # Check every 0.2s

    return False


async def try_click_turnstile_frame(page: Page) -> bool:
    """Try to click on Turnstile frame - optimized for speed."""
    try:
        for frame in page.frames:
            if "challenges.cloudflare" in frame.url or "turnstile" in frame.url:
                fe = await frame.frame_element()
                box = await fe.bounding_box()
                if box and box.get("y", 0) > 0:
                    cx = box["x"] + box["width"] / 2
                    cy = box["y"] + box["height"] / 2
                    await page.mouse.click(cx, cy)
                    return True
    except Exception:
        pass
    return False


async def login_account(page: Page, email: str) -> dict:
    start_time = time.time()
    result = {"email": email, "status": "unknown", "url": "", "duration": 0, "captcha_duration": 0}

    try:
        print(f"{Fore.CYAN}Opening login page...{Style.RESET_ALL}")
        # Chỉ đợi DOM ready, không đợi networkidle để nhanh hơn
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    except PlaywrightTimeoutError:
        print(f"{Fore.YELLOW}Page load timed out, continuing with current DOM.{Style.RESET_ALL}")

    if is_logged_in_url(page.url):
        result.update(status="success", url=page.url)
        return result

    # Scroll xuống vùng mật khẩu trước khi điền form (để trigger CAPTCHA lazy loading)
    print(f"{Fore.CYAN}Scrolling to password area to load CAPTCHA...{Style.RESET_ALL}")
    try:
        # Scroll đến vùng mật khẩu (khoảng giữa màn hình)
        await page.evaluate("() => window.scrollTo(0, window.innerHeight * 0.5)")
        await asyncio.sleep(0.5)
        # Scroll thêm xuống để CAPTCHA hiện rõ hoàn toàn (dưới ô mật khẩu)
        await page.evaluate("() => window.scrollBy(0, 1100)")
        await asyncio.sleep(1)
        print(f"{Fore.GREEN}Scrolled to password/CAPTCHA area{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.YELLOW}Scroll warning: {e}{Style.RESET_ALL}")

    try:
        await page.locator('input[name="identifier"]').wait_for(timeout=15000)
        await page.fill('input[name="identifier"]', email)
        await page.fill('input[name="password"]', email)
    except Exception as exc:
        if is_logged_in_url(page.url):
            result.update(status="success", url=page.url)
            return result
        result.update(status="form_not_found", error=str(exc), url=page.url)
        return result

    # Đợi Turnstile widget xuất hiện (tối đa 10s)
    print(f"{Fore.CYAN}Waiting for Turnstile widget...{Style.RESET_ALL}")
    try:
        await page.wait_for_selector('iframe[src*="challenges.cloudflare"], [data-sitekey], [name="cf-turnstile-response"]', timeout=10000)
        print(f"{Fore.GREEN}Turnstile widget loaded{Style.RESET_ALL}")
    except:
        print(f"{Fore.YELLOW}Widget not detected, continuing anyway...{Style.RESET_ALL}")

    print(f"{Fore.YELLOW}Auto-solving Turnstile CAPTCHA...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Auto-click every 2s. Timeout: {MANUAL_CAPTCHA_TIMEOUT}s{Style.RESET_ALL}")
    captcha_start = time.time()
    turnstile_ok = await wait_for_turnstile_token(page)
    result["captcha_duration"] = round(time.time() - captcha_start, 2)
    if not turnstile_ok:
        result.update(status="captcha_timeout", url=page.url)
        return result
    print(f"{Fore.GREEN}Turnstile token detected.{Style.RESET_ALL}")

    try:
        await page.click('button[type="submit"]', timeout=10000)
    except Exception as exc:
        result.update(status="submit_failed", error=str(exc), url=page.url)
        return result

    await asyncio.sleep(2)  # Reduced wait time
    result["url"] = page.url
    result["duration"] = round(time.time() - start_time, 2)

    if is_logged_in_url(page.url):
        result["status"] = "success"
    elif "login" in page.url:
        result["status"] = "login_failed_or_captcha"
    else:
        result["status"] = "unknown"

    print(f"{Fore.CYAN}[Time] Total: {result['duration']}s, CAPTCHA: {result['captcha_duration']}s{Style.RESET_ALL}")
    return result


def get_window_position(profile_num: int, total_profiles: int) -> tuple[int, int]:
    """Grid layout 6x2 for 12 profiles."""
    SCREEN_W = 1536
    SCREEN_H = 824
    COLS = 6
    ROWS = 2
    WIN_W = SCREEN_W // COLS
    WIN_H = SCREEN_H // ROWS

    col = (profile_num - 1) % COLS
    row = (profile_num - 1) // COLS
    x = col * WIN_W
    y = row * WIN_H
    return (x, y)


def get_window_geometry(profile_num: int, total_profiles: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Grid layout 6x2 for windows."""
    index = profile_num - 1
    col = index % WINDOW_COLS
    row = index // WINDOW_COLS

    x = col * WINDOW_WIDTH
    y = row * WINDOW_HEIGHT

    return (x, y), (WINDOW_WIDTH, WINDOW_HEIGHT)


def set_window_bounds_hwnd(hwnd: int, x: int, y: int, width: int, height: int) -> None:
    """Set window position and size via Windows API."""
    import ctypes
    SW_RESTORE = 9
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    ctypes.windll.user32.MoveWindow(hwnd, x, y, width, height, True)


# Global tracking for resized windows
_resized_lock = asyncio.Lock()
_resized_hwnds: set[int] = set()


def find_all_gemlogin_windows() -> list[tuple[int, str, int, int]]:
    """Find all GemLogin Chrome window handles and their sizes."""
    import ctypes
    import ctypes.wintypes

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


async def set_window_bounds_async(x: int, y: int, width: int, height: int) -> None:
    """Set window position and size via Windows API. Resizes the first unresized GemLogin window."""
    await asyncio.sleep(2)  # Wait for window to open

    async with _resized_lock:
        windows = find_all_gemlogin_windows()
        # Find first window not yet resized and not too small already
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
            print(f"{Fore.YELLOW}Warning: No unresized GemLogin window found for ({x},{y}){Style.RESET_ALL}")


async def run_profile_tasks(client, profile_id: str, accounts: list[str], profile_num: int, total_profiles: int) -> dict:
    """Run login tasks for one profile."""
    profile_start = time.time()
    stats = {"success": 0, "failed": 0, "total": len(accounts)}
    print(f"{Fore.CYAN}Starting profile {profile_num}: {profile_id}{Style.RESET_ALL}")

    window_pos, window_size = get_window_geometry(profile_num, total_profiles)
    print(f"{Fore.CYAN}[Profile {profile_num}] Window position: {window_pos}, size: {window_size}{Style.RESET_ALL}")

    ws_url = await start_profile(client, profile_id, window_position=window_pos, window_size=window_size)
    if not ws_url:
        print(f"{Fore.RED}[Profile {profile_num}] Could not start profile{Style.RESET_ALL}")
        return stats

    completed_accounts = 0
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await get_one_tab(context)

            # Set window bounds via Windows API
            await set_window_bounds_async(window_pos[0], window_pos[1], window_size[0], window_size[1])

            for index, email in enumerate(accounts, start=1):
                print(f"\n{Fore.MAGENTA}[Profile {profile_num}] {'=' * 40}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}[Profile {profile_num}] Account {index}/{len(accounts)}: {email}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}[Profile {profile_num}] Resetting browser state...{Style.RESET_ALL}")
                await reset_browser_state(context, page)

                print(f"{Fore.CYAN}[Profile {profile_num}] Running login...{Style.RESET_ALL}")
                result = await login_account(page, email)
                cookies = await context.cookies()
                current_url = result.get("url") or page.url
                save_login_cookies(profile_id, email, result["status"], current_url, cookies)

                color = Fore.GREEN if result["status"] == "success" else Fore.RED
                print(f"{color}[Profile {profile_num}] Result: {result['status']}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}[Profile {profile_num}] Saved {len(cookies)} cookies{Style.RESET_ALL}")

                # Track stats
                if result["status"] == "success":
                    stats["success"] += 1
                    remove_account_from_file(email)
                else:
                    stats["failed"] += 1

                completed_accounts += 1
                await reset_browser_state(context, page)
    except Exception as exc:
        remaining_accounts = len(accounts) - completed_accounts
        stats["failed"] += remaining_accounts
        print(f"{Fore.RED}[Profile {profile_num}] Error: {type(exc).__name__}: {exc}{Style.RESET_ALL}")
    finally:
        await close_profile(client, profile_id)

    profile_duration = round(time.time() - profile_start, 2)
    print(f"{Fore.GREEN}[Profile {profile_num}] Done in {profile_duration}s ({stats['success']}/{stats['total']} success){Style.RESET_ALL}")
    return stats


async def run_one_tab_login_test() -> None:
    total_start = time.time()
    _resized_hwnds.clear()
    init_db()

    accounts = load_accounts(ACCOUNT_FILE)
    if not accounts:
        print(f"{Fore.RED}No account found in {ACCOUNT_FILE}.{Style.RESET_ALL}")
        return

    saved_emails = get_saved_success_emails()
    pending_accounts = [email for email in accounts if email not in saved_emails]
    if MAX_ACCOUNTS_PER_RUN:
        pending_accounts = pending_accounts[:MAX_ACCOUNTS_PER_RUN]

    print(f"{Fore.CYAN}Found {len(accounts)} accounts in {ACCOUNT_FILE}.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Already saved success: {len(saved_emails)} accounts.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}This run will process: {len(pending_accounts)} accounts.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Using {NUM_PROFILES} parallel profiles{Style.RESET_ALL}")

    if not pending_accounts:
        print(f"{Fore.GREEN}No pending accounts to login.{Style.RESET_ALL}")
        return

    async with httpx.AsyncClient() as client:
        profiles = await get_profiles(client)

        # Tạo thêm profile nếu chưa đủ
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

        if len(profiles) < NUM_PROFILES:
            print(f"{Fore.YELLOW}Only have {len(profiles)} profiles, using available.{Style.RESET_ALL}")

        # Chia accounts cho các profiles
        chunk_size = (len(pending_accounts) + NUM_PROFILES - 1) // NUM_PROFILES
        account_chunks = [
            pending_accounts[i:i + chunk_size]
            for i in range(0, len(pending_accounts), chunk_size)
        ]

        # Chạy song song
        tasks = []
        for i in range(NUM_PROFILES):
            if i < len(account_chunks) and account_chunks[i]:
                profile = profiles[i]
                profile_id = str(profile.get("id") or profile.get("profile_id") or profile)
                task = run_profile_tasks(client, profile_id, account_chunks[i], i + 1, NUM_PROFILES)
                tasks.append(task)

        results = await asyncio.gather(*tasks)

    # Calculate totals
    total_success = sum(r["success"] for r in results if isinstance(r, dict))
    total_failed = sum(r["failed"] for r in results if isinstance(r, dict))
    total_accounts = sum(r["total"] for r in results if isinstance(r, dict))
    total_duration = round(time.time() - total_start, 2)

    # Summary report
    print(f"\n{'=' * 50}")
    print(f"{Fore.GREEN}SUMMARY REPORT{Style.RESET_ALL}")
    print(f"{'=' * 50}")
    print(f"Total accounts processed: {total_accounts}")
    print(f"{Fore.GREEN}✓ Success: {total_success}{Style.RESET_ALL}")
    print(f"{Fore.RED}✗ Failed:  {total_failed}{Style.RESET_ALL}")
    print(f"Success rate: {total_success/total_accounts*100:.1f}%" if total_accounts > 0 else "N/A")
    print(f"Total time: {total_duration}s")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    try:
        # Use new_event_loop to avoid "Event loop is closed" errors
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_one_tab_login_test())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopped.{Style.RESET_ALL}")
