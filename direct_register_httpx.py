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

account_lock = asyncio.Lock()
CONNECTION_LIMITS = httpx.Limits(max_keepalive_connections=200, max_connections=500)


try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}


DEFAULT_URL = config.get("elleNewRegisterUrl", "https://www.elle.vn/dang-ky/")
DENIED_HOSTS = set()
KIOT_KEYS: list[str] = config.get("kiotProxyKeys", [])
KIOT_REGION = config.get("kiotRegion", "random")
DEFAULT_ACCOUNT_FILE = config.get("httpxAccountFile", "accounts_https.txt")
DEFAULT_CREATE_COUNT = int(config.get("httpxCreateCount", 1))
RESULTS_FILE = config.get("httpxResultsFile", "results_https.txt")
FAILED_FILE = config.get("httpxFailedFile", "failed_https.txt")
DEBUG_DIR = Path(config.get("httpxDebugDir", "debug_httpx"))
DEFAULT_EMAIL_DOMAIN = config.get("emailDomain", "").strip()
VERBOSE = False


def log_verbose(message: str) -> None:
    if VERBOSE:
        print(message)


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


def random_email(domain: str = "example.test") -> str:
    local = "".join(random.choice(string.ascii_lowercase) for _ in range(10))
    return f"{local}{random.randint(10000, 99999)}@{domain}"


def parse_account_line(line: str, account_file: str) -> tuple[str, str, str] | None:
    parts = [part.strip() for part in line.strip().split("|")]
    email = parts[0] if parts else ""
    if not email:
        return None
    password = parts[1] if len(parts) > 1 and parts[1] else email
    return email, password, account_file


async def read_next_account(account_file: str) -> tuple[str, str, str] | None:
    async with account_lock:
        path = Path(account_file)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                account = parse_account_line(line, account_file)
                if account:
                    return account
    return None


async def read_all_accounts(account_file: str) -> list[tuple[str, str, str]]:
    async with account_lock:
        path = Path(account_file)
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        accounts: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for line in lines:
            account = parse_account_line(line, account_file)
            if account and account[0] not in seen:
                accounts.append(account)
                seen.add(account[0])
        return accounts


def random_email_local(used: set[str]) -> str:
    for _ in range(1000):
        first = "".join(random.choice(string.ascii_lowercase) for _ in range(random.randint(5, 8)))
        second = "".join(random.choice(string.ascii_lowercase) for _ in range(random.randint(4, 7)))
        local = f"{first}{second}{random.randint(10, 999999)}"
        if local not in used:
            used.add(local)
            return local
    raise RuntimeError("Khong tao duoc email local random khong trung")


async def get_email_domains(proxy_server: str | None, user_agent: str) -> list[str]:
    async with httpx.AsyncClient(follow_redirects=True, proxy=proxy_server, timeout=30) as client:
        for attempt in range(5):
            try:
                res = await client.get(
                    "https://generator.email/",
                    headers={"user-agent": user_agent, "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"},
                )
                soup = BeautifulSoup(res.text, "html.parser")
                domains = [p.get_text(strip=True) for p in soup.select(".e7m.tt-suggestions div > p")]
                domains = [domain for domain in domains if domain and "." in domain]
                if domains:
                    return domains
                print(f"Khong thay domain generator.email lan {attempt + 1}/5")
            except Exception as exc:
                print(f"Loi lay domain generator.email lan {attempt + 1}/5: {exc}")
            await asyncio.sleep(2)
    return []


async def create_accounts_file_if_empty(
    account_file: str,
    count: int,
    proxy_server: str | None,
    user_agent: str,
    email_domain: str = "",
) -> None:
    if await read_next_account(account_file):
        return

    fixed_domain = email_domain.strip()
    domains = [fixed_domain] if fixed_domain else await get_email_domains(proxy_server, user_agent)
    if not domains:
        raise SystemExit(f"{account_file} rong va khong lay duoc domain generator.email de tao mail.")

    count = max(1, count)
    used: set[str] = set()
    path = Path(account_file)
    with path.open("a", encoding="utf-8") as f:
        for _ in range(count):
            email = f"{random_email_local(used)}@{random.choice(domains)}"
            f.write(f"{email}|{email}\n")
    print(f"Da tao {count} email va luu vao {account_file}")


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


def random_cccd(birth: date | None = None) -> str:
    birth = birth or random_birth_date()
    gender = random.choice(["male", "female"])
    return "".join([
        random.choice(PROVINCE_CODES),
        gender_century_digit(birth.year, gender),
        f"{birth.year % 100:02d}",
        f"{random.randint(0, 999999):06d}",
    ])


def is_allowed_url(url: str, allowed_hosts: set[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host in DENIED_HOSTS:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".test") or host.endswith(".local") or host.endswith(".localhost"):
        return True
    if host in allowed_hosts:
        return True
    return False


def absolute_url(base_url: str, maybe_url: str | None) -> str:
    return str(httpx.URL(base_url).join(maybe_url or base_url))


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
                print(f"KiotProxy {label}: {proxy['raw']} ({console_safe(proxy['location'])})")
                return proxy
            print(f"KiotProxy {label} loi: {console_safe(data.get('message') or data.get('error') or data)}")
        except Exception as exc:
            print(f"KiotProxy {label} exception: {exception_text(exc)}")
    return None


async def get_confirmation_link(email: str, max_retries: int = 30, proxy_server: str | None = None) -> str | None:
    local_part, domain = email.split("@", 1)
    inbox_url = f"https://generator.email/{local_part}@{domain}"
    safe_email = "".join(ch if ch.isalnum() else "_" for ch in email)

    async with httpx.AsyncClient(follow_redirects=True, proxy=proxy_server, timeout=60) as client:
        for i in range(max_retries):
            try:
                res = await client.get(
                    inbox_url,
                    headers={
                        "cookie": f"surl={domain}%2F{local_part}",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                        "referer": f"https://generator.email/",
                    },
                )
                if res.status_code != 200:
                    log_verbose(f"Doc inbox {inbox_url} -> {res.status_code}")
                    await asyncio.sleep(5)
                    continue
                confirm_link = find_confirmation_link(res.text, inbox_url)
                if confirm_link:
                    return confirm_link
                if i in {0, max_retries - 1}:
                    if VERBOSE:
                        save_inbox_debug(safe_email, res.text)
            except Exception as exc:
                log_verbose(f"Chua doc duoc mail lan {i + 1}: {exc}")
            await asyncio.sleep(5)
    return None


def normalize_href(href: str, base_url: str) -> str:
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    return urljoin(base_url, href)


def confirm_link_score(a_tag, href: str) -> int:
    text = remove_accents(a_tag.get_text(" ", strip=True)).lower()
    href_lower = remove_accents(href).lower()
    combined = f"{text} {href_lower}"
    host = (urlparse(href).hostname or "").lower()

    reject_markers = [
        "unsubscribe",
        "preferences",
        "view-in-browser",
        "view_email",
        "facebook.com",
        "instagram.com",
        "youtube.com",
        "tiktok.com",
        "generator.email",
    ]
    if any(marker in combined or marker in host for marker in reject_markers):
        return -100

    score = 0
    for marker in ["xac nhan", "confirm", "verify", "verification", "activate", "activation", "kich hoat"]:
        if marker in text:
            score += 60
        if marker in href_lower:
            score += 25
    for marker in [
        "baseapi.elle.vn/auth/email-confirmation",
        "email-confirmation",
        "confirmation=",
        "r.wwwdigitalnetwork.com/tr/cl/",
        "wwwdigitalnetwork.com/tr/cl/",
        "elle.vn",
        "events.elle.vn",
    ]:
        if marker in href_lower:
            score += 35
    if "token" in href_lower or "key=" in href_lower or "code=" in href_lower:
        score += 20
    if a_tag.find_parent("td", attrs={"bgcolor": "#414141"}) or "#414141" in (a_tag.get("style") or ""):
        score += 15
    return score


def find_confirmation_link(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str, str]] = []
    for a_tag in soup.find_all("a", href=True):
        href = normalize_href(a_tag["href"], base_url)
        score = confirm_link_score(a_tag, href)
        if score > 0:
            text = a_tag.get_text(" ", strip=True)
            candidates.append((score, href, text))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    for score_item, href_item, text_item in candidates[:3]:
        log_verbose(f"Ung vien link xac nhan score={score_item}, text='{text_item[:60]}', href={href_item}")
    score, href, text = candidates[0]
    log_verbose(f"Chon link xac nhan score={score}, text='{text[:80]}', href={href}")
    return href


def save_inbox_debug(safe_email: str, html: str) -> None:
    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        debug_path = DEBUG_DIR / f"inbox_{safe_email}.html"
        debug_path.write_text(html, encoding="utf-8", errors="replace")
        log_verbose(f"Da luu HTML inbox debug: {debug_path}")
    except Exception as exc:
        log_verbose(f"Khong luu duoc HTML inbox debug: {exc}")


def save_submit_debug(email: str, html: str) -> None:
    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        safe_email = "".join(ch if ch.isalnum() else "_" for ch in email)
        debug_path = DEBUG_DIR / f"submit_{safe_email}.html"
        debug_path.write_text(html, encoding="utf-8", errors="replace")
        log_verbose(f"Da luu HTML submit debug: {debug_path}")
    except Exception as exc:
        log_verbose(f"Khong luu duoc HTML submit debug: {exc}")


def response_returned_register_form(response: httpx.Response) -> bool:
    soup = BeautifulSoup(response.text, "html.parser")
    form = find_register_form(soup)
    if not form:
        return False

    fields = {tag.get("name") for tag in form.find_all(["input", "select", "textarea"]) if tag.get("name")}
    endpoint_hint = " ".join(
        value for value in [form.get("hx-post"), form.get("action"), form.get("data-loading-path")] if value
    ).lower()
    return {"email", "password"} <= fields and (
        "user_signup" in endpoint_hint or "identificationID" in fields or "identificationDate" in fields
    )


def returned_form_diagnostics(response: httpx.Response) -> str:
    soup = BeautifulSoup(response.text, "html.parser")
    form = find_register_form(soup)
    if not form:
        return ""

    important_fields = ["username", "identificationID", "identificationDate", "email", "phone", "password"]
    empty_fields: list[str] = []
    present_fields: set[str] = set()
    for tag in form.find_all(["input", "select", "textarea"]):
        name = tag.get("name")
        if not name:
            continue
        present_fields.add(name)
        if name in important_fields and not field_value(tag):
            empty_fields.append(name)

    details: list[str] = []
    if empty_fields:
        details.append("field rong sau submit: " + ", ".join(dict.fromkeys(empty_fields)))
    missing_fields = [name for name in important_fields if name not in present_fields]
    if missing_fields:
        details.append("field khong thay trong form tra ve: " + ", ".join(missing_fields))
    return "; ".join(details)


def registration_may_have_sent_email(response: httpx.Response, text: str) -> tuple[bool, str]:
    normalized_html = remove_accents(response.text).lower()
    normalized_text = remove_accents(text).lower()

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    if "login-success" in normalized_html:
        return True, "co login-success"
    success_markers = [
        "kiem tra email",
        "xac thuc tai khoan",
        "xac nhan email",
        "dang ky thanh cong",
        "vui long kiem tra",
    ]
    for marker in success_markers:
        if marker in normalized_text:
            return True, f"co thong bao: {marker}"

    error_markers = [
        "email da ton tai",
        "email is already taken",
        "username da ton tai",
        "khong hop le",
        "invalid",
        "truong nay la bat buoc",
        "vui long nhap",
        "vui long dien",
        "dang ky that bai",
    ]
    for marker in error_markers:
        if marker in normalized_text:
            return False, f"co dau hieu loi: {marker}"

    if response_returned_register_form(response):
        details = returned_form_diagnostics(response)
        reason = "server tra lai form dang ky, chua co dau hieu gui mail"
        if details:
            reason = f"{reason}; {details}"
        return False, reason

    return True, "HTTP 200 khong co loi ro rang, tiep tuc kiem tra inbox"


def confirmation_succeeded(response: httpx.Response) -> tuple[bool, str]:
    status_ok = 200 <= response.status_code < 400
    final_url = str(response.url)
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        text = remove_accents(response.text).lower()
    else:
        text = remove_accents(
            " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
        ).lower()
    preview = response.text[:500].replace("\n", " ").replace("\r", " ")
    error_markers = [
        "error",
        "invalid",
        "expired",
        "not found",
        "khong hop le",
        "het han",
        "loi",
        "that bai",
    ]
    if not status_ok:
        return False, f"HTTP {response.status_code}, final_url={final_url}, body={preview}"
    for marker in error_markers:
        if marker in text:
            return False, f"Trang xac nhan co dau hieu loi: {marker}, final_url={final_url}, body={preview}"
    return True, f"HTTP {response.status_code}, final_url={final_url}"


def form_payload(form, email: str, password: str) -> dict[str, str]:
    payload: dict[str, str] = {}
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
        payload[name] = field_value(tag) or ("on" if input_type in {"checkbox", "radio"} else "")

    birth = random_birth_date()
    identification_date = random_identification_date(birth)
    generated = {
        "username": random_vietnamese_name(),
        "identificationID": random_cccd(birth),
        "identificationDate": identification_date.isoformat(),
        "email": email,
        "phone": random_phone(),
        "password": password,
        "acceptTerm": "on",
        "acceptPrivacy": "on",
    }
    for key, value in generated.items():
        payload[key] = value
    return payload


def submit_endpoint(page_url: str, form) -> tuple[str, str]:
    hx_post = form.get("hx-post")
    if hx_post:
        return "POST", absolute_url(page_url, hx_post)
    method = (form.get("method") or "GET").upper()
    action = absolute_url(page_url, form.get("action"))
    return method, action


async def remove_account_from_file(email: str, account_file: str) -> None:
    async with account_lock:
        try:
            with open(account_file, "r", encoding="utf-8") as f:
                remaining = []
                for line in f:
                    stripped = line.strip()
                    if stripped and stripped.split("|")[0].strip() != email:
                        remaining.append(stripped)
            with open(account_file, "w", encoding="utf-8") as f:
                f.write("\n".join(remaining) + "\n" if remaining else "")
        except FileNotFoundError:
            pass


async def record_failed_account(email: str, password: str, reason: str) -> None:
    clean_reason = reason.replace("\n", " ").replace("\r", " ")[:500]
    async with account_lock:
        with open(FAILED_FILE, "a", encoding="utf-8") as f:
            f.write(f"{email}|{password}|{clean_reason}\n")


def is_final_confirmation_failure(reason: str) -> bool:
    normalized = remove_accents(reason).lower()
    final_markers = [
        "token.invalid",
        "token.expired",
        "confirmation",
        "expired",
    ]
    return any(marker in normalized for marker in final_markers)


async def process_single_account(
    email: str,
    password: str,
    account_file: str | None,
    args: argparse.Namespace,
    proxy_server: str | None,
    allowed_hosts: set[str],
    worker_id: int,
) -> None:
    """Xu ly 1 account trong 1 worker."""
    auto_email = account_file is not None
    source_account_file = account_file

    async with httpx.AsyncClient(follow_redirects=True, timeout=30, proxy=proxy_server, limits=CONNECTION_LIMITS) as client:
        try:
            page = await client.get(args.url, headers={"user-agent": args.user_agent})
            log_verbose(f"[W{worker_id}] GET {page.url} -> {page.status_code}")

            soup = BeautifulSoup(page.text, "html.parser")
            form = find_register_form(soup)
            if not form:
                print(f"[W{worker_id}] FAIL no register form")
                return

            method, endpoint = submit_endpoint(str(page.url), form)
            if not is_allowed_url(endpoint, allowed_hosts):
                print(f"[W{worker_id}] FAIL blocked endpoint")
                log_verbose(f"[W{worker_id}] Blocked submit endpoint: {endpoint}")
                return

            payload = form_payload(form, email, password)
            log_verbose(f"[W{worker_id}] Payload: {payload}")
            headers = {
                "user-agent": args.user_agent,
                "referer": str(page.url),
                "origin": f"{httpx.URL(str(page.url)).scheme}://{httpx.URL(str(page.url)).host}",
                "content-type": "application/x-www-form-urlencoded",
                "hx-request": "true",
                "hx-current-url": str(page.url),
            }

            print(f"[W{worker_id}] account {email}")
            if source_account_file:
                log_verbose(f"[W{worker_id}] Account file: {source_account_file}")

            if not args.submit:
                print(f"[W{worker_id}] DRY-RUN")
                return

            if method == "POST":
                response = await client.post(endpoint, data=payload, headers=headers)
            else:
                response = await client.get(endpoint, params=payload, headers=headers)

            log_verbose(f"[W{worker_id}] {method} {response.url} -> {response.status_code}")
            log_verbose(f"[W{worker_id}] Response body preview: {response.text[:500]}")
            text = " ".join(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True).split())
            log_verbose(f"[W{worker_id}] {text[:500]}")

            should_check_mail, submit_reason = registration_may_have_sent_email(response, text)
            if should_check_mail:
                if "login-success" not in response.text.lower():
                    log_verbose(f"[W{worker_id}] Khong thay login-success ({submit_reason}), van kiem tra inbox.")
                    if VERBOSE:
                        save_submit_debug(email, response.text)
                if args.skip_confirm:
                    log_verbose(f"[W{worker_id}] --skip-confirm da bi vo hieu hoa: phai xac nhan mail moi tinh thanh cong.")
                print(f"[W{worker_id}] submit OK, waiting mail")
                confirm_link = await get_confirmation_link(email, proxy_server=proxy_server)
                if confirm_link:
                    print(f"[W{worker_id}] mail OK")
                    log_verbose(f"[W{worker_id}] Tim thay link xac nhan: {confirm_link}")
                    try:
                        log_verbose(f"[W{worker_id}] Dang mo link xac nhan bang cung session dang ky...")
                        confirm_res = await client.get(
                            confirm_link,
                            headers={
                                "user-agent": args.user_agent,
                                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                                "referer": f"https://generator.email/{email}",
                            },
                            timeout=30,
                        )
                        ok, reason = confirmation_succeeded(confirm_res)
                        log_verbose(f"[W{worker_id}] Xac nhan: GET {confirm_link} -> {reason}")
                    except Exception as exc:
                        print(f"[W{worker_id}] confirm ERROR {exception_text(exc)}")
                        ok = False
                        reason = exception_text(exc)
                    if ok:
                        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                            f.write(f"{email}\n")
                        print(f"[W{worker_id}] confirm OK, saved {RESULTS_FILE}")
                        if auto_email and source_account_file:
                            await remove_account_from_file(email, source_account_file)
                            log_verbose(f"[W{worker_id}] Da bo {email} khoi {source_account_file}")
                    else:
                        print(f"[W{worker_id}] confirm FAIL")
                        log_verbose(f"[W{worker_id}] Khong luu ket qua vi link xac nhan chua duoc xac minh thanh cong: {reason}")
                        if auto_email and source_account_file and is_final_confirmation_failure(reason):
                            await record_failed_account(email, password, reason)
                            await remove_account_from_file(email, source_account_file)
                            print(f"[W{worker_id}] moved to {FAILED_FILE}")
                else:
                    print(f"[W{worker_id}] mail FAIL no confirm link")
                    if auto_email and source_account_file:
                        await record_failed_account(email, password, "mail FAIL no confirm link")
                        await remove_account_from_file(email, source_account_file)
                        print(f"[W{worker_id}] moved to {FAILED_FILE}")
            else:
                print(f"[W{worker_id}] submit FAIL: {submit_reason}")
                if VERBOSE:
                    save_submit_debug(email, response.text)
                if auto_email and source_account_file:
                    await record_failed_account(email, password, f"submit FAIL: {submit_reason}")
                    await remove_account_from_file(email, source_account_file)
                    print(f"[W{worker_id}] moved to {FAILED_FILE}")
        except Exception as exc:
            print(f"[W{worker_id}] ERROR {email}: {exception_text(exc)}")


async def direct_register(args: argparse.Namespace) -> None:
    allowed_hosts = {host.lower() for host in args.allow_host}
    target_host = (urlparse(args.url).hostname or "").lower()
    if target_host:
        allowed_hosts.add(target_host)
    if not is_allowed_url(args.url, allowed_hosts):
        raise SystemExit(f"Blocked target URL: {args.url}")

    # No proxy - always use direct connection
    proxy_server = None

    # Single account mode
    if args.email:
        await process_single_account(
            args.email,
            args.password or args.email,
            None,
            args,
            proxy_server,
            allowed_hosts,
            0,
        )
        return

    # Multi-account mode
    await create_accounts_file_if_empty(
        args.accounts_file,
        args.create_count,
        proxy_server,
        args.user_agent,
        args.email_domain,
    )

    accounts = await read_all_accounts(args.accounts_file)
    if not accounts:
        print(f"Khong co email trong {args.accounts_file} sau khi tao account.")
        return

    max_accounts = max(1, args.max_accounts)
    selected_accounts = accounts[:max_accounts]
    queue: asyncio.Queue[tuple[str, str, str]] = asyncio.Queue()
    for account in selected_accounts:
        queue.put_nowait(account)

    processed_count = 0

    async def worker_wrapper(worker_id: int):
        nonlocal processed_count
        while True:
            try:
                email, file_password, account_file = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            password = args.password or file_password or email
            await process_single_account(email, password, account_file, args, proxy_server, allowed_hosts, worker_id)
            processed_count += 1
            queue.task_done()

    tasks = []
    worker_count = max(1, min(args.workers, len(selected_accounts)))
    for i in range(worker_count):
        tasks.append(worker_wrapper(i))

    await asyncio.gather(*tasks)
    print(f"Da xu ly xong {processed_count} account(s).")


def main() -> None:
    global VERBOSE
    parser = argparse.ArgumentParser(description="Direct httpx register submit for elle.vn and production targets.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--email")
    parser.add_argument("--email-domain", default=DEFAULT_EMAIL_DOMAIN, help="Domain email co dinh khi tu tao account; bo trong de lay tu generator.email.")
    parser.add_argument("--password")
    parser.add_argument("--accounts-file", default=DEFAULT_ACCOUNT_FILE, help="File account dang email|password.")
    parser.add_argument("--create-count", type=int, default=DEFAULT_CREATE_COUNT, help="So email tu tao khi accounts file dang rong.")
    parser.add_argument("--max-accounts", type=int, default=999999, help="So account xu ly trong lan chay nay (mac dinh 999999 = all).")
    parser.add_argument("--workers", type=int, default=1, help="So luong worker song song (mac dinh 1).")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--skip-confirm", action="store_true", help="Ignored: results are only saved after email confirmation.")
    parser.add_argument("--allow-host", action="append", default=[], help="Exact staging host allowed for submit, e.g. staging.example.com")
    parser.add_argument("--user-agent", default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    parser.add_argument("--verbose", action="store_true", help="In log chi tiet de debug.")
    args = parser.parse_args()
    VERBOSE = args.verbose
    asyncio.run(direct_register(args))


if __name__ == "__main__":
    main()
