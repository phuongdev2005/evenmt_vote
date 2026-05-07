# SMS Tool - Full Workflow

## Chạy bằng Docker (Khuyên dùng)

### Bước 1: Cài Docker + GemLogin
- Cài Docker Desktop từ [docker.com](https://www.docker.com/products/docker-desktop/)
- Cài GemLogin trên máy host (vote.py cần kết nối GemLogin API)
- Đảm bảo GemLogin đang chạy (API localhost:1010)

### Bước 2: Build image
```bash
cd sms_tool
docker build -t sms_tool .
```

### Bước 3: Chạy container
```bash
# Build Docker image (chạy 1 lần)
run_docker_build.bat

# Chạy full workflow với docker-compose
docker-compose up

# Hoặc chạy trực tiếp với docker run (Windows dùng --network host)
docker run --rm --network host -v ../vote:/app/vote:ro -v ./vote_cookies.sqlite3:/app/vote_cookies.sqlite3 -v ./smsaccount.txt:/app/smsaccount.txt -v ./failed_sms.txt:/app/failed_sms.txt -v ./results_sms.txt:/app/results_sms.txt sms_tool python main.py --count 5
```

### Chạy bằng .bat files (Double-click)
- `run_docker_build.bat` - Build Docker image (chạy 1 lần)
- `run_register.bat` - Đăng ký account
- `run_vote.bat` - Login + Vote
- `run_main.bat` - Full workflow
- `run_check.bat` - Kiểm tra DB

### Chạy từng script riêng
```bash
# Đăng ký
docker run --rm -v ../vote:/app/vote:ro -v ./smsaccount.txt:/app/smsaccount.txt -v ./failed_sms.txt:/app/failed_sms.txt -v ./results_sms.txt:/app/results_sms.txt sms_tool python register.py --count 5

# Login + Vote
docker run --rm -v ../vote:/app/vote:ro -v ./vote_cookies.sqlite3:/app/vote_cookies.sqlite3 -v ./smsaccount.txt:/app/smsaccount.txt sms_tool python vote.py

# Check DB
docker run --rm -v ./vote_cookies.sqlite3:/app/vote_cookies.sqlite3 -v ./smsaccount.txt:/app/smsaccount.txt -v ./failed_sms.txt:/app/failed_sms.txt -v ./results_sms.txt:/app/results_sms.txt sms_tool python check_db.py
```

**Ưu điểm Docker:**
- Không cần cài Python trên máy
- Không bị ảnh hưởng bởi môi trường hệ thống
- Dễ dàng deploy trên bất kỳ máy nào có Docker
- Tách biệt hoàn toàn với môi trường host

**⚠️ Hạn chế Docker:**
- **GemLogin workflow không hoạt động trong Docker** vì GemLogin cần launch browser window trên host machine (container không thể truy cập GUI host)
- Chỉ `register.py` hoạt động tốt trong Docker (không cần GemLogin)
- `vote.py` (login + vote) cần chạy local Python với GemLogin

---

## Luồng hoạt động

1. **register.py** - Tạo email tạm (SmailPro API) + đăng ký Elle.vn + xác nhận email
2. **vote.py** - Login bằng GemLogin (5 profile) + lưu cookie + vote
3. **main.py** - Chạy full workflow (register -> vote)
4. **check_db.py** - Kiểm tra trạng thái database

---

## Các lệnh

### 1. Đăng ký tài khoản

```bash
# Đăng ký 5 account mặc định
python sms_tool/register.py

# Đăng ký 10 account
python sms_tool/register.py --count 10

# Đăng ký với domain outlook.com
python sms_tool/register.py --count 5 --domain outlook.com

# Đăng ký với password cố định
python sms_tool/register.py --count 5 --password mypass123

# Đăng ký với API key khác
python sms_tool/register.py --count 5 --api-key YOUR_API_KEY
```

**Output:** Lưu `email|password` vào `smsaccount.txt`

---

### 2. Login + Vote (GemLogin, 5 profiles)

```bash
# Login và vote tất cả account trong smsaccount.txt
python sms_tool/vote.py

# Vote cho candidate ID khác
python sms_tool/vote.py --target 69e1fe40de1b6fbcd4b30990

# Giới hạn 10 account
python sms_tool/vote.py --limit 10

# Vote lại từ DB (không re-login)
python sms_tool/vote.py --vote-only

# Vote lại cho candidate khác
python sms_tool/vote.py --vote-only --target ANOTHER_ID
```

---

### 3. Full Workflow (register + vote)

```bash
# Full: đăng ký 5 account rồi login + vote
python sms_tool/main.py --count 5

# Full với 10 account
python sms_tool/main.py --count 10

# Chạy vòng lặp vô hạn (register -> vote -> lặp lại)
python sms_tool/main.py --count 3 --loop

# Chỉ đăng ký, không vote
python sms_tool/main.py --count 10 --register-only

# Chỉ vote lại từ DB
python sms_tool/main.py --vote-only --target <candidate_id>
```

---

### 4. Kiểm tra trạng thái

```bash
# Xem tổng kết database
python sms_tool/check_db.py
```

Hiển thị:
- Số account pending/failed/registered
- Login success/failed count
- Vote count và unique voters
- Danh sách account **pending** (login OK, chưa vote)
- 10 vote gần nhất + 10 login gần nhất

---

## Files trong thư mục

| File | Mô tả |
|------|-------|
| `register.py` | Tạo email + đăng ký Elle.vn |
| `vote.py` | Login GemLogin + lưu cookie + vote |
| `main.py` | Chạy full workflow |
| `check_db.py` | Kiểm tra DB |
| `smsaccount.txt` | Danh sách account đã tạo |
| `vote_cookies.sqlite3` | Database cookie + vote |
| `failed_sms.txt` | Account đăng ký thất bại |
| `results_sms.txt` | Account đăng ký thành công (từ register.py) |
| `requirements.txt` | Danh sách thư viện (cho local Python) |
| `setup.bat` | Cài đặt môi trường Python local (chạy 1 lần) |
| `run_docker_build.bat` | Build Docker image (chạy 1 lần) |
| `run_register.bat` | Đăng ký account (Docker) |
| `run_vote.bat` | Login + Vote (Docker) |
| `run_main.bat` | Full workflow (Docker) |
| `run_check.bat` | Kiểm tra DB (Docker) |
| `portable_setup.bat` | Download + cài Python portable (không cần cài Python) |
| `run_portable.bat` | Chạy tool bằng Python portable |
| `Dockerfile` | Docker image build file |
| `docker-compose.yml` | Docker compose config |

---

## Cài đặt trên máy KHÔNG có Python (Portable)

### Bước 1: Copy thư mục
Copy toàn bộ thư mục `sms_tool` sang máy đích.

### Bước 2: Chạy setup
Double-click `portable_setup.bat` — sẽ tự động:
- Download Python 3.11 embeddable
- Cài pip
- Cài tất cả thư viện (`httpx`, `playwright`, `colorama`, `beautifulsoup4`)
- Cài Playwright Chromium

### Bước 3: Chạy
Double-click `run_portable.bat` hoặc các file `run_*.bat`.

Python portable sẽ nằm trong `sms_tool/python_embed/`.

---

## Cài đặt trên máy CÓ Python

### Bước 1: Cài Python
Tải và cài Python 3.10+ từ [python.org](https://www.python.org/downloads/).

### Bước 2: Copy thư mục
Copy toàn bộ thư mục `sms_tool` và `vote` (chứa `gemlogin.py`) sang máy đích.

### Bước 3: Cài thư viện
Chạy `setup.bat` hoặc mở CMD trong thư mục `sms_tool`:
```bash
cd sms_tool
pip install -r requirements.txt
python -m playwright install chromium
```

### Bước 4: Chạy
Double-click các file `.bat` hoặc chạy lệnh python trực tiếp.

---

## Database Schema

### login_cookies
- `id`, `profile_id`, `email`, `status`, `current_url`, `cookies_json`, `created_at`, `updated_at`

### votes
- `id`, `email`, `target_id`, `voted_at`
