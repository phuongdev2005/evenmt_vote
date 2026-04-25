import argparse
import asyncio
import json
import random
import sys
import unicodedata
from datetime import date

import httpx
from bs4 import BeautifulSoup

from playwright.async_api import Page, async_playwright


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}

REGISTER_URL = config.get("elleNewRegisterUrl", "https://www.elle.vn/dang-ky/")
CONCURRENCY = int(config.get("concurrency", 5))
KIOT_KEYS: list[str] = config.get("kiotProxyKeys", [])
KIOT_REGION = config.get("kiotRegion", "random")
GEMLOGIN_API = config.get("gemloginApi", "http://localhost:1010")
USERNAME_SELECTOR = 'input#username[name="username"]'
ACCOUNTS_FILE = "accounts.txt"
RESULTS_FILE = "mail.txt"
USED_CCCD_FILE = "used_cccd.txt"
PROFILE_PROXIES: dict[str, dict] = {}

LAST_NAMES = [
    "An",
    "Bach",
    "Banh",
    "Bui",
    "Cao",
    "Chu",
    "Chung",
    "Dang",
    "Dao",
    "Dinh",
    "Do",
    "Doan",
    "Dong",
    "Du",
    "Duong",
    "Giang",
    "Ha",
    "Ho",
    "Hoang",
    "Huynh",
    "Kha",
    "Khuat",
    "Kieu",
    "La",
    "Lam",
    "Le",
    "Lieu",
    "Luu",
    "Ly",
    "Mai",
    "Mac",
    "Ngo",
    "Nguyen",
    "Nghiem",
    "Nong",
    "Ong",
    "Phan",
    "Pham",
    "Phung",
    "Quach",
    "Ta",
    "Tang",
    "Thai",
    "Than",
    "Thang",
    "Thao",
    "Thach",
    "To",
    "Ton",
    "Tran",
    "Trieu",
    "Trinh",
    "Truong",
    "Tu",
    "Ung",
    "Vi",
    "Vo",
    "Vu",
    "Vuong",
    "Xa",
    "Yen",
]

MIDDLE_NAMES = [
    "Anh",
    "Bao",
    "Bich",
    "Cam",
    "Chi",
    "Cong",
    "Dai",
    "Dang",
    "Dinh",
    "Duc",
    "Duy",
    "Gia",
    "Hai",
    "Hien",
    "Hoai",
    "Hoang",
    "Hong",
    "Huu",
    "Khai",
    "Khanh",
    "Kim",
    "Lan",
    "Mai",
    "Manh",
    "Minh",
    "My",
    "Nam",
    "Nhat",
    "Ngoc",
    "Nhu",
    "Phu",
    "Phuc",
    "Phuong",
    "Quang",
    "Quoc",
    "Tan",
    "Thanh",
    "Thao",
    "Thi",
    "Thu",
    "Thuy",
    "Tien",
    "Trong",
    "Truc",
    "Tuan",
    "Tung",
    "Van",
    "Viet",
    "Xuan",
]

GIVEN_NAMES = [
    "An",
    "Anh",
    "Anh Thu",
    "Bach",
    "Bao",
    "Bao Chau",
    "Bao Han",
    "Bao Ngoc",
    "Bao Tram",
    "Binh",
    "Cam",
    "Cam Ly",
    "Chau",
    "Chi",
    "Dat",
    "Diep",
    "Dung",
    "Duy",
    "Duyen",
    "Giang",
    "Hac",
    "Giang",
    "Ha",
    "Hai",
    "Han",
    "Hao",
    "Hanh",
    "Hien",
    "Hieu",
    "Hoa",
    "Hoai",
    "Hong",
    "Huy",
    "Huynh",
    "Hung",
    "Khang",
    "Khanh",
    "Khoa",
    "Khoi",
    "Kiet",
    "Lam",
    "Lan",
    "Linh",
    "Loan",
    "Loc",
    "Long",
    "Mai",
    "Manh",
    "Mi",
    "My",
    "My Anh",
    "My Duyen",
    "My Linh",
    "Nam",
    "Nga",
    "Ngan",
    "Nghi",
    "Nghia",
    "Nhat",
    "Nhu",
    "Nhi",
    "Phan",
    "Phat",
    "Phuc",
    "Phung",
    "Phuong",
    "Quan",
    "Quang",
    "Quoc",
    "Quynh",
    "Quynh Anh",
    "Quynh Chi",
    "Quynh Nhu",
    "Sang",
    "Son",
    "Tam",
    "Tan",
    "Thang",
    "Thao",
    "Thien",
    "Thinh",
    "Thoa",
    "Thu",
    "Thu Ha",
    "Thu Huong",
    "Thu Trang",
    "Thuy",
    "Thuy Anh",
    "Tien",
    "Trang",
    "Tri",
    "Trinh",
    "Trung",
    "Tu",
    "Tuan",
    "Tung",
    "Uyen",
    "Van",
    "Viet",
    "Vinh",
    "Vy",
    "Xuan",
    "Yen",
]

PROVINCE_CODES = [
    "001",
    "004",
    "006",
    "008",
    "011",
    "014",
    "017",
    "019",
    "022",
    "024",
    "026",
    "027",
    "030",
    "031",
    "033",
    "034",
    "035",
    "036",
    "037",
    "038",
    "040",
    "042",
    "044",
    "045",
    "046",
    "048",
    "049",
    "051",
    "052",
    "054",
    "056",
    "058",
    "060",
    "062",
    "064",
    "066",
    "067",
    "068",
    "070",
    "072",
    "074",
    "075",
    "077",
    "079",
    "080",
    "082",
    "083",
    "084",
    "086",
    "087",
    "089",
    "091",
    "092",
    "093",
    "094",
    "095",
    "096",
]

PHONE_PREFIXES = ["032", "033", "034", "035", "036", "037", "038", "039", "070", "076", "077", "078", "079", "081", "082", "083", "084", "085", "086", "088", "089", "090", "091", "092", "093", "094", "096", "097", "098"]


async def get_kiot_proxy(client: httpx.AsyncClient, key: str) -> dict | None:
    for endpoint, label in [
        ("https://api.kiotproxy.com/api/v1/proxies/new", "new"),
        ("https://api.kiotproxy.com/api/v1/proxies/current", "current"),
    ]:
        try:
            params = {"key": key}
            if label == "new":
                params["region"] = KIOT_REGION
            res = await client.get(endpoint, params=params, timeout=20)
            data = res.json()
            if data.get("success") and data.get("data"):
                info = data["data"]
                proxy = {
                    "host": info["host"],
                    "port": int(info["httpPort"]),
                    "server": f"http://{info['host']}:{info['httpPort']}",
                    "raw": info.get("http") or f"{info['host']}:{info['httpPort']}",
                    "location": info.get("location", "?"),
                    "ttl": info.get("ttl"),
                    "source": label,
                }
                print(f"KiotProxy {label}: {proxy['raw']} ({proxy['location']})")
                return proxy
            print(f"KiotProxy {label} loi: {data.get('message') or data.get('error') or data}")
        except Exception as exc:
            print(f"KiotProxy {label} exception: {exc}")
    return None


async def gemlogin_update_proxy(client: httpx.AsyncClient, profile_id: str, proxy: dict) -> bool:
    payloads = [
        {"raw_proxy": proxy["raw"]},
        {"proxy": {"mode": "http", "host": proxy["host"], "port": proxy["port"]}},
    ]
    for payload in payloads:
        try:
            res = await client.post(f"{GEMLOGIN_API}/api/profiles/update/{profile_id}", json=payload, timeout=30)
            data = res.json()
            if data.get("success") is not False:
                print(f"GemLogin profile {profile_id} dung proxy {proxy['raw']}")
                return True
            print(f"GemLogin update proxy {profile_id} loi: {data.get('message') or data.get('error') or data}")
        except Exception as exc:
            print(f"GemLogin update proxy {profile_id} exception: {exc}")
    return False


async def gemlogin_create_profile(client: httpx.AsyncClient) -> str | None:
    try:
        res = await client.post(f"{GEMLOGIN_API}/api/profiles/create", json={}, timeout=30)
        data = res.json()
        profile_id = data.get("id") or data.get("data", {}).get("id") or data.get("profile_id")
        if profile_id:
            return str(profile_id)
        print(f"GemLogin create loi: {data}")
    except Exception as exc:
        print(f"GemLogin create exception: {exc}")
    return None


async def gemlogin_start_profile(client: httpx.AsyncClient, profile_id: str) -> str | None:
    try:
        res = await client.get(f"{GEMLOGIN_API}/api/profiles/start/{profile_id}", timeout=60)
        data = res.json()
        if data.get("success") is False:
            message = data.get("message") or data.get("error") or data
            print(f"GemLogin start profile {profile_id}: {message}")
            if isinstance(message, str) and "currently being opened" in message.lower():
                await asyncio.sleep(3)

        remote_debugging_address = (
            data.get("data", {}).get("remote_debugging_address")
            or data.get("remote_debugging_address")
        )
        if not remote_debugging_address:
            ws_url = (
                data.get("wsUrl")
                or data.get("data", {}).get("wsUrl")
                or data.get("ws", {}).get("puppeteer")
                or data.get("data", {}).get("ws")
                or data.get("data", {}).get("webSocketDebuggerUrl")
                or data.get("webSocketDebuggerUrl")
            )
            if ws_url:
                return ws_url
            print(f"GemLogin start response khong co wsUrl: {json.dumps(data, ensure_ascii=False)[:300]}")
            return None

        debug_url = f"http://{remote_debugging_address}/json/version"
        await asyncio.sleep(2)
        ver_res = await client.get(debug_url, timeout=15)
        ver_data = ver_res.json()
        ws_url = ver_data.get("webSocketDebuggerUrl")
        if ws_url:
            return ws_url
        print(f"/json/version khong co webSocketDebuggerUrl: {json.dumps(ver_data, ensure_ascii=False)[:300]}")
    except Exception as exc:
        print(f"GemLogin start exception: {type(exc).__name__}: {exc}")
    return None


async def gemlogin_close_profile(client: httpx.AsyncClient, profile_id: str) -> None:
    try:
        await client.get(f"{GEMLOGIN_API}/api/profiles/close/{profile_id}", timeout=15)
    except Exception:
        pass


async def gemlogin_check_profile_status(client: httpx.AsyncClient, profile_id: str) -> str | None:
    try:
        res = await client.post(f"{GEMLOGIN_API}/api/profiles/check-status/{profile_id}", timeout=10)
        data = res.json()
        status = data.get("status") or data.get("data", {}).get("status")
        if status:
            return status
        message = str(data.get("message") or "")
        if "not running" in message.lower():
            return "closed"
        return message or None
    except Exception:
        return None


def get_work_area() -> tuple[int, int, int, int]:
    try:
        import ctypes
        import ctypes.wintypes

        rect = ctypes.wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if ok and width > 0 and height > 0:
            return rect.left, rect.top, width, height
    except Exception:
        pass
    return 0, 0, 1536, 824


def build_window_positions(count: int) -> list[dict[str, int]]:
    screen_x, screen_y, screen_w, screen_h = get_work_area()
    cols = min(6, max(1, count))
    rows = max(1, (count + cols - 1) // cols)
    win_w = screen_w // cols
    win_h = screen_h // rows
    positions = []
    for i in range(count):
        col = i % cols
        row = i // cols
        x = screen_x + col * win_w
        y = screen_y + row * win_h
        width = screen_x + screen_w - x if col == cols - 1 else win_w
        height = screen_y + screen_h - y if row == rows - 1 else win_h
        positions.append({"x": x, "y": y, "w": width, "h": height})
    return positions


async def prepare_profile_window(browser, context, worker_index: int, positions: list[dict[str, int]], tag: str) -> Page:
    page = context.pages[0] if context.pages else await context.new_page()
    if worker_index >= len(positions):
        return page

    pos = positions[worker_index]
    await page.set_viewport_size({"width": pos["w"], "height": pos["h"]})
    try:
        page_session = await context.new_cdp_session(page)
        target_info = await page_session.send("Target.getTargetInfo")
        target_id = target_info.get("targetInfo", {}).get("targetId")
        browser_session = await browser.new_browser_cdp_session()
        window_info = await browser_session.send(
            "Browser.getWindowForTarget",
            {"targetId": target_id} if target_id else {},
        )
        await browser_session.send(
            "Browser.setWindowBounds",
            {"windowId": window_info["windowId"], "bounds": {"windowState": "normal"}},
        )
        await browser_session.send(
            "Browser.setWindowBounds",
            {
                "windowId": window_info["windowId"],
                "bounds": {
                    "left": pos["x"],
                    "top": pos["y"],
                    "width": pos["w"],
                    "height": pos["h"],
                },
            },
        )
        print(f"{tag} Window: ({pos['x']},{pos['y']}) {pos['w']}x{pos['h']}")
    except Exception as exc:
        print(f"{tag} Khong set duoc vi tri window qua CDP: {exc}")
    return page


def remove_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    no_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return no_marks.replace("\u0111", "d").replace("\u0110", "D")


def random_vietnamese_name() -> str:
    parts = [random.choice(LAST_NAMES), random.choice(MIDDLE_NAMES)]
    if random.random() < 0.35:
        second_middle = random.choice(MIDDLE_NAMES)
        if second_middle not in parts:
            parts.append(second_middle)
    parts.append(random.choice(GIVEN_NAMES))
    name = " ".join(parts)
    return remove_accents(name).upper()


def gender_century_digit(year: int, gender: str) -> str:
    century_index = (year - 1900) // 100
    base = century_index * 2
    if gender == "female":
        base += 1
    return str(base)


def random_birth_date() -> date:
    year = random.randint(1988, 2007)
    month = random.randint(1, 12)
    if month == 2:
        max_day = 29 if year % 4 == 0 else 28
    elif month in {4, 6, 9, 11}:
        max_day = 30
    else:
        max_day = 31
    return date(year, month, random.randint(1, max_day))


def random_cccd_for_birth(birth: date) -> str:
    gender = random.choice(["male", "female"])
    return "".join(
        [
            random.choice(PROVINCE_CODES),
            gender_century_digit(birth.year, gender),
            f"{birth.year % 100:02d}",
            f"{random.randint(0, 999999):06d}",
        ]
    )


def load_used_cccd() -> set[str]:
    try:
        with open(USED_CCCD_FILE, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def reserve_unique_cccd(birth: date) -> str:
    used_cccd = load_used_cccd()
    for _ in range(1000):
        cccd = random_cccd_for_birth(birth)
        if cccd not in used_cccd:
            with open(USED_CCCD_FILE, "a", encoding="utf-8") as f:
                f.write(f"{cccd}\n")
            return cccd
    raise RuntimeError("Khong sinh duoc CCCD moi sau 1000 lan thu")


def random_phone() -> str:
    return random.choice(PHONE_PREFIXES) + f"{random.randint(0, 9999999):07d}"


def random_email_local() -> str:
    letters = "abcdefghijklmnopqrstuvwxyz"
    first = "".join(random.choice(letters) for _ in range(random.randint(5, 8)))
    second = "".join(random.choice(letters) for _ in range(random.randint(4, 7)))
    digits = random.randint(10, 9999)
    return f"{first}{second}{digits}"


def random_password() -> str:
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"
    specials = "!@#$%&*"
    chars = letters + digits + specials
    base = [
        random.choice("abcdefghijklmnopqrstuvwxyz"),
        random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        random.choice(digits),
        random.choice(specials),
    ]
    base.extend(random.choice(chars) for _ in range(random.randint(6, 10)))
    random.shuffle(base)
    return "".join(base)


def read_next_email() -> str:
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                email = line.strip().split("|")[0].strip()
                if email:
                    return email
    except FileNotFoundError:
        pass
    local = random_email_local()
    return f"{local}@vitaspherelife.com"


async def get_confirmation_link(email: str, max_retries: int = 30, proxy_server: str | None = None) -> str | None:
    local_part, domain = email.split("@", 1)
    inbox_url = f"https://generator.email/{local_part}@{domain}"

    async with httpx.AsyncClient(follow_redirects=True, proxy=proxy_server) as client:
        for i in range(max_retries):
            try:
                res = await client.get(
                    inbox_url,
                    headers={
                        "cookie": f"surl={domain}%2F{local_part}",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    timeout=20,
                )
                soup = BeautifulSoup(res.text, "html.parser")

                confirm_selectors = [
                    'td[bgcolor="#414141"] a[href]',
                    'td[style*="background: #414141"] a[href]',
                    'a[href*="r.wwwdigitalnetwork.com/tr/cl/"]',
                ]
                for selector in confirm_selectors:
                    for a_tag in soup.select(selector):
                        text = remove_accents(a_tag.get_text(" ", strip=True)).lower()
                        href = a_tag.get("href", "")
                        if href and ("xac nhan" in text or "r.wwwdigitalnetwork.com/tr/cl/" in href):
                            if href.startswith("//"):
                                href = "https:" + href
                            return href

                for a_tag in soup.find_all("a", href=True):
                    text = remove_accents(a_tag.get_text(" ", strip=True)).lower()
                    href = a_tag["href"]
                    if "xac nhan" in text or "confirm" in text:
                        if href.startswith("//"):
                            href = "https:" + href
                        return href
            except Exception as exc:
                print(f"Chua doc duoc mail lan {i + 1}: {exc}")
            await asyncio.sleep(3)
    return None


async def process_one_account(
    page: Page,
    email: str,
    password: str | None = None,
    tag: str = "",
    request_proxy: str | None = None,
) -> dict:
    full_name = random_vietnamese_name()
    birth_date = random_birth_date()
    cccd = reserve_unique_cccd(birth_date)
    account_email = email
    account_password = password or account_email
    phone = random_phone()

    try:
        await page.goto(REGISTER_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector(USERNAME_SELECTOR, timeout=30000)

        await page.fill(USERNAME_SELECTOR, full_name)
        await page.fill('input#identificationID[name="identificationID"]', cccd)
        await page.fill('input#identificationDate[name="identificationDate"]', birth_date.isoformat())
        await page.fill('input#email[name="email"]', account_email)

        phone_input = page.locator('input[name="phone"]')
        await phone_input.click()
        await phone_input.press("Control+A")
        await phone_input.press("Backspace")
        await page.keyboard.type(phone, delay=random.randint(70, 130))

        password_input = page.locator('input#password[name="password"]')
        await password_input.click()
        await password_input.press("Control+A")
        await password_input.press("Backspace")
        await page.keyboard.type(account_password, delay=random.randint(70, 130))

        await page.wait_for_timeout(1500)

        for selector in ['input[name="acceptTerm"]', 'input[name="acceptPrivacy"]']:
            checkboxes = page.locator(selector)
            for i in range(await checkboxes.count()):
                checkbox = checkboxes.nth(i)
                if not await checkbox.is_checked():
                    await checkbox.check()

        print(f"{tag} Da dien ten: {full_name}")
        print(f"{tag} Da dien CCCD: {cccd} (nam sinh {birth_date.year})")
        print(f"{tag} Da dien ngay: {birth_date.isoformat()}")
        print(f"{tag} Da dien email: {account_email}")
        print(f"{tag} Da dien phone: {phone}")

        await page.wait_for_timeout(500)
        success_message = page.locator(".login-success").first
        submit_buttons = page.locator('button[type="submit"]')
        clicked_submit = False
        click_error = None

        for i in range(await submit_buttons.count()):
            button = submit_buttons.nth(i)
            try:
                if await button.is_visible(timeout=1000):
                    await button.scroll_into_view_if_needed(timeout=5000)
                    await button.click(timeout=10000)
                    clicked_submit = True
                    break
            except Exception as exc:
                click_error = exc

        if not clicked_submit:
            try:
                await page.evaluate(
                    """() => {
                        const buttons = Array.from(document.querySelectorAll('button[type="submit"]'));
                        const visibleButton = buttons.find((button) => {
                            const rect = button.getBoundingClientRect();
                            const style = window.getComputedStyle(button);
                            return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                        });
                        if (!visibleButton) {
                            throw new Error('No visible submit button');
                        }
                        visibleButton.click();
                    }"""
                )
                clicked_submit = True
            except Exception:
                if await page.locator(".login-success").count() == 0:
                    raise click_error or Exception("Khong bam duoc nut DANG KY")

        try:
            await success_message.wait_for(timeout=15000)
            print(f"{tag} Da bam DANG KY, trang bao dang ky thanh cong. Dang cho mail xac nhan...")
        except Exception:
            messages = []
            for selector in [
                ".login-error",
                ".error",
                ".invalid-feedback",
                "[class*='error']",
                "[class*='invalid']",
                ".text-milanoRed",
            ]:
                try:
                    for text in await page.locator(selector).all_inner_texts():
                        text = " ".join(text.split())
                        if text and text not in messages:
                            messages.append(text)
                except Exception:
                    pass
            if messages:
                print(f"{tag} Thong bao tren trang: {' | '.join(messages[:5])}")
            raise Exception("Da bam DANG KY nhung khong thay thong bao thanh cong, dung doc mail xac nhan")

        confirm_link = await get_confirmation_link(account_email, proxy_server=request_proxy)
        if confirm_link:
            print(f"{tag} Tim thay link xac nhan: {confirm_link}")
            try:
                await page.goto(confirm_link, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                await page.goto(confirm_link, wait_until="commit", timeout=30000)
            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{account_email}|{account_password}\n")
            print(f"{tag} Da xac nhan va luu vao {RESULTS_FILE}")
        else:
            print(f"{tag} Khong tim thay link xac nhan trong mail.")

        return {
            "name": full_name,
            "cccd": cccd,
            "date": birth_date.isoformat(),
            "email": account_email,
            "phone": phone,
            "confirmed": bool(confirm_link),
            "success": bool(confirm_link),
        }
    except Exception as exc:
        print(f"{tag} Loi account {account_email}: {exc}")
        return {
            "name": full_name,
            "cccd": cccd,
            "date": birth_date.isoformat(),
            "email": account_email,
            "phone": phone,
            "confirmed": False,
            "success": False,
            "reason": str(exc),
        }


async def fill_form(headless: bool, keep_open: bool, email: str | None, password: str | None) -> dict:
    account_email = email or read_next_email()
    auto_email = email is None
    request_proxy = None
    async with async_playwright() as pw:
        launch_kwargs = {"headless": headless}
        if KIOT_KEYS:
            async with httpx.AsyncClient() as http_client:
                proxy = await get_kiot_proxy(http_client, KIOT_KEYS[0])
            if proxy:
                launch_kwargs["proxy"] = {"server": proxy["server"]}
                request_proxy = proxy["server"]
                print(f"[LOCAL] Dung KiotProxy {proxy['raw']}")
            else:
                print("[LOCAL] Khong lay duoc KiotProxy, chay khong proxy.")
        browser = await pw.chromium.launch(**launch_kwargs)
        page = await browser.new_page()
        result = await process_one_account(page, account_email, password, "[LOCAL]", request_proxy)
        if auto_email:
            remove_account_from_file(account_email)
            print(f"[LOCAL] Da bo {account_email} khoi {ACCOUNTS_FILE}, lan sau se dung mail tiep theo.")

        if keep_open:
            print("Nhan Enter de dong trinh duyet...")
            await asyncio.to_thread(sys.stdin.readline)
        else:
            await page.wait_for_timeout(3000)

        await browser.close()

    return result


def remove_account_from_file(email: str) -> None:
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            remaining = []
            for line in f:
                stripped = line.strip()
                if stripped and stripped.split("|")[0].strip() != email:
                    remaining.append(stripped)
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(remaining) + "\n" if remaining else "")
    except FileNotFoundError:
        pass


async def read_accounts(limit: int | None = None) -> list[dict]:
    lines = []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        pass

    if not lines:
        count = int(config.get("accountCount", 100))
        print(f"Chua co {ACCOUNTS_FILE}, tu tao {count} email...")
        from create import main as create_main

        await create_main()
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            pass

    accounts = []
    for idx, line in enumerate(lines):
        parts = [part.strip() for part in line.split("|")]
        email = parts[0]
        password = parts[1] if len(parts) > 1 and parts[1] else email
        if email:
            accounts.append({"email": email, "password": password, "idx": idx + 1})
        if limit and len(accounts) >= limit:
            break
    return accounts


async def prepare_gemlogin_profiles(needed: int) -> list[str]:
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.get(f"{GEMLOGIN_API}/api/profiles", timeout=10)
            data = res.json()
            profiles = data if isinstance(data, list) else data.get("data", data.get("profiles", []))
            profile_ids = [str(p.get("id") or p.get("profile_id") or p) for p in profiles]
            print(f"GemLogin dang chay, hien co {len(profile_ids)} profile.")
        except Exception as exc:
            print(f"Khong ket noi duoc GemLogin tai {GEMLOGIN_API}: {exc}")
            print("Hay mo GemLogin truoc khi chay register_new.py.")
            return []

        print("Dong cac profile cu de reset trang thai...")
        for profile_id in profile_ids:
            await gemlogin_close_profile(http_client, profile_id)

        print("Doi profile dong hoan toan...")
        for profile_id in profile_ids:
            for _ in range(20):
                status = await gemlogin_check_profile_status(http_client, profile_id)
                if status and "close" in status.lower():
                    break
                await asyncio.sleep(1)
        await asyncio.sleep(2)

        if len(profile_ids) < needed:
            to_create = needed - len(profile_ids)
            print(f"Can {needed} profile, tao them {to_create} profile...")
            for _ in range(to_create):
                new_id = await gemlogin_create_profile(http_client)
                if new_id:
                    profile_ids.append(new_id)
                    print(f"Da tao profile {new_id}")
                else:
                    print("Khong tao duoc profile moi.")

        use_profile_ids = profile_ids[:needed]
        if KIOT_KEYS:
            if len(KIOT_KEYS) < len(use_profile_ids):
                print(f"Canh bao: chi co {len(KIOT_KEYS)} KiotProxy key cho {len(use_profile_ids)} profile, se dung lai key.")
            for i, profile_id in enumerate(use_profile_ids):
                key = KIOT_KEYS[i % len(KIOT_KEYS)]
                proxy = await get_kiot_proxy(http_client, key)
                if proxy:
                    ok = await gemlogin_update_proxy(http_client, profile_id, proxy)
                    if not ok:
                        print(f"Khong gan duoc proxy cho profile {profile_id}.")
                    else:
                        PROFILE_PROXIES[profile_id] = proxy
                else:
                    print(f"Khong lay duoc proxy Kiot cho profile {profile_id}.")
        else:
            print("KiotProxy: chua co key trong config.json, chay khong proxy.")

    return profile_ids[:needed]


async def gemlogin_worker(
    pw,
    http_client: httpx.AsyncClient,
    profile_id: str,
    account_queue: asyncio.Queue,
    results: list[dict],
    worker_name: str,
    worker_index: int,
    positions: list[dict[str, int]],
    start_event: asyncio.Event,
) -> None:
    tag = f"[{worker_name}]"
    ws_url = None
    for attempt in range(1, 6):
        print(f"{tag} Start profile {profile_id} lan {attempt}...")
        ws_url = await gemlogin_start_profile(http_client, profile_id)
        if ws_url:
            break
        await asyncio.sleep(5)

    if not ws_url:
        print(f"{tag} Khong start duoc profile {profile_id}.")
        return

    browser = await pw.chromium.connect_over_cdp(ws_url)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = await prepare_profile_window(browser, context, worker_index, positions, tag)
    await start_event.wait()

    try:
        while True:
            try:
                acc = account_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            email = acc["email"]
            acc_tag = f"[{worker_name} | Acc {acc['idx']}]"
            try:
                await context.clear_cookies()
                if page.is_closed():
                    page = await context.new_page()
                proxy = PROFILE_PROXIES.get(profile_id)
                request_proxy = proxy["server"] if proxy else None
                result = await process_one_account(page, email, acc["password"], acc_tag, request_proxy)
                results.append(result)
                remove_account_from_file(email)
            finally:
                try:
                    if not page.is_closed():
                        await page.goto("about:blank", wait_until="commit", timeout=5000)
                except Exception:
                    pass
            await asyncio.sleep(0.5)
    except Exception as exc:
        print(f"{tag} Worker loi: {exc}")
    finally:
        print(f"{tag} Dong profile {profile_id}...")
        await gemlogin_close_profile(http_client, profile_id)


async def run_gemlogin(limit: int | None = None) -> None:
    accounts = await read_accounts(limit)
    if not accounts:
        print(f"Khong co account trong {ACCOUNTS_FILE}.")
        return

    needed = min(CONCURRENCY, len(accounts))
    profile_ids = await prepare_gemlogin_profiles(needed)
    if not profile_ids:
        return

    print(f"Doc {len(accounts)} account tu {ACCOUNTS_FILE}")
    print(f"GemLogin: {len(profile_ids)} profile ({', '.join(profile_ids)})")
    print(f"GemLogin API: {GEMLOGIN_API}")

    queue: asyncio.Queue = asyncio.Queue()
    for acc in accounts:
        await queue.put(acc)

    positions = build_window_positions(len(profile_ids))
    results: list[dict] = []

    async with async_playwright() as pw:
        async with httpx.AsyncClient() as http_client:
            start_event = asyncio.Event()

            async def release_after_setup() -> None:
                await asyncio.sleep(10)
                start_event.set()

            async def run_staggered_workers() -> None:
                tasks = []
                for i, profile_id in enumerate(profile_ids):
                    worker_name = f"P{i + 1}:{profile_id[:8]}"
                    tasks.append(
                        asyncio.create_task(
                            gemlogin_worker(
                                pw,
                                http_client,
                                profile_id,
                                queue,
                                results,
                                worker_name,
                                i,
                                positions,
                                start_event,
                            )
                        )
                    )
                    if i < len(profile_ids) - 1:
                        await asyncio.sleep(2)
                await asyncio.gather(*tasks)

            await asyncio.gather(run_staggered_workers(), release_after_setup())

    success_count = sum(1 for item in results if item.get("success"))
    fail_count = len(results) - success_count
    print(f"Ket qua: {success_count} thanh cong / {fail_count} that bai / {len(accounts)} tong")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Chay an trinh duyet.")
    parser.add_argument("--keep-open", action="store_true", help="Giu trinh duyet mo sau khi chay local.")
    parser.add_argument("--email", help="Email dung de dang ky. Mac dinh lay dong dau tien trong accounts.txt.")
    parser.add_argument("--password", help="Mat khau. Mac dinh trung voi email.")
    parser.add_argument("--limit", type=int, help="Gioi han so account lay tu accounts.txt khi chay GemLogin.")
    parser.add_argument("--local", action="store_true", help="Chay bang Chromium local, khong dung GemLogin.")
    args = parser.parse_args()

    if args.local or args.email:
        await fill_form(
            headless=args.headless,
            keep_open=args.keep_open,
            email=args.email,
            password=args.password,
        )
    else:
        await run_gemlogin(args.limit)


if __name__ == "__main__":
    asyncio.run(main())
