"""
Sắp xếp lại các cửa sổ GemLogin đang mở
"""
import ctypes
import ctypes.wintypes

SCREEN_W = 1536
SCREEN_H = 824  # 864 - 40px taskbar
COLS = 6
ROWS = 2
WIN_W = SCREEN_W // COLS  # 256
WIN_H = SCREEN_H // ROWS  # 412

# Lưới 6x2, 12 cửa sổ
WIN_POSITIONS = []
for i in range(12):
    col = i % COLS
    row = i // COLS
    x = col * WIN_W
    y = row * WIN_H
    w = (SCREEN_W - x) if col == COLS - 1 else WIN_W
    h = (SCREEN_H - y) if row == ROWS - 1 else WIN_H
    WIN_POSITIONS.append({"x": x, "y": y, "w": w, "h": h})

def arrange_gemlogin_windows():
    """Tìm tất cả cửa sổ Chrome/GemLogin và sắp xếp lên màn hình"""
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
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        if w < 200:
            return True
        title_lower = title.lower()
        if title_lower.startswith("gemlogin -"):
            return True
        if "gemlogin" in title_lower or "events.elle.vn" in title_lower:
            chrome_hwnds.append(hwnd)
        return True

    EnumWindows(WNDENUMPROC(enum_cb), 0)

    arranged = 0
    for i, hwnd in enumerate(chrome_hwnds[:len(WIN_POSITIONS)]):
        pos = WIN_POSITIONS[i]
        ShowWindow(hwnd, SW_RESTORE)
        MoveWindow(hwnd, pos["x"], pos["y"], pos["w"], pos["h"], True)
        buf = ctypes.create_unicode_buffer(200)
        GetWindowTextW(hwnd, buf, 200)
        print(f"   📐 Cửa sổ {i+1}: ({pos['x']},{pos['y']}) {pos['w']}x{pos['h']} \"{buf.value[:40]}\"")
        arranged += 1

    return arranged

if __name__ == "__main__":
    print("📐 Sắp xếp cửa sổ GemLogin...")
    count = arrange_gemlogin_windows()
    print(f"✅ Đã sắp xếp {count} cửa sổ!")
