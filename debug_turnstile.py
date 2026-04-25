"""Debug Turnstile: thử mọi phương pháp cho đến khi giải được"""
import json
import asyncio
import random
import httpx
from playwright.async_api import async_playwright, Page

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

GEMLOGIN_API = config.get("gemloginApi", "http://localhost:1010")
REGISTER_URL = config.get("elleRegisterUrl", "https://events.elle.vn/register?returnTo=%2Felle-beauty-awards-2026")


async def is_solved(page):
    try:
        token = await page.evaluate("""() => {
            const el = document.querySelector('[name="cf-turnstile-response"]');
            return el ? el.value : null;
        }""")
        return bool(token and len(token) > 10)
    except:
        return False


async def dump_state(page):
    """In trạng thái Turnstile hiện tại"""
    try:
        info = await page.evaluate("""() => {
            const cf = document.querySelector('[name="cf-turnstile-response"]');
            const sk = document.querySelector('[data-sitekey]');
            return {
                cfExists: !!cf,
                tokenLen: cf ? cf.value.length : 0,
                hasTurnstileObj: !!window.turnstile,
                sitekey: sk ? sk.getAttribute('data-sitekey') : null,
                windowFrames: window.frames.length,
            };
        }""")
        print(f"  State: token={info['tokenLen']}chars, turnstileObj={info['hasTurnstileObj']}, sitekey={info['sitekey']}, windowFrames={info['windowFrames']}")

        # CF frame info
        for i, frame in enumerate(page.frames):
            if "challenges.cloudflare" in frame.url or "turnstile" in frame.url:
                try:
                    fe = await frame.frame_element()
                    box = await fe.bounding_box()
                    html_len = await frame.evaluate("document.documentElement.outerHTML.length")
                    inner = await frame.evaluate("document.body.innerHTML.substring(0, 500)")
                    print(f"  CF frame[{i}]: box={box}, htmlLen={html_len}")
                    print(f"  CF body: {inner[:300]}")
                except Exception as e:
                    print(f"  CF frame[{i}] lỗi: {e}")
    except Exception as e:
        print(f"  dump lỗi: {e}")


async def try_method(page, name, fn):
    """Chạy 1 phương pháp, return True nếu giải được"""
    print(f"\n--- Thử: {name} ---")
    try:
        await fn()
    except Exception as e:
        print(f"  Lỗi: {e}")
    # Chờ token
    for w in range(15):
        if await is_solved(page):
            print(f"  ✅ THÀNH CÔNG bằng [{name}] sau {w}s!")
            return True
        await asyncio.sleep(1)
    print(f"  ❌ Không giải được")
    return False


async def main():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{GEMLOGIN_API}/api/profiles", timeout=10)
        data = res.json()
        profiles = data if isinstance(data, list) else data.get("data", data.get("profiles", []))
        pid = str(profiles[0].get("id") or profiles[0].get("profile_id") or profiles[0])

        # Đóng trước nếu đang chạy
        await client.get(f"{GEMLOGIN_API}/api/profiles/close/{pid}", timeout=10)
        await asyncio.sleep(3)

        start_res = await client.get(f"{GEMLOGIN_API}/api/profiles/start/{pid}", timeout=60)
        sdata = start_res.json()
        addr = sdata.get("remote_debugging_address") or sdata.get("data", {}).get("remote_debugging_address") or ""
        if not addr:
            print(f"Response: {start_res.text[:300]}")
            print("Không tìm remote_debugging_address!")
            return

        ws_res = await client.get(f"http://{addr}/json/version", timeout=10)
        ws_url = ws_res.json().get("webSocketDebuggerUrl")
        print(f"Profile {pid}, ws: {ws_url[:60]}...")

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws_url)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print(f"Mở {REGISTER_URL}...")
        await page.goto(REGISTER_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        print("\n===== TRẠNG THÁI BAN ĐẦU =====")
        await dump_state(page)

        # ============ TEST CLICK CF FRAME — 5 VÒNG ============
        success = 0
        fail = 0
        for round_num in range(1, 6):
            print(f"\n===== VÒNG {round_num}/5 =====")

            if round_num > 1:
                print("  Reload trang...")
                await page.reload(wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)

            await dump_state(page)

            if await is_solved(page):
                print("  Token đã có sẵn!")
                success += 1
                continue

            # Click CF frame
            solved = False
            for attempt in range(1, 4):
                for frame in page.frames:
                    if "challenges.cloudflare" in frame.url or "turnstile" in frame.url:
                        try:
                            fe = await frame.frame_element()
                            await fe.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
                            await asyncio.sleep(0.5)
                            box = await fe.bounding_box()
                            print(f"  [{attempt}] CF frame box: x={int(box['x'])},y={int(box['y'])} {int(box['width'])}x{int(box['height'])}")
                            if box and box["y"] > 0:
                                cx = box["x"] + box["width"] / 2
                                cy = box["y"] + box["height"] / 2
                                print(f"  [{attempt}] Click center ({int(cx)}, {int(cy)})")
                                await page.mouse.move(cx, cy, steps=10)
                                await asyncio.sleep(0.3)
                                await page.mouse.click(cx, cy)
                        except Exception as e:
                            print(f"  [{attempt}] Lỗi: {e}")
                        break

                # Chờ token
                for w in range(8):
                    if await is_solved(page):
                        solved = True
                        break
                    await asyncio.sleep(1)
                if solved:
                    break

            if solved:
                print(f"  ✅ VÒNG {round_num}: THÀNH CÔNG!")
                success += 1
            else:
                print(f"  ❌ VÒNG {round_num}: THẤT BẠI")
                fail += 1

        print(f"\n\n📊 KẾT QUẢ: {success}/5 thành công, {fail}/5 thất bại")

asyncio.run(main())
