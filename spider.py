import requests
import re
import os
import time
import sqlite3
from datetime import datetime

LIST_URL = "https://www.foxwq.com/qipu.html"
QIPU_URL = "https://www.foxwq.com/qipu/newlist/id/{}.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

REQUEST_DELAY = 2
RETRY = 1

BASE_DIR = "sgf"
DB_FILE = "ids.db"

os.makedirs(BASE_DIR, exist_ok=True)

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS downloaded (id TEXT PRIMARY KEY)")
conn.commit()


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip()


def extract_ids_from_list(html):
    return set(re.findall(r'/qipu/newlist/id/(\d+)\.html', html))


def extract_sgf(html):
    m = re.search(r'\(\s*;.*?\)\s*</div>', html, re.S)
    if not m:
        return None
    return re.sub(r'</?div.*?>', '', m.group(0)).strip()


def extract_info_from_page(html, qid):
    m = re.search(r'<h4[^>]*>(.*?)</h4>', html, re.S)
    if not m:
        return "未知赛事", "未知黑", "未知白", "未知结果", qid[:8]

    text = m.group(1)
    text = re.sub(r'<.*?>', '', text)
    text = text.replace("&nbsp;", " ").replace("绝艺讲解", "")
    text = re.sub(r'\s+', ' ', text).strip()

    if " " not in text:
        return "未知赛事", "未知黑", "未知白", "未知结果", qid[:8]

    event = text.split(" ")[0]
    rest = text[len(event):].strip()

    m2 = re.search(r'(.+?)执(黑|白)(中盘|[\d\.]+目)?胜(.+)', rest)
    if not m2:
        return event, "未知黑", "未知白", "未知结果", qid[:8]

    p1 = m2.group(1).strip()
    color = m2.group(2)
    win_type = m2.group(3)
    p2 = m2.group(4).strip()

    if color == "黑":
        black, white = p1, p2
    else:
        white, black = p1, p2

    if win_type == "中盘":
        result = f"{color}中盘胜"
    elif win_type:
        result = f"{color}{win_type}胜"
    else:
        result = f"{color}胜"

    return event, black, white, result, qid[:8]


def fetch_sgf(qid):
    url = QIPU_URL.format(qid)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        sgf = extract_sgf(r.text)
        return sgf, r.text
    except:
        return None, None


def main():
    month = datetime.now().strftime("%Y-%m")
    save_dir = os.path.join(BASE_DIR, month)
    os.makedirs(save_dir, exist_ok=True)

    html = requests.get(LIST_URL, headers=HEADERS).text
    ids = extract_ids_from_list(html)

    for qid in sorted(ids, reverse=True):
        cur.execute("SELECT 1 FROM downloaded WHERE id=?", (qid,))
        if cur.fetchone():
            continue

        sgf, page_html = fetch_sgf(qid)
        if not sgf:
            continue

        event, black, white, result, date = extract_info_from_page(page_html, qid)

        filename = safe_filename(f"{event}_{black}_{white}_{result}_{date}.sgf")
        path = os.path.join(save_dir, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(sgf)

        cur.execute("INSERT OR IGNORE INTO downloaded VALUES (?)", (qid,))
        conn.commit()

        time.sleep(REQUEST_DELAY)


if __name__ == "__main__":
    main()
