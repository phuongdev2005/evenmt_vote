import argparse
import json
import random
import string
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}


REGISTER_URL = config.get(
    "elleNewRegisterUrl",
    config.get("elleRegisterUrl", "https://www.elle.vn/dang-ky/"),
)


def random_text(length: int = 10) -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


def random_phone() -> str:
    return random.choice(["032", "033", "034", "035", "036", "037", "038", "039", "090", "091", "092", "093"]) + f"{random.randint(0, 9999999):07d}"


def random_birth_date() -> str:
    year = random.randint(1988, 2007)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return date(year, month, day).isoformat()


def random_cccd() -> str:
    province = random.choice(["001", "004", "008", "031", "038", "052", "079"])
    year = random.randint(1988, 2007)
    gender_century = "0" if year < 2000 else "2"
    return f"{province}{gender_century}{year % 100:02d}{random.randint(0, 999999):06d}"


def make_email() -> str:
    local = f"{random_text(8)}{random.randint(1000, 9999)}"
    return f"{local}@example.test"


def absolute_url(base_url: str, action: str) -> str:
    return str(httpx.URL(base_url).join(action or base_url))


def is_local_target(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".test") or host.endswith(".local")


def find_register_form(soup: BeautifulSoup):
    forms = soup.find_all("form")
    for form in forms:
        names = {tag.get("name") for tag in form.find_all(["input", "select", "textarea"]) if tag.get("name")}
        if {"username", "email", "password"} & names:
            return form
    return forms[0] if forms else None


def build_payload(form, email: str, password: str) -> dict[str, str]:
    payload: dict[str, str] = {}

    for tag in form.find_all(["input", "select", "textarea"]):
        name = tag.get("name")
        if not name:
            continue

        tag_name = tag.name.lower()
        input_type = (tag.get("type") or "").lower()
        value = tag.get("value") or ""

        if tag_name == "select":
            option = tag.find("option", selected=True) or tag.find("option")
            value = option.get("value", "") if option else ""
        elif input_type in {"checkbox", "radio"}:
            if not tag.has_attr("checked") and name not in {"acceptTerm", "acceptPrivacy"}:
                continue
            value = value or "on"

        payload[name] = value

    overrides = {
        "username": f"NGUYEN VAN {random_text(5).upper()}",
        "identificationID": random_cccd(),
        "identificationDate": random_birth_date(),
        "email": email,
        "phone": random_phone(),
        "password": password,
        "acceptTerm": "on",
        "acceptPrivacy": "on",
    }
    for key, value in overrides.items():
        if key in payload or key in {"username", "identificationID", "identificationDate", "email", "phone", "password"}:
            payload[key] = value

    return payload


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and inspect a registration form without opening a browser.")
    parser.add_argument("--url", default=REGISTER_URL)
    parser.add_argument("--email", default=make_email())
    parser.add_argument("--password")
    parser.add_argument("--submit", action="store_true", help="Only allowed for localhost/.test/.local URLs.")
    args = parser.parse_args()

    password = args.password or args.email

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        res = await client.get(args.url, headers={"user-agent": "Mozilla/5.0"})
        print(f"GET {res.url} -> {res.status_code}")

        soup = BeautifulSoup(res.text, "html.parser")
        form = find_register_form(soup)
        if not form:
            print("Khong tim thay form trong HTML.")
            return

        method = (form.get("method") or "GET").upper()
        action = absolute_url(str(res.url), form.get("action") or str(res.url))
        payload = build_payload(form, args.email, password)

        print(f"Form method: {method}")
        print(f"Form action: {action}")
        print("Fields:")
        for key in sorted(payload):
            shown_value = payload[key]
            if key.lower() in {"password", "pass"}:
                shown_value = "<password>"
            print(f"  {key} = {shown_value}")

        if not args.submit:
            print("Dry-run only. Khong submit. Dung --submit chi voi URL test/local cua ban.")
            return

        if not is_local_target(action):
            print("Khong submit: script nay chi cho phep submit vao localhost/.test/.local.")
            return

        if method == "POST":
            submit_res = await client.post(action, data=payload, headers={"referer": str(res.url), "user-agent": "Mozilla/5.0"})
        else:
            submit_res = await client.get(action, params=payload, headers={"referer": str(res.url), "user-agent": "Mozilla/5.0"})

        print(f"{method} {submit_res.url} -> {submit_res.status_code}")
        text = " ".join(BeautifulSoup(submit_res.text, "html.parser").get_text(" ", strip=True).split())
        print(text[:1000])


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
