"""
Register Elle.vn accounts using SmailPro temporary email API.
Flow: create smailpro email -> register elle.vn -> read inbox -> confirm -> save to smsaccount.txt.
Tham khảo direct_register_httpx.py.
"""

import argparse
import asyncio
import json
import random
import string
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
SMSACCOUNT_FILE = SCRIPT_DIR / "smsaccount.txt"
FAILED_FILE = SCRIPT_DIR / "failed_sms.txt"
RESULTS_FILE = SCRIPT_DIR / "results_sms.txt"

API_BASE = "https://app.sonjj.com/v1/temp_email"
DEFAULT_API_KEY = "9cb5fe11b14da95a62d63efbf8a0e86cfe52483672801c8beefa334f04a628bb"
ELLE_URL = "https://www.elle.vn/dang-ky/"

account_lock = asyncio.Lock()
CONNECTION_LIMITS = httpx.Limits(max_keepalive_connections=100, max_connections=200)


def console_safe(value) -> str:
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = text.replace("\u0111", "d").replace("\u0110", "D")
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def exception_text(exc: Exception) -> str:
    message = str(exc) or repr(exc)
    return f"{type(exc).__name__}: {console_safe(message)}"


# =================== SmailPro API ===================

async def smailpro_create_email(email: str, api_key: str, expiry_minutes: int = 60) -> dict:
    headers = {"Accept": "application/json", "X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{API_BASE}/create"
        params = {"email": email, "expiry_minutes": expiry_minutes}
        res = await client.get(url, params=params, headers=headers)
        res.raise_for_status()
        return res.json()


async def smailpro_inbox(email: str, api_key: str) -> list[dict]:
    headers = {"Accept": "application/json", "X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{API_BASE}/inbox"
        params = {"email": email}
        res = await client.get(url, params=params, headers=headers)
        res.raise_for_status()
        data = res.json()
        return data.get("messages", [])


async def smailpro_message(email: str, mid: str, api_key: str) -> dict:
    headers = {"Accept": "application/json", "X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{API_BASE}/message"
        params = {"email": email, "mid": mid}
        res = await client.get(url, params=params, headers=headers)
        res.raise_for_status()
        return res.json()


# =================== Name / Identity Generators ===================

LAST_NAMES = [
    "An", "Bach", "Banh", "Bui", "Cao", "Chu", "Chung", "Dang", "Dao", "Dinh",
    "Do", "Doan", "Dong", "Du", "Duong", "Giang", "Ha", "Ho", "Hoang", "Huynh",
    "Kha", "Khuat", "Kieu", "La", "Lam", "Le", "Lieu", "Luu", "Ly", "Mai",
    "Mac", "Ngo", "Nguyen", "Nghiem", "Nong", "Ong", "Phan", "Pham", "Phung", "Quach",
    "Ta", "Tang", "Thai", "Than", "Thang", "Thao", "Thach", "To", "Ton", "Tran",
    "Trieu", "Trinh", "Truong", "Tu", "Ung", "Vi", "Vo", "Vu", "Vuong", "Xa", "Yen",
]

MIDDLE_NAMES = [
    "Anh", "Bao", "Bich", "Cam", "Chi", "Cong", "Dai", "Dang", "Dinh", "Duc",
    "Duy", "Gia", "Hai", "Hien", "Hoai", "Hoang", "Hong", "Huu", "Khai", "Khanh",
    "Kim", "Lan", "Mai", "Manh", "Minh", "My", "Nam", "Nhat", "Ngoc", "Nhu",
    "Phu", "Phuc", "Phuong", "Quang", "Quoc", "Tan", "Thanh", "Thao", "Thi", "Thu",
    "Thuy", "Tien", "Trong", "Truc", "Tuan", "Tung", "Van", "Viet", "Xuan",
]

GIVEN_NAMES = [
    "An", "Anh", "Anh Thu", "Bach", "Bao", "Bao Chau", "Bao Han", "Bao Ngoc", "Bao Tram",
    "Binh", "Cam", "Cam Ly", "Chau", "Chi", "Dat", "Diep", "Dung", "Duy", "Duyen",
    "Giang", "Hac", "Giang", "Ha", "Hai", "Han", "Hao", "Hanh", "Hien", "Hieu",
    "Hoa", "Hoai", "Hong", "Huy", "Huynh", "Hung", "Khang", "Khanh", "Khoa", "Khoi",
    "Kiet", "Lam", "Lan", "Linh", "Loan", "Loc", "Long", "Mai", "Manh", "Mi",
    "My", "My Anh", "My Duyen", "My Linh", "Nam", "Nga", "Ngan", "Nghi", "Nghia",
    "Nhat", "Nhu", "Nhi", "Phan", "Phat", "Phuc", "Phung", "Phuong", "Quan", "Quang",
    "Quoc", "Quynh", "Quynh Anh", "Quynh Chi", "Quynh Nhu", "Sang", "Son", "Tam",
    "Tan", "Thang", "Thao", "Thien", "Thinh", "Thoa", "Thu", "Thu Ha", "Thu Huong",
    "Thu Trang", "Thuy", "Thuy Anh", "Tien", "Trang", "Tri", "Trinh", "Trung",
    "Tu", "Tuan", "Tung", "Uyen", "Van", "Viet", "Vinh", "Vy", "Xuan", "Yen",
]

PROVINCE_CODES = [
    "001", "004", "006", "008", "011", "014", "017", "019", "022", "024",
    "026", "027", "030", "031", "033", "034", "035", "036", "037", "038",
    "040", "042", "044", "045", "046", "048", "049", "051", "052", "054",
    "056", "058", "060", "062", "064", "066", "067", "068", "070", "072",
    "074", "075", "077", "079", "080", "082", "083", "084", "086", "087",
    "089", "091", "092", "093", "094", "095", "096",
]

PHONE_PREFIXES = ["032", "033", "034", "035", "036", "037", "038", "039", "070", "076",
                   "077", "078", "079", "081", "082", "083", "084", "085", "086",
                   "088", "089", "090", "091", "092", "093", "094", "096", "097", "098"]


def random_vietnamese_name() -> str:
    parts = [random.choice(LAST_NAMES), random.choice(MIDDLE_NAMES)]
    if random.random() < 0.35:
        second_middle = random.choice(MIDDLE_NAMES)
        if second_middle not in parts:
            parts.append(second_middle)
    parts.append(random.choice(GIVEN_NAMES))
    return " ".join(parts).upper()


def random_phone() -> str:
    return random.choice(PHONE_PREFIXES) + f"{random.randint(0, 9999999):07d}"


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


def add_years_safe(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def random_identification_date(birth: date) -> date:
    earliest = add_years_safe(birth, 14)
    latest = date.today() - timedelta(days=30)
    if earliest > latest:
        earliest = latest
    span_days = max(0, (latest - earliest).days)
    return earliest + timedelta(days=random.randint(0, span_days))


USED_CCCD: set[str] = set()
USED_CCCD_FILE = Path("used_cccd.txt")


def load_used_cccd() -> set[str]:
    if USED_CCCD_FILE.exists():
        with USED_CCCD_FILE.open("r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    return set()


USED_CCCD = load_used_cccd()


def save_used_cccd(cccd: str) -> None:
    USED_CCCD.add(cccd)
    with USED_CCCD_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{cccd}\n")


def random_cccd(birth: date | None = None) -> str:
    birth = birth or random_birth_date()
    gender = random.choice(["male", "female"])
    for _ in range(1000):
        cccd = "".join([
            random.choice(PROVINCE_CODES),
            gender_century_digit(birth.year, gender),
            f"{birth.year % 100:02d}",
            f"{random.randint(0, 999999):06d}",
        ])
        if cccd not in USED_CCCD:
            return cccd
    raise RuntimeError("Cannot generate unique CCCD")


# =================== Elle.vn Registration ===================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def browser_headers(user_agent: str | None = None) -> dict[str, str]:
    return {
        "User-Agent": user_agent or get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def find_register_form(soup: BeautifulSoup):
    forms = soup.find_all("form")
    for form in forms:
        fields = {tag.get("name") for tag in form.find_all(["input", "select", "textarea"]) if tag.get("name")}
        if {"email", "password"} <= fields:
            return form
    return forms[0] if forms else None


def field_value(tag) -> str:
    if tag.name == "select":
        option = tag.find("option", selected=True) or tag.find("option")
        return option.get("value", "") if option else ""
    return tag.get("value") or ""


def form_payload(form, email: str, password: str) -> list[tuple[str, str]]:
    generated_fields = {"username", "identificationID", "identificationDate", "email", "phone", "password"}
    payload: list[tuple[str, str]] = []
    for tag in form.find_all(["input", "select", "textarea"]):
        name = tag.get("name")
        if not name:
            continue
        input_type = (tag.get("type") or "").lower()
        if input_type in {"submit", "button", "file"}:
            continue
        if input_type in {"checkbox", "radio"} and not tag.has_attr("checked"):
            if name not in {"acceptTerm", "acceptPrivacy"}:
                continue
        if name in generated_fields:
            continue
        payload.append((name, field_value(tag) or ("on" if input_type in {"checkbox", "radio"} else "")))

    birth = random_birth_date()
    identification_date = random_identification_date(birth)
    generated = [
        ("username", random_vietnamese_name()),
        ("identificationID", random_cccd(birth)),
        ("identificationDate", identification_date.isoformat()),
        ("email", email),
        ("phone", random_phone()),
        ("password", password),
    ]
    for item in generated:
        payload.append(item)
    return payload


def absolute_url(base_url: str, maybe_url: str | None) -> str:
    return str(httpx.URL(base_url).join(maybe_url or base_url))


def submit_endpoint(page_url: str, form) -> tuple[str, str]:
    hx_post = form.get("hx-post")
    if hx_post:
        return "POST", absolute_url(page_url, hx_post)
    method = (form.get("method") or "GET").upper()
    action = absolute_url(page_url, form.get("action"))
    return method, action


def remove_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    no_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return no_marks.replace("\u0111", "d").replace("\u0110", "D")


def registration_may_have_sent_email(response: httpx.Response, text: str) -> tuple[bool, str]:
    normalized_html = remove_accents(response.text).lower()
    normalized_text = remove_accents(text).lower()

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    if "login-success" in normalized_html:
        return True, "login-success found"
    success_markers = [
        "kiem tra email", "xac thuc tai khoan", "xac nhan email",
        "dang ky thanh cong", "vui long kiem tra",
    ]
    for marker in success_markers:
        if marker in normalized_text:
            return True, f"success marker: {marker}"
    error_markers = [
        "email da ton tai", "email is already taken", "username da ton tai",
        "khong hop le", "invalid", "truong nay la bat buoc",
        "vui long nhap", "vui long dien", "dang ky that bai",
    ]
    for marker in error_markers:
        if marker in normalized_text:
            return False, f"error marker: {marker}"
    return True, "HTTP 200 no clear error"


def normalize_href(href: str, base_url: str) -> str:
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    return urljoin(base_url, href)


def find_confirmation_link(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str, str]] = []
    for a_tag in soup.find_all("a", href=True):
        href = normalize_href(a_tag["href"], base_url)
        text = remove_accents(a_tag.get_text(" ", strip=True)).lower()
        href_lower = remove_accents(href).lower()
        combined = f"{text} {href_lower}"
        host = (urlparse(href).hostname or "").lower()

        reject_markers = [
            "unsubscribe", "preferences", "view-in-browser", "view_email",
            "facebook.com", "instagram.com", "youtube.com", "tiktok.com",
            "generator.email", "smailpro.com",
        ]
        if any(marker in combined or marker in host for marker in reject_markers):
            continue

        score = 0
        for marker in ["xac nhan", "confirm", "verify", "verification", "activate", "activation", "kich hoat"]:
            if marker in text:
                score += 60
            if marker in href_lower:
                score += 25
        for marker in [
            "baseapi.elle.vn/auth/email-confirmation",
            "email-confirmation", "confirmation=",
            "elle.vn", "events.elle.vn",
        ]:
            if marker in href_lower:
                score += 35
        if "token" in href_lower or "key=" in href_lower or "code=" in href_lower:
            score += 20
        if score > 0:
            candidates.append((score, href, text))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def confirmation_succeeded(response: httpx.Response) -> tuple[bool, str]:
    status_ok = 200 <= response.status_code < 400
    text = remove_accents(response.text).lower()
    error_markers = ["error", "invalid", "expired", "not found", "khong hop le", "het han", "loi", "that bai"]
    if not status_ok:
        return False, f"HTTP {response.status_code}"
    for marker in error_markers:
        if marker in text:
            return False, f"error: {marker}"
    return True, f"HTTP {response.status_code}"


# =================== Main Flow ===================

async def register_account(email: str, password: str, api_key: str, client: httpx.AsyncClient) -> bool:
    """Register one Elle.vn account and confirm via SmailPro."""
    try:
        ua = get_random_user_agent()
        page = await client.get(ELLE_URL, headers=browser_headers(ua))
        print(f"GET register page -> {page.status_code}")

        soup = BeautifulSoup(page.text, "lxml")
        form = find_register_form(soup)
        if not form:
            print("FAIL: no register form found")
            return False

        method, endpoint = submit_endpoint(str(page.url), form)
        payload = form_payload(form, email, password)
        headers = {
            **browser_headers(ua),
            "Referer": str(page.url),
            "Origin": f"{httpx.URL(str(page.url)).scheme}://{httpx.URL(str(page.url)).host}",
            "Content-Type": "application/x-www-form-urlencoded",
            "HX-Request": "true",
            "HX-Current-URL": str(page.url),
        }

        if method == "POST":
            from urllib.parse import urlencode
            post_data = urlencode(payload, doseq=True).encode("utf-8")
            response = await client.post(endpoint, content=post_data, headers=headers)
        else:
            response = await client.get(endpoint, params=payload, headers=headers)

        text = " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
        should_check_mail, reason = registration_may_have_sent_email(response, text)
        print(f"Submit -> {response.status_code} | {reason}")

        if not should_check_mail:
            print(f"FAIL: submit failed - {reason}")
            return False

        # Wait for confirmation email in SmailPro inbox
        print("Waiting for confirmation email...")
        confirm_link = None
        for attempt in range(30):
            await asyncio.sleep(5)
            messages = await smailpro_inbox(email, api_key)
            print(f"  Inbox check {attempt + 1}/30: {len(messages)} messages")
            for msg in messages:
                mid = msg.get("id") or msg.get("mid")
                if not mid:
                    continue
                msg_data = await smailpro_message(email, mid, api_key)
                body = msg_data.get("body", "")
                link = find_confirmation_link(body, "https://generator.email/")
                if link:
                    confirm_link = link
                    print(f"  Found confirmation link: {confirm_link}")
                    break
            if confirm_link:
                break

        if not confirm_link:
            print("FAIL: no confirmation link in inbox")
            return False

        # Open confirmation link
        confirm_res = await client.get(
            confirm_link,
            headers={**browser_headers(), "Referer": f"https://generator.email/{email}"},
            timeout=30,
        )
        ok, reason = confirmation_succeeded(confirm_res)
        print(f"Confirm -> {reason}")
        if ok:
            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{email}|{password}\n")
            print(f"SUCCESS: saved to {RESULTS_FILE}")
            cccd = next((v for k, v in payload if k == "identificationID"), None)
            if cccd:
                save_used_cccd(cccd)
            return True
        else:
            print(f"FAIL: confirmation failed - {reason}")
            return False

    except Exception as exc:
        print(f"ERROR: {exception_text(exc)}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Register Elle.vn using SmailPro temp email")
    parser.add_argument("--count", type=int, default=1, help="Number of accounts to create")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="SmailPro API key")
    parser.add_argument("--domain", default="gmail.com", help="Email domain (gmail.com, outlook.com, etc.)")
    parser.add_argument("--password", default="", help="Fixed password (random if empty)")
    args = parser.parse_args()

    # Ensure smsaccount.txt exists
    SMSACCOUNT_FILE.touch(exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30, limits=CONNECTION_LIMITS) as client:
        for i in range(args.count):
            local = "".join(random.choice(string.ascii_lowercase) for _ in range(8)) + str(random.randint(1000, 99999))
            email = f"{local}@{args.domain}"
            password = args.password or email

            print(f"\n{'='*50}")
            print(f"Account {i + 1}/{args.count}: {email}")
            print(f"{'='*50}")

            try:
                result = await smailpro_create_email(email, args.api_key, expiry_minutes=60)
                print(f"SmailPro create: {result}")
            except Exception as exc:
                print(f"SmailPro create error: {exception_text(exc)}")
                continue

            success = await register_account(email, password, args.api_key, client)
            if success:
                with open(SMSACCOUNT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{email}|{password}\n")
                print(f"Saved to {SMSACCOUNT_FILE}")
            else:
                with open(FAILED_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{email}|{password}|registration_failed\n")
                print(f"Saved to {FAILED_FILE}")

            await asyncio.sleep(2)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
