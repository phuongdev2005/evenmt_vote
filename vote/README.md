# Elle Beauty Awards 2026 - Auto Login & Vote

Hệ thống tự động login và vote cho sự kiện Elle Beauty Awards 2026.

## Cấu trúc

| File | Chức năng |
|------|-----------|
| `open_profiles.py` | Login tự động bằng GemLogin + Playwright |
| `vote_api.py` | Vote qua API (Next.js Server Action) |
| `vote_single.py` | Vote 1 account cụ thể |
| `vote_all.py` | Vote tự động bằng nhiều account |
| `export_accounts.py` | Xuất danh sách voted/unvoted ra txt |
| `check_vote_status.py` | Kiểm tra trạng thái vote |
| `gemlogin.py` | Kết nối GemLogin API |
| `account.txt` | Danh sách tài khoản email |
| `login_cookies.sqlite3` | Database lưu cookies sau login |

## Yêu cầu

- Python 3.10+
- GemLogin đang chạy (port 1010)
- Các gói: `httpx`, `playwright`, `colorama`

```bash
pip install -r requirements.txt
playwright install chromium
```

## 1. Login tự động

### Chạy test

```bash
python vote/open_profiles.py
```

### Chạy liên tục đến khi hết account

```bash
python vote/run_until_empty.py
```

### Tham số điều chỉnh (trong `open_profiles.py`)

```python
NUM_PROFILES = 6               # Số profile song song (mặc định 6)
MAX_ACCOUNTS_PER_RUN = 0       # 0 = không giới hạn, chạy hết
```

### Tính năng

- **Tự động xóa account đã xử lý** khỏi `account.txt`
- **Không xử lý lại** account đã có trong database
- **Sắp xếp cửa sổ**: 6 profile theo lưới 3x2, mỗi cửa sổ 512x412
- **Tự động giải CAPTCHA** (Cloudflare Turnstile)
- **Đo thời gian** và thống kê success/failure

## 2. Vote tự động

### Vote tất cả account chưa vote

```bash
python vote/vote_api.py
```

### Vote số lượng giới hạn (test)

```bash
python vote/vote_api.py --limit 5
```

### Vote 1 account cụ thể

```bash
python vote/vote_api.py --email xekzh0g1rp@jieluv.com
```

### Vote candidate khác

```bash
python vote/vote_api.py --target 69e1fe40de1b6fbcd4b30990
```

### Vote bằng vote_single.py

```bash
python vote/vote_single.py xekzh0g1rp@jieluv.com
python vote/vote_single.py xekzh0g1rp@jieluv.com --target 69e1fe40de1b6fbcd4b30990
```

### Vote tất cả account (không check voted_at)

```bash
python vote/vote_all.py
```

## 3. Kiểm tra trạng thái

### Check nhanh (số lượng)

```bash
python vote/vote_api.py --check
```

Output: `Total success: 626 | Voted: 323 | Unvoted: 303`

### Check chi tiết

```bash
python vote/check_vote_status.py
```

### Xuất ra file txt

```bash
python vote/export_accounts.py
```

Tạo:
- `vote/voted_accounts.txt`
- `vote/unvoted_accounts.txt`

## 4. Dọn dẹp

### Xóa duplicate & account đã có trong DB

```bash
python vote/clean_duplicates.py
```

## Candidate IDs

| ID | Tên |
|----|-----|
| `69e1fe40de1b6fbcd4b30990` | Kim Tuyến |
| `69e1fa86df6e31bd3fa4c6f8` | Huyền Tường San |
| `69e1fa8da51bd7bcd50c5b2e` | ... |

## Lưu ý

- Mỗi account chỉ vote **1 lần/24 giờ**
- Vote thành công sẽ được đánh dấu trong database (`voted_at`, `voted_for`)
- Nếu gặp lỗi "Event loop is closed", giảm `NUM_PROFILES` xuống
