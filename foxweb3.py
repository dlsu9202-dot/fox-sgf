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
RETRY = 1

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


# ================= ⭐ 核心：标题解析 ==================

def extract_info_from_page(html, qid):
    """
    统一解析：
    比赛名 + A执黑/执白 + 结果 + B
    """

    m = re.search(r'<h4[^>]*>(.*?)</h4>', html, re.S)
    if not m:
        return "未知赛事", "未知黑", "未知白", "未知结果", qid[:8]

    text = m.group(1)

    # 清理 HTML
    text = re.sub(r'<.*?>', '', text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("绝艺讲解", "")
    text = re.sub(r'\s+', ' ', text).strip()

    # ===== 比赛名（不写死）=====
    # 规则：第一个空格之前
    if " " in text:
        event = text.split(" ")[0].strip()
        rest = text[len(event):].strip()
    else:
        return "未知赛事", "未知黑", "未知白", "未知结果", qid[:8]

    # ===== 核心结构匹配 =====
    # A执黑中盘胜B
    # A执白5.5目胜B
    m2 = re.search(
        r'(.+?)执(黑|白)(中盘|[\d\.]+目)?胜(.+)',
        rest
    )

    if not m2:
        return event, "未知黑", "未知白", "未知结果", qid[:8]

    player_a = m2.group(1).strip()
    color = m2.group(2)
    win_type = m2.group(3)
    player_b = m2.group(4).strip()

    # ===== 黑白判断 =====
    if color == "黑":
        black = player_a
        white = player_b
    else:
        white = player_a
        black = player_b

    # ===== 结果统一 =====
    if win_type is None:
        result = f"{color}胜"
    elif win_type == "中盘":
        result = f"{color}中盘胜"
    else:
        result = f"{color}{win_type}胜"

    date = qid[:8]

    return event, black, white, result, date


# ================= 列表页 ==================

def extract_ids_from_list(html):
    return set(re.findall(r'/qipu/newlist/id/(\d+)\.html', html))


# ================= SGF ==================

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
            cur.execute("INSERT OR IGNORE INTO failed VALUES (?, 1)", (qid,))
            conn.commit()
            continue

        event, black, white, result, date = extract_info_from_page(page_html, qid)

        filename = safe_filename(
            f"{event}_{black}_{white}_{result}_{date}.sgf"
        )[:200]

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
