#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brand_story_bot.py — Gửi "câu chuyện brand hàng ngày" vào Telegram, tóm tắt bằng Gemini.

Biến môi trường:
  BRAND_NAME       Tên brand (VD: LEGO)
  TELEGRAM_TOKEN   Token từ @BotFather
  TELEGRAM_CHAT_ID Chat ID từ @userinfobot
  GEMINI_API_KEY   Key từ Google AI Studio (aistudio.google.com)
  GEMINI_MODEL     Mặc định: gemini-2.5-flash
"""

import os, json, re, hashlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

BRAND      = os.environ.get("BRAND_NAME", "LEGO")
TOKEN      = os.environ["TELEGRAM_TOKEN"]
CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
MODEL      = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
STATE_FILE = "data/state.json"
MAX_STORIES = 3   # số tin được tóm tắt bằng AI mỗi ngày (tiết kiệm quota)

# ---------- Tiện ích ----------

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"sent": []}

def save_state(state):
    os.makedirs("data", exist_ok=True)
    state["sent"] = state["sent"][-200:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ---------- Lấy tin ----------

def fetch_news(brand):
    q = urllib.parse.quote(f'"{brand}"')
    url = f"https://news.google.com/rss/search?q={q}+when:1d&hl=vi&gl=VN&ceid=VN:vi"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    items = []
    for item in root.iter("item"):
        title = item.findtext("title") or ""
        link  = item.findtext("link") or ""
        desc  = item.findtext("description") or ""
        if title and link:
            items.append({"title": title, "link": link,
                          "desc": re.sub(r"<[^>]+>", "", desc)[:600]})
    return items

# ---------- Gemini ----------

def gemini_summarize(title, desc):
    """Trả về dict(tom_tat, bai_hoc) hoặc None nếu lỗi."""
    prompt = f"""Bạn là chuyên gia phân tích chiến lược kinh doanh. Người đọc thích đọc về chiến lược brand, câu chuyện vượt khó và case study.

Tin tức về brand "{BRAND}":
Tiêu đề: {title}
Trích dẫn: {desc}

Hãy trả lời đúng theo cấu trúc sau, không viết gì thêm:
TOMTAT: 2-3 câu tóm tắt tin bằng tiếng Việt, đơn giản, dễ hiểu.
BAIHOC: 1 câu bài học chiến lược rút ra cho người kinh doanh."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 300},
    }).encode()
    url = GEMINI_URL.format(model=MODEL, key=GEMINI_KEY)
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    m1 = re.search(r"TOMTAT:\s*(.+?)(?=\nBAIHOC:)", text, re.S)
    m2 = re.search(r"BAIHOC:\s*(.+)", text, re.S)
    return {
        "tom_tat": (m1.group(1) if m1 else text).strip(),
        "bai_hoc": (m2.group(1).strip() if m2 else ""),
    }

# ---------- Telegram ----------

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status == 200

def shorten_url(url):
    """Google News link rất dài gây lỗi 400; rút gọn bằng tinyurl."""
    api = "http://tinyurl.com/api-create.php?url=" + urllib.parse.quote(url)
    try:
        with urllib.request.urlopen(api, timeout=15) as r:
            return r.read().decode()
    except Exception:
        return url

# ---------- Main ----------

def main():
    state = load_state()
    news = fetch_news(BRAND)
    fresh = []
    for n in news:
        h = hashlib.md5(n["link"].encode()).hexdigest()
        if h not in state["sent"]:
            fresh.append((h, n))

    today = datetime.now().strftime("%d/%m/%Y")
    if not fresh:
        send_telegram(f"📭 <b>Câu chuyện {BRAND} — {today}</b>\n\nHôm nay không có tin mới. Ngày mai quay lại nhé!")
        print("Không có tin mới")
        return

    lines = [f"📰 <b>Câu chuyện {BRAND} — {today}</b>\n"]
    to_summarize = fresh[:MAX_STORIES]
    used_ai = 0

    for i, (h, n) in enumerate(to_summarize, 1):
        title = n["title"].split(" - ")[0]
        block = f"<b>{i}. {title}</b>\n"
        if GEMINI_KEY:
            try:
                s = gemini_summarize(n["title"], n["desc"])
                block += f'📝 {s["tom_tat"]}\n💡 <i>Bài học: {s["bai_hoc"]}</i>\n'
                used_ai += 1
            except Exception as e:
                print(f"Gemini lỗi, dùng bản thường: {e}")
        block += f"🔗 <a href=\"{shorten_url(n['link'])}\">đọc bài gốc</a>"
        lines.append(block)
        state["sent"].append(h)

    # Tin thừa (nếu > MAX_STORIES): gửi kèm dạng danh sách nhanh
    extra = fresh[MAX_STORIES:]
    if extra:
        lines.append("<b>Tin khác:</b>")
        for n in extra:
            state["sent"].append(hashlib.md5(n["link"].encode()).hexdigest())

    save_state(state)
    ok = send_telegram("\n\n".join(lines))
    print(f"OK={ok}, tin mới={len(fresh)}, tóm tắt AI={used_ai}")

if __name__ == "__main__":
    main()
