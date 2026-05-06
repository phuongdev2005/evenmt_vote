import http.server
import socketserver
import json
import urllib.request
import re
import threading
import time
import os
import sqlite3
import random
import string
from datetime import datetime, timedelta
import webbrowser

PORT = 9090
URL = "https://events.elle.vn/elle-beauty-awards-2026/nhan-vat"

DB_FILE = "tracker.db"

SECTIONS = [
    ("69e1fafaa51bd7bcd50c5b32", "Best Face"),
    ("69e1fbd7a51bd7bcd50c5b33", "Best Hair"),
    ("69e1fce9de1b6fbcd4b30988", "Best Body"),
    ("69e1fde4df6e31bd3fa4c702", "Best Looking Gentleman"),
    ("69e1ff73df6e31bd3fa4c709", "Male Breakthrough Artist"),
    ("69e1ff7bf0f595bd4a8d225a", "Female Breakthrough Artist"),
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS snapshots
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  data_json TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(snap):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO snapshots (timestamp, data_json) VALUES (?, ?)", 
              (snap['timestamp'], json.dumps(snap, ensure_ascii=False)))
    
    # Dọn dẹp dữ liệu cũ (chỉ giữ lại 2 ngày gần nhất)
    two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()
    c.execute("DELETE FROM snapshots WHERE timestamp < ?", (two_days_ago,))
    
    conn.commit()
    conn.close()

def get_latest_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT data_json FROM snapshots ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def get_past_data(minutes_ago):
    target_time = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tìm snapshot có thời gian gần nhất với target_time (lấy cái nhỏ hơn hoặc bằng target_time)
    c.execute("SELECT data_json FROM snapshots WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1", (target_time,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def fetch_data_from_elle():
    token = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    req = urllib.request.Request(f"{URL}?_rsc={token}", headers={
        "User-Agent": "Mozilla/5.0", "RSC": "1"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8")
    except Exception as e:
        print(f"Error fetching: {e}")
        return None

    celebrities = []
    all_pcts = re.findall(r'"votePercentage"\s*:\s*"([^"]+)"', raw)
    for pct in all_pcts:
        idx = raw.find(f'"votePercentage":"{pct}"')
        window = raw[max(0, idx - 400): idx]
        names = re.findall(r'"name"\s*:\s*"([^"]+)"', window)
        if names:
            celebrities.append({"name": names[-1], "pct": float(pct.rstrip('%'))})
            
    snap = {"timestamp": datetime.now().isoformat(), "sections": {}}
    for i, (sid, title) in enumerate(SECTIONS):
        snap["sections"][sid] = {"title": title, "candidates": celebrities[i*5: (i+1)*5]}
    return snap

def background_fetch():
    while True:
        snap = fetch_data_from_elle()
        if snap:
            save_to_db(snap)
        time.sleep(1) # Cập nhật mỗi 1 giây (Hyper Real-time)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ELLE Beauty Awards 2026 - Pro Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #121212; color: #ffffff; font-family: 'Inter', sans-serif; }
        .card { background-color: #1e1e1e; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        .neutral { color: #9ca3af; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #333; }
        th { color: #9ca3af; font-size: 12px; text-transform: uppercase; }
        .rank-1 { color: #fbbf24; font-weight: bold; }
    </style>
</head>
<body class="p-8">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-3xl font-bold text-white">ELLE BEAUTY AWARDS 2026</h1>
            <div class="text-gray-400">
                Lần cập nhật cuối: <span id="last-update" class="text-white font-mono">Đang tải...</span>
            </div>
        </div>
        
        <div id="dashboard">
            <div class="text-center text-gray-400 mt-20">Đang tải dữ liệu trực tiếp...</div>
        </div>
    </div>

    <script>
        function formatNumber(num) {
            return num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ".");
        }

        function formatDiff(diff) {
            if (diff === null || diff === 0) return '<span class="neutral">-</span>';
            const val = diff.toFixed(1);
            if (diff > 0) return '<span class="positive">+' + val + '%</span>';
            return '<span class="negative">' + val + '%</span>';
        }

        async function updateDashboard() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                if (data.error) return;

                document.getElementById('last-update').innerText = new Date(data.current.timestamp).toLocaleTimeString('vi-VN');
                
                let html = '';
                for (const [sid, sdata] of Object.entries(data.current.sections)) {
                    html += `<div class="card">
                        <h2 class="text-xl font-bold mb-4 uppercase text-pink-500">${sdata.title}</h2>
                        <table>
                            <thead>
                                <tr>
                                    <th width="5%">#</th>
                                    <th width="35%">ỨNG VIÊN</th>
                                    <th width="15%">%</th>
                                    <th width="10%">1MIN</th>
                                    <th width="10%">10MIN</th>
                                    <th width="10%">1H</th>
                                    <th width="10%">24H</th>
                                </tr>
                            </thead>
                            <tbody>`;
                    
                    const candidates = [...sdata.candidates].sort((a, b) => b.pct - a.pct);
                    candidates.forEach((c, index) => {
                        const rank = index + 1;
                        const rankHtml = rank === 1 ? '<span class="rank-1">👑 1</span>' : rank;
                        
                        const getPastPct = (pastSnap) => {
                            if (!pastSnap) return null;
                            const pastCands = pastSnap.sections[sid]?.candidates || [];
                            const pastC = pastCands.find(x => x.name === c.name);
                            return pastC ? pastC.pct : null;
                        };

                        const diff1m = data.past_1m ? c.pct - getPastPct(data.past_1m) : null;
                        const diff10m = data.past_10m ? c.pct - getPastPct(data.past_10m) : null;
                        const diff1h = data.past_1h ? c.pct - getPastPct(data.past_1h) : null;
                        const diff24h = data.past_24h ? c.pct - getPastPct(data.past_24h) : null;

                        html += `<tr>
                            <td>${rankHtml}</td>
                            <td class="font-medium">${c.name}</td>
                            <td class="font-mono text-lg font-bold">${c.pct.toFixed(1)}%</td>
                            <td class="font-mono">${formatDiff(diff1m)}</td>
                            <td class="font-mono">${formatDiff(diff10m)}</td>
                            <td class="font-mono">${formatDiff(diff1h)}</td>
                            <td class="font-mono">${formatDiff(diff24h)}</td>
                        </tr>`;
                    });
                    
                    html += `</tbody></table></div>`;
                }
                
                document.getElementById('dashboard').innerHTML = html;
            } catch (err) {
                console.error(err);
            }
        }

        updateDashboard();
        setInterval(updateDashboard, 1000); // Tải lại mỗi 1 giây
    </script>
</body>
</html>
"""

class TrackerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            
            current_data = get_latest_data()
            if not current_data:
                self.wfile.write(b'{"error": "No data yet"}')
                return
                
            response = {
                "current": current_data,
                "past_1m": get_past_data(1),
                "past_10m": get_past_data(10),
                "past_1h": get_past_data(60),
                "past_24h": get_past_data(1440)
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_error(404)

if __name__ == "__main__":
    # Khởi tạo DB
    init_db()
    
    # Import dữ liệu cũ từ file JSON nếu có
    if os.path.exists("web_history.json"):
        try:
            with open("web_history.json", "r", encoding="utf-8") as f:
                old_history = json.load(f)
                for snap in old_history:
                    save_to_db(snap)
            os.remove("web_history.json") # Đã import xong thì xóa
            print("Đã migrate dữ liệu từ file JSON sang SQLite thành công!")
        except: pass

    # Start background thread
    t = threading.Thread(target=background_fetch, daemon=True)
    t.start()
    
    # Wait for first fetch
    print("Đang lấy dữ liệu ban đầu...")
    time.sleep(2)
    
    # Start server
    try:
        with socketserver.TCPServer(("", PORT), TrackerHandler) as httpd:
            print(f"===========================================================")
            print(f"🚀 SQLite Dashboard chạy tại: http://localhost:{PORT}")
            print(f"===========================================================")
            webbrowser.open(f"http://localhost:{PORT}")
            httpd.serve_forever()
    except OSError:
        print(f"Cổng {PORT} đang được sử dụng. Vui lòng tắt các server cũ trước khi chạy lại.")
