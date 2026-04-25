"""Tạo email ngẫu nhiên từ danh sách domain cố định → lưu accounts.txt"""
import random
import string
import sys

domains = [
    '24mail.top', 'abyis.com', 'alightmotion.id', 'amazinggift.life', 'annd.us',
    'arthiq.world', 'au1688x.us', 'basakerrr.digital', 'btcmod.com', 'checkotpmail.com',
    'chiamn.com', 'chongqilai.cc', 'clonehotmail.click', 'code-gmail.com', 'dontsleep404.com',
    'donusumekatil.com', 'easyhomefit.com', 'edgetopgrid.com', 'fbviamail.com', 'fviamail.com',
    'generator1email.com', 'gmaiil.top', 'gmail2.gq', 'gmail2.shop', 'gmaillk.com',
    'gptpluz2.shop', 'higuruma.site', 'histartool.com', 'iapermisul.ro', 'javaka.live',
    'jieluv.com', 'jualakun.com', 'kajaib.social', 'kt-family.my.id', 'kt-gmail.com',
    'kunseller.top', 'linkbm365.com', 'luffygadgets.com', 'mabubsa.com', 'mailgetget.asia',
    'meser.cc', 'miscalhero.com', 'mlemmlem.asia', 'moreablle.com', 'nangspa.vn',
    'navermail.kr', 'nevanata.com', 'ngontol.com', 'opelkun.net', 'peakpoppro.com',
    'phanmembanhang24h.com', 'plup.me', 'redproxies.com', 'remaild.com', 'riko.my',
    'shopeeboost.com', 'sociefan.com', 'streamingku.live', 'tempmail247.top', 'voucherskuy.com',
    'vregion.ru', 'warunkto.com', 'zavex.sbs'
]

def generate_random_username(length=10):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

# Lấy số lượng email từ tham số dòng lệnh, mặc định là 63
count = int(sys.argv[1]) if len(sys.argv) > 1 else len(domains)

emails = []
for i in range(count):
    domain = domains[i % len(domains)]  # Lặp lại domain nếu cần
    username = generate_random_username()
    email = f'{username}@{domain}'
    emails.append(email)

with open('accounts_https.txt', 'w', encoding='utf-8') as f:
    for email in emails:
        f.write(f'{email}|{email}\n')

print(f'Đã tạo {len(emails)} email')
print('Đã lưu vào accounts_https.txt')
