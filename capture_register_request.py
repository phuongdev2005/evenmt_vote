import argparse
import asyncio
import json
import random
import string
import sys
from datetime import date

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Request, Response, async_playwright


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}


REGISTER_URL = config.get(
    "elleNewRegisterUrl",
    config.get("elleRegisterUrl", "https://www.elle.vn/dang-ky/"),
)
USERNAME_SELECTOR = 'input#username[name="username"]'
ACCOUNTS_FILE = "accounts.txt"
OUTPUT_FILE = "register_network_capture.json"


LAST_NAMES = ["NGUYEN", "TRAN", "LE", "PHAM", "HOANG", "VU", "VO", "DANG", "BUI", "DO"]
MIDDLE_NAMES = ["VAN", "THI", "MINH", "QUOC", "THANH", "ANH", "DUC", "GIA", "NHAT", "BAO"]
GIVEN_NAMES = ["AN", "BINH", "CHI", "DUNG", "GIANG", "HA", "HUNG", "KHANH", "LINH", "TRANG"]
PROVINCE_CODES = ["001", "004", "008", "031", "038", "040", "052", "079", "092", "096"]
PHONE_PREFIXES = ["032", "033", "034", "035", "036", "037", "038", "039", "090", "091", "092", "093", "096", "097", "098"]


def random_name() -> str:
    return f"{random.choice(LAST_NAMES)} {random.choice(MIDDLE_NAMES)} {random.choice(GIVEN_NAMES)}"


def random_birth_date() -> date:
    return date(random.randint(1988, 2007), random.randint(1, 12), random.randint(1, 28))


def random_cccd(birth: date) -> str:
    gender_century = "0" if birth.year < 2000 else "2"
    return f"{random.choice(PROVINCE_CODES)}{gender_century}{birth.year % 100:02d}{random.randint(0, 999999):06d}"


def random_phone() -> str:
    return random.choice(PHONE_PREFIXES) + f"{random.randint(0, 9999999):07d}"


def random_email() -> str:
    local = "".join(random.choice(string.ascii_lowercase) for _ in range(10)) + str(random.randint(1000, 9999))
    return f"{local}@example.test"


def read_next_account() -> tuple[str, str]:
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = [part.strip() for part in line.strip().split("|")]
                if parts and parts[0]:
                    return parts[0], parts[1] if len(parts) > 1 and parts[1] else parts[0]
    except FileNotFoundError:
        pass
    email = random_email()
    return email, email


async def get_email_domains() -> list[str]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        res = await client.get("https://generator.email/", headers={"user-agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        domains = []
        for p_tag in soup.select(".e7m.tt-suggestions div > p"):
            text = p_tag.get_text(strip=True)
            if text:
                domains.append(text)
        return domains


async def make_fresh_email() -> str:
    try:
        domains = await get_email_domains()
        domain = random.choice(domains) if domains else "vitaspherelife.com"
    except Exception as exc:
        print(f"Khong lay duoc domain generator.email, dung fallback: {exc}")
        domain = "vitaspherelife.com"
    local = "".join(random.choice(string.ascii_lowercase) for _ in range(12)) + str(random.randint(10000, 99999))
    return f"{local}@{domain}"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in {"cookie", "authorization"}:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


async def maybe_body(request: Request) -> str | None:
    try:
        data = request.post_data
        if data and len(data) > 5000:
            return data[:5000] + "...<truncated>"
        return data
    except Exception:
        return None


def interesting(url: str, method: str) -> bool:
    lower = url.lower()
    return "www.elle.vn/wp/wp-admin/admin-ajax.php" in lower or "www.elle.vn/dang-ky" in lower


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--use-accounts-file", action="store_true")
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args()

    if args.email:
        email = args.email
        password = args.password or email
    elif args.use_accounts_file:
        email, password = read_next_account()
        password = args.password or password or email
    else:
        email = await make_fresh_email()
        password = args.password or email

    birth = random_birth_date()
    form_data = {
        "name": random_name(),
        "cccd": random_cccd(birth),
        "birth_date": birth.isoformat(),
        "email": email,
        "password": password,
        "phone": random_phone(),
    }

    events: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        page = await browser.new_page()

        async def on_request(request: Request) -> None:
            if interesting(request.url, request.method):
                events.append(
                    {
                        "type": "request",
                        "method": request.method,
                        "url": request.url,
                        "resource_type": request.resource_type,
                        "headers": redact_headers(request.headers),
                        "post_data": await maybe_body(request),
                    }
                )

        async def on_response(response: Response) -> None:
            request = response.request
            if interesting(request.url, request.method):
                item = {
                    "type": "response",
                    "method": request.method,
                    "url": response.url,
                    "status": response.status,
                    "headers": redact_headers(response.headers),
                }
                content_type = response.headers.get("content-type", "")
                if "admin-ajax.php" in response.url and ("json" in content_type or "text" in content_type or "html" in content_type):
                    try:
                        text = await response.text()
                        item["body_preview"] = text[:8000]
                    except Exception as exc:
                        item["body_error"] = str(exc)
                events.append(item)

        page.on("request", on_request)
        page.on("response", on_response)

        await page.goto(REGISTER_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector(USERNAME_SELECTOR, timeout=30000)

        await page.fill(USERNAME_SELECTOR, form_data["name"])
        await page.fill('input#identificationID[name="identificationID"]', form_data["cccd"])
        await page.fill('input#identificationDate[name="identificationDate"]', form_data["birth_date"])
        await page.fill('input#email[name="email"]', form_data["email"])
        await page.fill('input[name="phone"]', form_data["phone"])
        await page.fill('input#password[name="password"]', form_data["password"])

        for selector in ['input[name="acceptTerm"]', 'input[name="acceptPrivacy"]']:
            checkboxes = page.locator(selector)
            for i in range(await checkboxes.count()):
                checkbox = checkboxes.nth(i)
                if not await checkbox.is_checked():
                    await checkbox.check()

        print(f"Da dien email: {email}")
        print("Dang bam submit de bat network request that...")

        submit_buttons = page.locator('button[type="submit"]')
        clicked = False
        for i in range(await submit_buttons.count()):
            button = submit_buttons.nth(i)
            try:
                if await button.is_visible(timeout=1000):
                    await button.scroll_into_view_if_needed(timeout=5000)
                    await button.click(timeout=10000)
                    clicked = True
                    break
            except Exception:
                pass

        if not clicked:
            await page.evaluate(
                """() => {
                    const button = Array.from(document.querySelectorAll('button[type="submit"]'))
                        .find((item) => item.offsetWidth > 0 && item.offsetHeight > 0);
                    if (!button) throw new Error('No visible submit button');
                    button.click();
                }"""
            )

        await page.wait_for_timeout(12000)
        success_text = ""
        try:
            success_text = " ".join((await page.locator(".login-success").first.inner_text(timeout=1000)).split())
        except Exception:
            pass

        output = {
            "register_url": REGISTER_URL,
            "form_data": {**form_data, "password": "<same as email>" if password == email else "<redacted>"},
            "success_text": success_text,
            "events": events,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"Da luu network capture vao {args.output}")
        if success_text:
            print(f"Trang bao: {success_text}")
        else:
            print("Khong thay .login-success trong 12 giay.")

        if args.keep_open:
            print("Nhan Enter de dong browser...")
            await asyncio.to_thread(sys.stdin.readline)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
