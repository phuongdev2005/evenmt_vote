import sqlite3
conn = sqlite3.connect('vote/login_cookies.sqlite3')
rows = conn.execute("SELECT email FROM login_cookies WHERE status='success' AND voted_at IS NULL LIMIT 3").fetchall()
for r in rows:
    print(r[0])
