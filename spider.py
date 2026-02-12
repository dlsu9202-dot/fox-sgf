import requests
import re
import os
import time
import sqlite3
from datetime import datetime

# ================= 基本配置 =================

LIST_URL = "https://www.foxwq.com/qipu.html"
QIPU_URL = "https://www.foxwq.com/qipu/newlist/id/{}.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

REQUEST_DELAY = 2
RETRY = 3

SAVE_ROOT = "sgf"
DB_FILE = "ids.db"
LOG_FILE = "logs.txt"

# ===========================================

# ================= 数据库 ==================

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS downloaded (id TEXT PRIMARY KEY)")
cur.execute("""
CREATE TABLE IF NOT EXISTS failed (
    id TEXT PRIMARY KEY,
    fail_days INTEGER DEFAULT 1
)
""")
conn.commit()

# ================= 工具 ==================

def log(msg):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip("_ ").strip()

# ================= 信息解析 ==================

def extract_info_from_page(html):

    js_patterns = [
        r'black\s*:\s*"([^"]+)"',
        r'white\s*:\s*"([^"]+)"',
        r'match\s*:\s*"([^"]+)"',
        r'result\s*:\s*"([^"]+)"'
    ]

    js_values = []
    for p in js_patterns:
        m = re.search(p, html)
        js_values.append(m.group(1).strip() if m else None)

    if all(js_values):
        black, white, event, result = js_values
        return event, black, white, result

    m = re.search(r'<h4[^>]*>(.*?)</h4>', html, re.S)
    if not m:
        return "未知赛事", "未知黑", "未知白", "未知结果"

    text = re.sub(r'<.*?>', '', m.group(1))
    text = re.sub(r'\s+', ' ', text).strip()

    return text[:20], "未知黑", "未知白", "未知结果"

# ================= SGF ==================

def extract_ids_from_list(html):
    return set(re.findall(r'/qipu/newlist/id/(\d+)\.html', html))

def extract_sgf(html):
    m = re.search(r'\(\s*;.*?\)\s*</div>', html, re.S)
    if not m:
        return None
    return re.sub(r'</?div.*?>', '', m.group(0)).strip()

def remove_variations(sgf):
    depth = 0
    out = []
    for c in sgf:
        if c == '(':
            depth += 1
            if depth == 1:
                out.append(c)
        elif c == ')':
            if depth == 1:
                out.append(c)
            depth -= 1
        else:
            if depth <= 1:
                out.append(c)
    return ''.join(out)

def fetch_sgf(qid):
    url = QIPU_URL.format(qid)
    for i in range(RETRY):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                raise Exception("HTTP error")

            sgf = extract_sgf(r.text)
            if not sgf:
                raise Exception("SGF not found")

            return sgf, r.text

        except Exception as e:
            log(f"重试 {qid} ({i+1}/{RETRY}) - {e}")
            time.sleep(2)

    return None, None

# ================= 主流程 ==================

def main():
    month = datetime.now().strftime("%Y-%m")

    pure_dir = os.path.join(SAVE_ROOT, "pure", month)
    ai_dir = os.path.join(SAVE_ROOT, "ai", month)

    os.makedirs(pure_dir, exist_ok=True)
    os.makedirs(ai_dir, exist_ok=True)

    log("===== 开始抓取 =====")

    html = requests.get(LIST_URL, headers=HEADERS).text
    ids = extract_ids_from_list(html)

    new_count = 0

    for qid in sorted(ids, reverse=True):
        cur.execute("SELECT 1 FROM downloaded WHERE id=?", (qid,))
        if cur.fetchone():
            continue

        log(f"下载 {qid}")

        sgf, page_html = fetch_sgf(qid)
        if not sgf:
            continue

        event, black, white, result = extract_info_from_page(page_html)

        filename = safe_filename(
            f"{event}_{black}(黑)_{white}(白)_{result}.sgf"
        )

        with open(os.path.join(ai_dir, filename), "w", encoding="utf-8") as f:
            f.write(sgf)

        with open(os.path.join(pure_dir, filename), "w", encoding="utf-8") as f:
            f.write(remove_variations(sgf))

        cur.execute("INSERT OR IGNORE INTO downloaded VALUES (?)", (qid,))
        conn.commit()

        log(f"保存成功：{filename}")
        new_count += 1
        time.sleep(REQUEST_DELAY)

    log(f"===== 完成，本次新增 {new_count} 盘 =====")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()


