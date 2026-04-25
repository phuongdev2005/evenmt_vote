"""
ĐĂNG KÝ ELLE BEAUTY AWARDS — GemLogin + Playwright
Mỗi account = 1 GemLogin profile riêng biệt (anti-detect)
"""
import json
import asyncio
import random
import time
import sys
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, Page
from colorama import Fore, Style, init

init()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

REGISTER_URL = config.get("elleRegisterUrl", "https://events.elle.vn/register?returnTo=%2Felle-beauty-awards-2026")
CONCURRENCY = config.get("concurrency", 5)
KIOT_KEYS: list[str] = config.get("kiotProxyKeys", [])
KIOT_REGION = config.get("kiotRegion", "random")
GEMLOGIN_API = config.get("gemloginApi", "http://localhost:1010")

RESULTS_FILE = "mail.txt"
ACCOUNTS_FILE = "accounts.txt"

# ===== AVAILABLE EMAIL DOMAINS =====
EMAIL_DOMAINS = [
    "24mail.top",
    "abyis.com",
    "alightmotion.id",
    "amazinggift.life",
    "annd.us",
    "arthiq.world",
    "au1688x.us",
    "basakerrr.digital",
    "btcmod.com",
    "checkotpmail.com",
    "chiamn.com",
    "chongqilai.cc",
    "clonehotmail.click",
    "code-gmail.com",
    "dontsleep404.com",
    "donusumekatil.com",
    "easyhomefit.com",
    "edgetopgrid.com",
    "fbviamail.com",
    "fviamail.com",
    "generator1email.com",
    "gmaiil.top",
    "gmail2.gq",
    "gmail2.shop",
    "gmaillk.com",
    "gptpluz2.shop",
    "higuruma.site",
    "histartool.com",
    "iapermisul.ro",
    "javaka.live",
    "jieluv.com",
    "jualakun.com",
    "kajaib.social",
    "kt-family.my.id",
    "kt-gmail.com",
    "kunseller.top",
    "linkbm365.com",
    "luffygadgets.com",
    "mabubsa.com",
    "mailgetget.asia",
    "meser.cc",
    "miscalhero.com",
    "mlemmlem.asia",
    "moreablle.com",
    "nangspa.vn",
    "navermail.kr",
    "nevanata.com",
    "ngontol.com",
    "opelkun.net",
    "peakpoppro.com",
    "phanmembanhang24h.com",
    "plup.me",
    "redproxies.com",
    "remaild.com",
    "riko.my",
    "shopeeboost.com",
    "sociefan.com",
    "streamingku.live",
    "tempmail247.top",
    "voucherskuy.com",
    "vregion.ru",
    "warunkto.com",
    "zavex.sbs"
]


# ===== GEMLOGIN API =====
async def gemlogin_create_profile(client: httpx.AsyncClient) -> str | None:
    """Tạo 1 profile GemLogin mới, trả về profile_id"""
    try:
        res = await client.post(f"{GEMLOGIN_API}/api/profiles/create", json={}, timeout=30)
        data = res.json()
        profile_id = data.get("id") or data.get("data", {}).get("id") or data.get("profile_id")
        if profile_id:
            return str(profile_id)
        print(f"{Fore.RED}❌ GemLogin create lỗi: {data}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ GemLogin create exception: {e}{Style.RESET_ALL}")
    return None


async def gemlogin_start_profile(client: httpx.AsyncClient, profile_id: str) -> str | None:
    """Start profile, lấy remote_debugging_address rồi query /json/version để lấy wsUrl"""
    try:
        res = await client.get(f"{GEMLOGIN_API}/api/profiles/start/{profile_id}", timeout=60)
        data = res.json()
        if data.get("success") is False:
            message = data.get("message") or data.get("error") or data
            print(f"{Fore.YELLOW}⚠️  GemLogin start profile {profile_id}: {message}{Style.RESET_ALL}")
            if isinstance(message, str) and "currently being opened" in message.lower():
                await asyncio.sleep(3)

        # Lấy remote_debugging_address từ response
        rda = (
            data.get("data", {}).get("remote_debugging_address")
            or data.get("remote_debugging_address")
        )
        if not rda:
            # Fallback: tìm wsUrl trực tiếp
            ws_url = (
                data.get("wsUrl") or data.get("data", {}).get("wsUrl")
                or data.get("ws", {}).get("puppeteer")
                or data.get("data", {}).get("ws")
                or data.get("data", {}).get("webSocketDebuggerUrl")
                or data.get("webSocketDebuggerUrl")
            )
            if ws_url:
                return ws_url
            print(f"{Fore.YELLOW}⚠️  GemLogin start response: {json.dumps(data, ensure_ascii=False)[:300]}{Style.RESET_ALL}")
            return None

        # Query /json/version từ debug port để lấy webSocketDebuggerUrl
        debug_url = f"http://{rda}/json/version"
        print(f"{Fore.LIGHTBLACK_EX}   [DEBUG] Lấy wsUrl từ {debug_url}...{Style.RESET_ALL}")
        await asyncio.sleep(2)  # chờ browser khởi động xong
        ver_res = await client.get(debug_url, timeout=15)
        ver_data = ver_res.json()
        ws_url = ver_data.get("webSocketDebuggerUrl")
        if ws_url:
            return ws_url

        print(f"{Fore.YELLOW}⚠️  /json/version response: {json.dumps(ver_data, ensure_ascii=False)[:300]}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ GemLogin start exception: {type(e).__name__}: {e}{Style.RESET_ALL}")
    return None


async def gemlogin_close_profile(client: httpx.AsyncClient, profile_id: str):
    """Đóng browser profile"""
    try:
        await client.get(f"{GEMLOGIN_API}/api/profiles/close/{profile_id}", timeout=15)
    except:
        pass


async def gemlogin_check_profile_status(client: httpx.AsyncClient, profile_id: str) -> str | None:
    """Kiểm tra trạng thái profile, trả về status string"""
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
    except:
        return None


# ===== KIOT PROXY =====
async def get_new_proxy(client: httpx.AsyncClient, key: str) -> str | None:
    """Lấy proxy mới từ KiotProxy, trả về dạng host:port"""
    try:
        res = await client.get(
            "https://api.kiotproxy.com/api/v1/proxies/new",
            params={"key": key, "region": KIOT_REGION},
            timeout=15,
        )
        data = res.json()
        if data.get("success") and data.get("data"):
            info = data["data"]
            print(f"{Fore.BLUE}🌐 Proxy: {info['host']}:{info['httpPort']} ({info.get('location', '?')}){Style.RESET_ALL}")
            return f"{info['host']}:{info['httpPort']}"
        print(f"{Fore.RED}❌ Proxy lỗi: {data.get('message', data.get('error'))}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ KiotProxy lỗi: {e}{Style.RESET_ALL}")
    return None


# ===== ĐỌC MAIL XÁC NHẬN =====
async def get_confirmation_link(email: str, max_retries: int = 30) -> str | None:
    """Đọc inbox generator.email, tìm link xác nhận"""
    local_part, domain = email.split("@")
    inbox_url = f"https://generator.email/{local_part}@{domain}"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i in range(max_retries):
            try:
                res = await client.get(
                    inbox_url,
                    headers={
                        "cookie": f"surl={domain}%2F{local_part}",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    timeout=15,
                )
                soup = BeautifulSoup(res.text, "html.parser")
                # Ưu tiên 1: Tìm link có text chính xác "Xác nhận"
                for a_tag in soup.find_all("a", href=True):
                    text = a_tag.get_text(strip=True)
                    if text == "Xác nhận":
                        href = a_tag["href"]
                        if href.startswith("//"):
                            href = "https:" + href
                        return href
                # Ưu tiên 2: Tìm link trong td có class heroBtnConfirm
                btn_td = soup.find("td", class_="heroBtnConfirm")
                if btn_td:
                    a_tag = btn_td.find("a", href=True)
                    if a_tag:
                        href = a_tag["href"]
                        if href.startswith("//"):
                            href = "https:" + href
                        return href
            except:
                pass
            if i < max_retries - 1:
                await asyncio.sleep(3)
    return None


# ===== GIẢI CLOUDFLARE TURNSTILE =====
async def has_turnstile(page: Page) -> bool:
    """Kiểm tra trang hiện tại có Cloudflare Turnstile hay không."""
    try:
        has_widget = await page.evaluate("""() => !!(
            document.querySelector('[name="cf-turnstile-response"]') ||
            document.querySelector('.cf-turnstile') ||
            document.querySelector('[data-sitekey]')
        )""")
        if has_widget:
            return True
    except Exception:
        pass

    return any(
        any(kw in frame.url for kw in ["challenges.cloudflare", "turnstile"])
        for frame in page.frames
    )


async def solve_turnstile(page: Page, max_retries: int = 5) -> bool:
    async def is_solved() -> bool:
        try:
            token = await page.evaluate("""() => {
                const el = document.querySelector('[name="cf-turnstile-response"]');
                return el ? el.value : null;
            }""")
            return bool(token and len(token) > 10)
        except:
            return False

    if await is_solved():
        return True

    for attempt in range(1, max_retries + 1):
        # Tìm CF frame → scrollIntoView → click center (y hệt debug_turnstile.py)
        for frame in page.frames:
            if any(kw in frame.url for kw in ["challenges.cloudflare", "turnstile"]):
                try:
                    fe = await frame.frame_element()
                    await fe.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
                    await asyncio.sleep(0.5)
                    box = await fe.bounding_box()
                    if box and box["y"] > 0 and box["width"] > 10:
                        cx = box["x"] + box["width"] / 2
                        cy = box["y"] + box["height"] / 2
                        await page.mouse.move(cx, cy, steps=10)
                        await asyncio.sleep(0.3)
                        await page.mouse.click(cx, cy)
                        print(f"   [CF] Click center ({int(cx)}, {int(cy)}) (lần {attempt})")
                except Exception as e:
                    print(f"   [CF] Lỗi: {e}")
                break

        # Chờ token
        for w in range(8):
            if await is_solved():
                return True
            await asyncio.sleep(1)

    return False


async def simulate_human_behavior(page: Page):
    """Di chuột random + scroll giống người thật (từ cloudflare.js)"""
    for _ in range(3):
        x = 100 + random.random() * 300
        y = 100 + random.random() * 200
        await page.mouse.move(x, y, steps=8 + random.randint(0, 10))
        await asyncio.sleep(random.uniform(0.2, 0.5))
    await page.evaluate("window.scrollBy(0, Math.floor(Math.random() * 200))")
    await asyncio.sleep(random.uniform(0.5, 1.0))


async def _human_click(page: Page, x: float, y: float):
    """Di chuột Bézier bậc 3 rồi click (từ cloudflare.js humanMouseMove)"""
    sx, sy = 100 + random.random() * 400, 100 + random.random() * 200
    steps = 15 + random.randint(0, 10)
    cp1x = sx + (x - sx) * 0.25 + (random.random() - 0.5) * 100
    cp1y = sy + (y - sy) * 0.25 + (random.random() - 0.5) * 80
    cp2x = sx + (x - sx) * 0.75 + (random.random() - 0.5) * 100
    cp2y = sy + (y - sy) * 0.75 + (random.random() - 0.5) * 80
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        mx = u**3*sx + 3*u**2*t*cp1x + 3*u*t**2*cp2x + t**3*x
        my = u**3*sy + 3*u**2*t*cp1y + 3*u*t**2*cp2y + t**3*y
        await page.mouse.move(mx, my)
        await asyncio.sleep(random.uniform(0.005, 0.02))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.04, 0.1))
    await page.mouse.up()


# ===== GÕ NHƯ NGƯỜI THẬT =====
async def human_type(page: Page, selector: str, text: str):
    el = await page.query_selector(selector)
    if not el:
        return
    await el.click(click_count=3)
    await page.keyboard.press("Backspace")
    await asyncio.sleep(random.uniform(0.15, 0.35))
    for ch in text:
        await page.keyboard.type(ch)
        await asyncio.sleep(random.uniform(0.03, 0.08))
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.1, 0.25))


async def paste_text(page: Page, selector: str, text: str):
    """Copy text vào clipboard rồi Ctrl+V — nhanh, không lỗi ký tự đặc biệt"""
    el = await page.query_selector(selector)
    if not el:
        return
    await el.click(click_count=3)
    await page.keyboard.press("Backspace")
    await asyncio.sleep(random.uniform(0.1, 0.2))
    await page.evaluate(f"navigator.clipboard.writeText({json.dumps(text)})")
    await page.keyboard.down("Control")
    await page.keyboard.press("v")
    await page.keyboard.up("Control")
    await asyncio.sleep(random.uniform(0.1, 0.3))


async def wait_for_register_form(page: Page, tag: str) -> bool:
    """Đợi form đăng ký sẵn sàng; retry một lần nếu trang chưa render kịp."""
    for attempt in range(1, 3):
        try:
            await page.wait_for_selector('input[name="username"]', state="visible", timeout=30000)
            await page.wait_for_selector('input[name="email"]', state="visible", timeout=10000)
            await page.wait_for_selector('input[name="password"]', state="visible", timeout=10000)
            return True
        except PlaywrightTimeoutError:
            try:
                title = await page.title()
            except Exception:
                title = ""
            print(f"{tag} {Fore.YELLOW}⚠️  Chưa thấy form đăng ký (lần {attempt}/2). url={page.url} title={title[:80]}{Style.RESET_ALL}")
            if attempt < 2:
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"{tag} {Fore.YELLOW}⚠️  Reload trang đăng ký lỗi: {e}{Style.RESET_ALL}")
                await asyncio.sleep(2)

    try:
        body_text = await page.evaluate("document.body ? document.body.innerText.slice(0, 500) : ''")
    except Exception:
        body_text = ""
    print(f"{tag} {Fore.RED}❌ Không thấy form đăng ký. Nội dung trang: {body_text!r}{Style.RESET_ALL}")
    return False


# ===== XỬ LÝ 1 ACCOUNT TRÊN 1 PAGE (đã kết nối sẵn) =====
async def process_one_account(page: Page, email: str, password: str, tag: str) -> dict:
    """Điền form, giải turnstile, submit, đọc mail, click xác nhận cho 1 account"""
    t0 = time.time()
    try:
        # BƯỚC 1: Truy cập trang đăng ký
        print(f"{tag} 📄 Truy cập {REGISTER_URL}")
        await page.goto(REGISTER_URL, wait_until="domcontentloaded", timeout=60000)
        if not await wait_for_register_form(page, tag):
            return {"email": email, "success": False, "reason": "register_form_timeout"}
        await asyncio.sleep(0.5)

        # BƯỚC 2: Điền form
        username = email.split("@")[0]
        print(f"{tag} ✍️  username={username}, email={email}")

        await page.fill('input[name="username"]', username, timeout=30000)
        await asyncio.sleep(0.15)
        await page.fill('input[name="email"]', email, timeout=30000)
        await asyncio.sleep(0.15)
        await page.fill('input[name="password"]', email, timeout=30000)
        await asyncio.sleep(0.15)
        await page.fill('input[name="passwordConfirmation"]', email, timeout=30000)
        await asyncio.sleep(0.15)

        # BƯỚC 3: Giải Cloudflare Turnstile nếu trang có captcha
        if await has_turnstile(page):
            print(f"{tag} 🛡️  Giải Turnstile...")
            await simulate_human_behavior(page)
            MAX_TURNSTILE = 10
            solved = False
            for turnstile_attempt in range(1, MAX_TURNSTILE + 1):
                if await solve_turnstile(page, 3):
                    solved = True
                    break
                print(f"{tag} {Fore.YELLOW}⚠️  Turnstile chưa được (lần {turnstile_attempt}/{MAX_TURNSTILE})...{Style.RESET_ALL}")
                await simulate_human_behavior(page)
                await asyncio.sleep(random.uniform(1, 2))
            if solved:
                print(f"{tag} {Fore.GREEN}✅ Turnstile OK! (sau {turnstile_attempt} vòng){Style.RESET_ALL}")
            else:
                print(f"{tag} {Fore.RED}❌ Turnstile FAIL sau {MAX_TURNSTILE} lần — bỏ qua account{Style.RESET_ALL}")
                return {"email": email, "success": False, "reason": "turnstile_fail"}
        else:
            print(f"{tag} 🛡️  Trang không có Turnstile, bỏ qua captcha.")

        # BƯỚC 4: Submit
        print(f"{tag} 📤 Submit...")
        submit_btn = await page.query_selector('button[type="submit"]')
        if not submit_btn:
            print(f"{tag} {Fore.RED}❌ Không tìm thấy nút submit!{Style.RESET_ALL}")
            return {"email": email, "success": False, "reason": "no_submit_button"}
        # Kiểm tra text nút
        btn_text = await submit_btn.inner_text()
        print(f"{tag}   [DEBUG] Nút submit: '{btn_text}'")
        await submit_btn.click()
        await asyncio.sleep(2)

        # Kiểm tra kết quả submit
        account_created = False
        for i in range(15):
            text = await page.evaluate("document.body.innerText")
            print(f"{tag}   [DEBUG] Kiểm tra submit (lần {i+1}/15)...")
            if "Tài khoản đã được tạo" in text or "Account created" in text:
                account_created = True
                break
            if "Email is already taken" in text or "Email đã tồn tại" in text:
                print(f"{tag} {Fore.YELLOW}⚠️  Email đã tồn tại — bỏ qua{Style.RESET_ALL}")
                return {"email": email, "success": False, "reason": "email_taken"}
            if "Username is already taken" in text or "Username đã tồn tại" in text:
                print(f"{tag} {Fore.YELLOW}⚠️  Username đã tồn tại — bỏ qua{Style.RESET_ALL}")
                return {"email": email, "success": False, "reason": "username_taken"}
            await asyncio.sleep(1)

        if not account_created:
            print(f"{tag} {Fore.RED}❌ Không thấy thông báo tạo tài khoản — submit thất bại{Style.RESET_ALL}")
            return {"email": email, "success": False, "reason": "no_account_created"}

        print(f"{tag} {Fore.GREEN}✅ Tài khoản đã được tạo! Chờ mail xác nhận...{Style.RESET_ALL}")

        # BƯỚC 5: Đọc mail xác nhận
        print(f"{tag} 📧 Chờ mail xác nhận ({email})...")
        confirm_link = await get_confirmation_link(email, 30)
        if not confirm_link:
            print(f"{tag} {Fore.RED}❌ Không tìm thấy link xác nhận!{Style.RESET_ALL}")
            return {"email": email, "success": False, "reason": "no_confirm_link"}

        print(f"{tag} {Fore.GREEN}🔗 Tìm thấy link xác nhận!{Style.RESET_ALL}")

        # BƯỚC 6: Click link xác nhận
        if confirm_link.startswith("//"):
            confirm_link = "https:" + confirm_link
        print(f"{tag} 🖱️  Truy cập link xác nhận...")
        try:
            await page.goto(confirm_link, wait_until="commit", timeout=15000)
        except:
            pass

        # BƯỚC 7: Ghi mail.txt
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{email}\n")
        elapsed = time.time() - t0
        print(f"{tag} {Fore.GREEN}🎉 THÀNH CÔNG! {email} ({elapsed:.0f}s){Style.RESET_ALL}")
        return {"email": email, "success": True}

    except Exception as e:
        print(f"{tag} {Fore.RED}❌ Lỗi: {e}{Style.RESET_ALL}")
        return {"email": email, "success": False, "reason": str(e)}


# ===== SẮP XẾP CỬA SỔ (12 cửa sổ: 6 cột x 2 hàng) =====
COLS = 6
ROWS = 2


def get_work_area() -> tuple[int, int, int, int]:
    """Lấy vùng màn hình làm việc, đã trừ taskbar. Fallback về màn 1536x824."""
    try:
        import ctypes
        import ctypes.wintypes

        rect = ctypes.wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if ok and w > 0 and h > 0:
            return rect.left, rect.top, w, h
    except Exception:
        pass
    return 0, 0, 1536, 824


def build_window_positions(count: int = 12) -> list[dict[str, int]]:
    screen_x, screen_y, screen_w, screen_h = get_work_area()
    win_w = screen_w // COLS
    win_h = screen_h // ROWS
    positions = []
    for i in range(count):
        col = i % COLS
        row = i // COLS
        x = screen_x + col * win_w
        y = screen_y + row * win_h
        w = (screen_x + screen_w - x) if col == COLS - 1 else win_w
        h = (screen_y + screen_h - y) if row == ROWS - 1 else win_h
        positions.append({"x": x, "y": y, "w": w, "h": h})
    return positions


WIN_POSITIONS = build_window_positions()


def arrange_gemlogin_windows():
    """Tìm tất cả cửa sổ Chrome/GemLogin và sắp xếp lên màn hình"""
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    MoveWindow = user32.MoveWindow
    IsWindowVisible = user32.IsWindowVisible
    ShowWindow = user32.ShowWindow
    SW_RESTORE = 9

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    chrome_hwnds = []

    def enum_cb(hwnd, _):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        # Tìm cửa sổ browser GemLogin (title chứa "Gemlogin" hoặc "events.elle.vn")
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        if w < 200:
            return True
        title_lower = title.lower()
        # Bỏ qua app GemLogin chính (title = "GemLogin - x.x.x")
        if title_lower.startswith("gemlogin -"):
            return True
        if "gemlogin" in title_lower or "events.elle.vn" in title_lower:
            chrome_hwnds.append(hwnd)
        return True

    EnumWindows(WNDENUMPROC(enum_cb), 0)

    # Sắp xếp tối đa 5 cửa sổ
    arranged = 0
    for i, hwnd in enumerate(chrome_hwnds[:len(WIN_POSITIONS)]):
        pos = WIN_POSITIONS[i]
        ShowWindow(hwnd, SW_RESTORE)
        MoveWindow(hwnd, pos["x"], pos["y"], pos["w"], pos["h"], True)
        # Log title + vị trí
        buf = ctypes.create_unicode_buffer(200)
        GetWindowTextW(hwnd, buf, 200)
        print(f"   📐 Cửa sổ {i+1}: ({pos['x']},{pos['y']}) {pos['w']}x{pos['h']} \"{buf.value[:40]}\"")
        arranged += 1

    return arranged


async def prepare_profile_window(browser, context, worker_index: int, tag: str):
    """Tạo/lấy page đầu tiên rồi đặt đúng vị trí cửa sổ profile qua CDP."""
    if worker_index >= len(WIN_POSITIONS):
        return context.pages[0] if context.pages else await context.new_page()

    pos = WIN_POSITIONS[worker_index]
    page = context.pages[0] if context.pages else await context.new_page()
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
        window_id = window_info["windowId"]

        await browser_session.send(
            "Browser.setWindowBounds",
            {"windowId": window_id, "bounds": {"windowState": "normal"}},
        )
        await browser_session.send(
            "Browser.setWindowBounds",
            {
                "windowId": window_id,
                "bounds": {
                    "left": pos["x"],
                    "top": pos["y"],
                    "width": pos["w"],
                    "height": pos["h"],
                },
            },
        )
        print(f"{tag}   📐 Window: ({pos['x']},{pos['y']}) {pos['w']}x{pos['h']}")
    except Exception as e:
        print(f"{tag} {Fore.YELLOW}⚠️  Không đặt được vị trí cửa sổ qua CDP: {e}{Style.RESET_ALL}")

    return page


# ===== WORKER: 1 GemLogin profile xử lý nhiều account tuần tự =====
async def profile_worker(
    pw, http_client: httpx.AsyncClient, profile_id: str,
    account_queue: asyncio.Queue, results: list, worker_name: str,
    worker_index: int = 0, start_event: asyncio.Event = None
):
    """Mỗi worker = 1 GemLogin profile cố định, lấy account từ queue, xử lý tuần tự"""
    tag = f"{Fore.CYAN}[{worker_name}]{Style.RESET_ALL}"

    # Start profile → lấy CDP ws endpoint (retry 5 lần)
    ws_url = None
    for attempt in range(1, 6):
        print(f"{tag} 🚀 Start profile {profile_id} (lần {attempt})...")
        ws_url = await gemlogin_start_profile(http_client, profile_id)
        if ws_url:
            break
        print(f"{tag} {Fore.YELLOW}⏳ Đợi 5s rồi thử lại...{Style.RESET_ALL}")
        await asyncio.sleep(5)
    if not ws_url:
        print(f"{tag} {Fore.RED}❌ Không start được profile {profile_id} sau 5 lần!{Style.RESET_ALL}")
        return

    print(f"{tag} 🔗 Kết nối Playwright → {ws_url[:60]}...")
    browser = await pw.chromium.connect_over_cdp(ws_url)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    context.set_default_timeout(30000)
    context.set_default_navigation_timeout(60000)

    # Tạo page sớm để có target CDP, rồi đặt vị trí cửa sổ đúng profile.
    setup_page = await prepare_profile_window(browser, context, worker_index, tag)

    # Chờ tín hiệu sắp xếp cửa sổ xong mới bắt đầu
    if start_event:
        await start_event.wait()

    try:
        while True:
            if not browser.is_connected():
                print(f"{tag} {Fore.RED}❌ Browser đã đóng, dừng worker.{Style.RESET_ALL}")
                break

            # Lấy account tiếp theo từ queue
            try:
                acc = account_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            email = acc["email"]
            password = acc["password"]
            acc_num = acc["idx"]
            acc_tag = f"{Fore.CYAN}[{worker_name} | Acc {acc_num}]{Style.RESET_ALL}"

            # Xóa cookie trước khi chạy account mới
            print(f"{acc_tag} 🧹 Xóa cookie...")
            await context.clear_cookies()

            # Giữ 1 tab sống xuyên suốt worker. Đóng tab cuối có thể làm GemLogin
            # đóng luôn browser, khiến account kế tiếp lỗi "Target ... has been closed".
            page = setup_page if setup_page and not setup_page.is_closed() else await context.new_page()
            setup_page = page
            if worker_index < len(WIN_POSITIONS):
                pos = WIN_POSITIONS[worker_index]
                await page.set_viewport_size({"width": pos["w"], "height": pos["h"]})
            try:
                result = await process_one_account(page, email, password, acc_tag)
                results.append(result)
                # Xóa email đã xử lý khỏi accounts.txt
                try:
                    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                        remaining = [l.strip() for l in f if l.strip() and l.strip() != email]
                    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                        f.write("\n".join(remaining) + "\n" if remaining else "")
                except:
                    pass
            finally:
                try:
                    if not page.is_closed():
                        await page.goto("about:blank", wait_until="commit", timeout=5000)
                except:
                    pass

            await asyncio.sleep(0.5)

    except Exception as e:
        print(f"{tag} {Fore.RED}❌ Worker lỗi: {e}{Style.RESET_ALL}")
    finally:
        # Đóng profile (KHÔNG xóa — giữ lại dùng tiếp)
        print(f"{tag} 🔌 Đóng profile {profile_id}...")
        await gemlogin_close_profile(http_client, profile_id)


# ===== MAIN =====
async def main():
    # Đọc accounts.txt — nếu chưa có hoặc rỗng thì tự chạy create.py
    lines = []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        pass

    if not lines:
        count = config.get("accountCount", 100)
        print(f"{Fore.YELLOW}📝 Chưa có {ACCOUNTS_FILE}, tự tạo {count} email...{Style.RESET_ALL}")
        from create import main as create_main
        await create_main()
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
        except FileNotFoundError:
            pass
        if not lines:
            print(f"{Fore.RED}❌ Tạo email thất bại! {ACCOUNTS_FILE} vẫn rỗng.{Style.RESET_ALL}")
            return

    accounts = []
    for idx, line in enumerate(lines):
        email = line.split("|")[0].strip()
        if email:
            accounts.append({"email": email, "password": email, "idx": idx + 1})

    # ===== Kiểm tra + chuẩn bị GemLogin profiles =====
    needed = CONCURRENCY  # mặc định 5 profile
    async with httpx.AsyncClient() as http_client:
        # 1. Kiểm tra GemLogin đang chạy
        try:
            res = await http_client.get(f"{GEMLOGIN_API}/api/profiles", timeout=10)
            data = res.json()
            profiles = data if isinstance(data, list) else data.get("data", data.get("profiles", []))
            profile_ids = [str(p.get("id") or p.get("profile_id") or p) for p in profiles]
            print(f"{Fore.GREEN}✅ GemLogin đang chạy! Hiện có {len(profile_ids)} profile.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}❌ Không kết nối được GemLogin tại {GEMLOGIN_API}: {e}{Style.RESET_ALL}")
            print(f"{Fore.RED}   Hãy mở GemLogin trước khi chạy tool.{Style.RESET_ALL}")
            return

        # 2. Đóng tất cả profile trước (reset trạng thái)
        print(f"{Fore.YELLOW}⚙️  Đóng tất cả profile cũ...{Style.RESET_ALL}")
        for pid in profile_ids:
            await gemlogin_close_profile(http_client, pid)

        # Đợi tất cả profile thực sự đóng
        print(f"{Fore.YELLOW}⏳ Đợi tất cả profile đóng hoàn toàn...{Style.RESET_ALL}")
        for pid in profile_ids:
            for i in range(20):  # tối đa 20s đợi mỗi profile
                status = await gemlogin_check_profile_status(http_client, pid)
                if status and "close" in status.lower():
                    break
                await asyncio.sleep(1)
        await asyncio.sleep(2)

        # 3. Tự tạo thêm profile nếu chưa đủ
        if len(profile_ids) < needed:
            to_create = needed - len(profile_ids)
            print(f"{Fore.YELLOW}⚙️  Cần {needed} profile, hiện có {len(profile_ids)}. Tạo thêm {to_create}...{Style.RESET_ALL}")
            for i in range(to_create):
                new_id = await gemlogin_create_profile(http_client)
                if new_id:
                    profile_ids.append(new_id)
                    print(f"{Fore.GREEN}   ✅ Tạo profile #{len(profile_ids)}: {new_id}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}   ❌ Không tạo được profile thứ {len(profile_ids) + 1}{Style.RESET_ALL}")

    if not profile_ids:
        print(f"{Fore.RED}❌ Không có profile nào để chạy!{Style.RESET_ALL}")
        return

    num_profiles = min(len(profile_ids), needed)
    use_profiles = profile_ids[:num_profiles]

    print(f"{Fore.YELLOW}\n📝 Đọc được {len(accounts)} tài khoản từ {ACCOUNTS_FILE}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}🖥️  GemLogin: {num_profiles} profile ({', '.join(use_profiles)}){Style.RESET_ALL}")
    print(f"{Fore.YELLOW}🌐 KiotProxy keys: {len(KIOT_KEYS)} keys{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}🖥️  GemLogin API: {GEMLOGIN_API}\n{Style.RESET_ALL}")

    # Đưa tất cả accounts vào queue
    queue: asyncio.Queue = asyncio.Queue()
    for acc in accounts:
        await queue.put(acc)

    results: list[dict] = []

    async with async_playwright() as pw:
        async with httpx.AsyncClient() as http_client:
            start_event = asyncio.Event()

            # Mỗi profile = 1 worker, chạy song song, lấy account từ queue
            tasks = []
            for i, pid in enumerate(use_profiles):
                worker_name = f"P{i+1}:{pid[:8]}"
                tasks.append(profile_worker(
                    pw, http_client, pid, queue, results, worker_name,
                    worker_index=i, start_event=start_event
                ))

            print(f"{Fore.CYAN}🚀 Tự bật {num_profiles} profile...{Style.RESET_ALL}")

            # Chạy song song: start profiles + đợi các worker tự đặt vị trí cửa sổ.
            async def release_after_window_setup():
                await asyncio.sleep(10)
                print(f"{Fore.GREEN}📐 Đã gửi vị trí cửa sổ cho các profile đã khởi động.{Style.RESET_ALL}")
                start_event.set()  # signal workers bắt đầu xử lý

            # Stagger profile starts: delay giữa các worker để tránh conflict
            async def run_staggered_workers():
                started_tasks = []
                for i, task in enumerate(tasks):
                    started_tasks.append(asyncio.create_task(task))
                    if i < len(tasks) - 1:
                        await asyncio.sleep(2)  # delay 2s giữa mỗi profile start
                await asyncio.gather(*started_tasks)

            all_tasks = [run_staggered_workers(), release_after_window_setup()]
            await asyncio.gather(*all_tasks)

    success_count = sum(1 for r in results if r.get("success"))
    fail_count = len(results) - success_count

    print(f"{Fore.YELLOW}\n📊 Kết quả: {Fore.GREEN}{success_count} thành công{Fore.YELLOW} / {Fore.RED}{fail_count} thất bại{Fore.YELLOW} / {len(accounts)} tổng{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}📄 Danh sách thành công lưu tại {RESULTS_FILE}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Hoàn thành!{Style.RESET_ALL}")


if __name__ == "__main__":
    asyncio.run(main())
