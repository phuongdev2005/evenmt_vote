"""
Kết nối với GemLogin API - Anti-detect browser automation
"""
import json
import asyncio
import httpx
import os
from typing import Optional
from colorama import Fore, Style


# Hỗ trợ biến môi trường cho Docker (host.docker.internal)
GEMLOGIN_API = os.getenv("GEMLOGIN_API_URL", "http://localhost:1010")


async def create_profile(client: httpx.AsyncClient, api_url: str = GEMLOGIN_API) -> Optional[str]:
    """Tạo profile GemLogin mới, trả về profile_id"""
    try:
        res = await client.post(f"{api_url}/api/profiles/create", json={}, timeout=30)
        data = res.json()
        profile_id = data.get("id") or data.get("data", {}).get("id") or data.get("profile_id")
        if profile_id:
            return str(profile_id)
        print(f"{Fore.RED}❌ GemLogin create lỗi: {data}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ GemLogin create exception: {e}{Style.RESET_ALL}")
    return None


async def start_profile(client: httpx.AsyncClient, profile_id: str, api_url: str = GEMLOGIN_API, window_position: tuple[int, int] | None = None, window_size: tuple[int, int] | None = None) -> Optional[str]:
    """Start profile, lấy WebSocket URL để kết nối Playwright"""
    try:
        # Build query parameters for window position
        params = {}
        if window_position:
            params['windowPositionX'] = window_position[0]
            params['windowPositionY'] = window_position[1]
            # Default size or custom size
            if window_size:
                params['windowWidth'] = window_size[0]
                params['windowHeight'] = window_size[1]
            else:
                params['windowWidth'] = 800
                params['windowHeight'] = 600
        
        res = await client.get(f"{api_url}/api/profiles/start/{profile_id}", params=params, timeout=60)
        data = res.json()
        
        if data.get("success") is False:
            message = data.get("message") or data.get("error") or data
            print(f"{Fore.YELLOW}⚠️ GemLogin start profile {profile_id}: {message}{Style.RESET_ALL}")
            return None

        # Lấy wsUrl từ response
        ws_url = (
            data.get("wsUrl")
            or data.get("data", {}).get("wsUrl")
            or data.get("webSocketDebuggerUrl")
            or data.get("data", {}).get("webSocketDebuggerUrl")
        )
        
        if ws_url:
            return ws_url

        # Nếu không có wsUrl, query từ debug port
        remote_address = (
            data.get("remote_debugging_address")
            or data.get("data", {}).get("remote_debugging_address")
        )
        
        if remote_address:
            if not remote_address.startswith("http"):
                remote_address = f"http://{remote_address}"
            
            ver_res = await client.get(f"{remote_address}/json/version", timeout=10)
            ver_data = ver_res.json()
            ws_url = ver_data.get("webSocketDebuggerUrl")
            if ws_url:
                return ws_url
            
            print(f"{Fore.YELLOW}⚠️ /json/version response: {json.dumps(ver_data, ensure_ascii=False)[:300]}{Style.RESET_ALL}")
        
        print(f"{Fore.YELLOW}⚠️ GemLogin start response: {json.dumps(data, ensure_ascii=False)[:300]}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ GemLogin start exception: {type(e).__name__}: {e}{Style.RESET_ALL}")
    return None


async def close_profile(client: httpx.AsyncClient, profile_id: str, api_url: str = GEMLOGIN_API):
    """Đóng browser profile"""
    try:
        await client.get(f"{api_url}/api/profiles/close/{profile_id}", timeout=15)
    except:
        pass


async def check_profile_status(client: httpx.AsyncClient, profile_id: str, api_url: str = GEMLOGIN_API) -> Optional[str]:
    """Kiểm tra trạng thái profile"""
    try:
        res = await client.post(f"{api_url}/api/profiles/check-status/{profile_id}", timeout=10)
        data = res.json()
        status = data.get("status") or data.get("data", {}).get("status")
        if status:
            return str(status)
    except:
        pass
    return None


async def get_profiles(client: httpx.AsyncClient, api_url: str = GEMLOGIN_API) -> list:
    """Lấy danh sách tất cả profiles"""
    try:
        res = await client.get(f"{api_url}/api/profiles", timeout=10)
        data = res.json()
        profiles = data if isinstance(data, list) else data.get("data", data.get("profiles", []))
        return profiles
    except Exception as e:
        print(f"{Fore.RED}❌ Lỗi lấy danh sách profiles: {e}{Style.RESET_ALL}")
        return []


async def delete_profile(client: httpx.AsyncClient, profile_id: str, api_url: str = GEMLOGIN_API) -> bool:
    """Xóa profile"""
    try:
        res = await client.delete(f"{api_url}/api/profiles/delete/{profile_id}", timeout=15)
        data = res.json()
        return data.get("success", False)
    except Exception as e:
        print(f"{Fore.RED}❌ Lỗi xóa profile {profile_id}: {e}{Style.RESET_ALL}")
        return False


async def wait_for_profile_close(client: httpx.AsyncClient, profile_id: str, timeout: int = 20, api_url: str = GEMLOGIN_API) -> bool:
    """Đợi profile đóng hoàn toàn"""
    for i in range(timeout):
        status = await check_profile_status(client, profile_id, api_url)
        if status and "close" in status.lower():
            return True
        await asyncio.sleep(1)
    return False
