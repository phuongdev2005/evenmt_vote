# Elle Beauty Awards 2026 - Auto Login & Vote

Hệ thống tự động login và vote cho sự kiện Elle Beauty Awards 2026.

## Cấu trúc

| File | Chức năng |
|------|-----------|
| `open_profiles.py` | Login tự động bằng GemLogin + Playwright |
| `vote_api.py` | Vote qua API (Next.js Server Action) |
| `vote_all.py` | Vote tự động bằng nhiều account |
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

### Chạy test (120 accounts, 12 profiles)

```bash
python vote/open_profiles.py
```

### Chạy liên tục đến khi hết account

```bash
python vote/run_until_empty.py
```

### Tham số điều chỉnh (trong `open_profiles.py`)

```python
NUM_PROFILES = 12              # Số profile song song
MAX_ACCOUNTS_PER_RUN = 120     # Số account mỗi lần chạy
```

### Tính năng

- **Tự động xóa account đã xử lý** khỏi `account.txt`
- **Không xử lý lại** account đã có trong database
- **Sắp xếp cửa sổ**: 12 profile đè lên nhau tại `(0, 0)`
- **Tự động giải CAPTCHA** (Cloudflare Turnstile)
- **Đo thời gian** và thống kê success/failure

## 2. Vote tự động

### Vote 1 account ngẫu nhiên

```bash
python vote/vote_api.py
```

### Vote cho candidate cụ thể

Sửa `target_id` trong `vote_api.py`:

```python
target_id = "69e1fa8da51bd7bcd50c5b2e"  # Candidate ID
```

### Vote tất cả account chưa vote

```bash
python vote/vote_all.py
```

## 3. Kiểm tra trạng thái

```bash
python vote/check_vote_status.py
```

Hiển thị:
- Tổng số account
- Số đã vote / chưa vote
- Danh sách chi tiết

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
- Nếu gặp lỗi "Event loop is closed", giảm `MAX_ACCOUNTS_PER_RUN` xuống
