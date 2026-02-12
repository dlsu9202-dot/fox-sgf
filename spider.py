import requests
import re
import os
import time
import sqlite3
import zipfile
from datetime import datetime

# =========================
# 基础配置
# =========================
LIST_URL = "https://www.foxwq.com/qipu.html"
QIPU_URL = "https://www.foxwq.com/qipu/newlist/id/{}.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

REQUEST_DELAY = 2
RETRY = 1

SAVE_ROOT = "sgf"
DB_FILE = "ids.db"

# =========================
# 初始化
# =========================
os.makedirs(SAVE_ROOT, exist_ok=True)

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS downloaded (id TEXT PRIMARY KEY)")
conn.commit()


# =========================
# 工具函数
# =========================
def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip("_ ")


def extract_sgf(html):
    m = re.search(r'\(\s*;.*?\)\s*</div>', html, re.S)
    if not m:
        return None
    return re.sub(r'</?div.*?>', '', m.group(0)).strip()


# =========================
# 去变化（纯棋谱）
# =========================
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


# =========================
# 解析标题信息
# =========================
def extract_info_from_page(html):
    m = re.search(r'<h4[^>]*>(.*?)</h4>', html, re.S)
    if not m:
        return "未知赛事", "未知黑", "未知白", "未知结果"

    text = re.sub(r'<.*?>', '', m.group(1))
    text = text.replace("&nbsp;", " ").replace("绝艺讲解", "")
    text = re.sub(r'\s+', ' ', text).strip()

    # 示例：安斋孝浚执白中盘胜曹承亚
    m2 = re.search(r'(.+?)执(黑|白)(中盘|[\d\.]+目)?胜(.+)', text)
    if not m2:
        return "未知赛事", "未知黑", "未知白", "未知结果"

    p1 = m2.group(1).strip()
    color = m2.group(2)
    win_type = m2.group(3)
    p2 = m2.group(4).strip()

    if color == "黑":
        black, white = p1, p2
    else:
        black, white = p2, p1

    if win_type == "中盘":
        result = f"{color}中盘胜"
    elif win_type:
        result = f"{color}{win_type}胜"
    else:
        result = f"{color}胜"

    event = text.split(" ")[0]
    return event, black, white, result


# =========================
# 下载棋谱
# =========================
def fetch_sgf(qid):
    url = QIPU_URL.format(qid)
    for _ in range(RETRY):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            sgf = extract_sgf(r.text)
            if sgf:
                return sgf, r.text
        except:
            pass
        time.sleep(1)
    return None, None


# =========================
# 压缩目录
# =========================
def zip_dir(folder):
    zip_path = folder + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, folder)
                z.write(full, rel)


# =========================
# 主流程
# =========================
def main():
    month = datetime.now().strftime("%Y-%m")

    ai_dir = os.path.join(SAVE_ROOT, "ai", month)
    pure_dir = os.path.join(SAVE_ROOT, "pure", month)

    os.makedirs(ai_dir, exist_ok=True)
    os.makedirs(pure_dir, exist_ok=True)

    html = requests.get(LIST_URL, headers=HEADERS).text
    ids = set(re.findall(r'/qipu/newlist/id/(\d+)\.html', html))

    pure_merge = []

    for qid in sorted(ids, reverse=True):
        cur.execute("SELECT 1 FROM downloaded WHERE id=?", (qid,))
        if cur.fetchone():
            continue

        sgf, page_html = fetch_sgf(qid)
        if not sgf:
            continue

        event, black, white, result = extract_info_from_page(page_html)
        fname = safe_filename(f"{event}_{black}(黑)_{white}(白)_{result}.sgf")

        # AI 原版
        ai_path = os.path.join(ai_dir, fname)
        with open(ai_path, "w", encoding="utf-8") as f:
            f.write(sgf)

        # 纯棋谱
        pure_sgf = remove_variations(sgf)
        pure_path = os.path.join(pure_dir, fname)
        with open(pure_path, "w", encoding="utf-8") as f:
            f.write(pure_sgf)

        pure_merge.append(pure_sgf)

        cur.execute("INSERT OR IGNORE INTO downloaded VALUES (?)", (qid,))
        conn.commit()

        time.sleep(REQUEST_DELAY)

    # =========================
    # 纯棋谱合集（你要的第 5 点）
    # =========================
    merge_path = os.path.join(pure_dir, f"pure_{today}_merge.sgf")
    with open(merge_path, "w", encoding="utf-8") as f:
        for s in pure_merge:
            f.write(s + "\n\n")

    # =========================
    # 自动压缩（你要的第 4 点）
    # =========================
    zip_dir(ai_dir)
    zip_dir(pure_dir)


if __name__ == "__main__":
    main()
