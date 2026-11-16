#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brand_story_bot.py — Mỗi sáng tự chọn 1 brand thú vị (có thể bạn chưa từng nghe),
quét tin 24h, tóm tắt bằng Gemini, gửi Telegram kèm bài học chiến lược.

Biến môi trường:
  TELEGRAM_TOKEN    Token từ @BotFather
  TELEGRAM_CHAT_ID  Chat ID từ @userinfobot
  GEMINI_API_KEY    Key từ Google AI Studio (aistudio.google.com)
"""

import os, json, re, html, random, hashlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

TOKEN      = os.environ["TELEGRAM_TOKEN"].strip()
CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"].strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=" + GEMINI_KEY
STATE_FILE = "data/state.json"
MAX_STORIES = 3

# Danh sách brand: lẫn lộn từ huyền thoại đến ẩn danh, nhiều quốc gia/ngành
BRANDS = [
    # Huyền thoại toàn cầu
    ("LEGO", "Đan Mạch", "Đồ chơi"), ("Nintendo", "Nhật", "Game"),
    ("Apple", "Mỹ", "Công nghệ"), ("Amazon", "Mỹ", "Thương mại điện tử"),
    ("Nike", "Mỹ", "Thể thao"), ("Coca-Cola", "Mỹ", "Nước giải khát"),
    ("Disney", "Mỹ", "Giải trí"), ("IKEA", "Thụy Điển", "Nội thất"),
    ("McDonald's", "Mỹ", "F&B"), ("Toyota", "Nhật", "Ô tô"),
    ("Samsung", "Hàn Quốc", "Công nghệ"), ("Zara (Inditex)", "Tây Ban Nha", "Thờitrang"),
    ("LVMH", "Pháp", "Hàng hiệu"), ("Rolls-Royce", "Anh", "Ô tô"),
    ("Patagonia", "Mỹ", "Thờitrang"), ("Netflix", "Mỹ", "Giải trí"),
    ("Airbnb", "Mỹ", "Du lịch"), ("Spotify", "Thụy Điển", "Âm nhạc"),
    ("Tesla", "Mỹ", "Ô tô điện"), ("SpaceX", "Mỹ", "Vũ trụ"),
    # Brand ít phổ biến nhưng câu chuyện cực hay
    ("Muji", "Nhật", "Bán lẻ"), ("Uniqlo (Fast Retailing)", "Nhật", "Thờitrang"),
    ("Yamaha", "Nhật", "Đa ngành"), ("Brother Industries", "Nhật", "Máy văn phòng"),
    ("Häagen-Dazs", "Mỹ", "Kem"), ("Ferrero", "Ý", "Bánh kẹo"),
    ("Ferrari", "Ý", "Ô tô"), ("Barilla", "Ý", "Thực phẩm"),
    ("Maersk", "Đan Mạch", "Vận tải biển"), ("Bosch", "Đức", "Công nghiệp"),
    ("SAP", "Đức", "Phần mềm"), ("Bang & Olufsen", "Đan Mạch", "Âm thanh"),
    ("Brompton Bicycle", "Anh", "Xe đạp"), ("Dyson", "Anh", "Điện gia dụng"),
    ("Aesop", "Úc", "Mỹ phẩm"), ("Atlassian", "Úc", "Phần mềm"),
    ("Canva", "Úc", "Phần mềm"), ("Afterpay?", "", ""),
    ("Xiaomi", "Trung Quốc", "Công nghệ"), ("SHEIN", "Trung Quốc", "Thờitrang"),
    ("DJI", "Trung Quốc", "Drone"), ("Haier", "Trung Quốc", "Điện gia dụng"),
    ("Meituan", "Trung Quốc", "F&B tech"), ("Pinduoduo", "Trung Quốc", "E-commerce"),
    ("Vinamilk", "Việt Nam", "Sữa"), ("Vingroup", "Việt Nam", "Đa ngành"),
    ("FPT", "Việt Nam", "Công nghệ"), ("Viettel", "Việt Nam", "Viễn thông"),
    ("TH True Milk", "Việt Nam", "Sữa"), ("Biti's", "Việt Nam", "Giày dép"),
    ("Cà phê Trung Nguyên", "Việt Nam", "F&B"), ("Masan Group", "Việt Nam", "Tiêu dùng"),
    ("MoMo", "Việt Nam", "Fintech"), ("Zalo (VNG)", "Việt Nam", "Công nghệ"),
    ("Razer", "Singapore", "Gaming"), ("Grab", "Singapore", "Super app"),
    ("Sea Group (Shopee)", "Singapore", "E-commerce"), ("Tokopedia", "Indonesia", "E-commerce"),
    ("Gojek", "Indonesia", "Super app"), ("Traveloka", "Indonesia", "Du lịch"),
    ("Jollibee", "Philippines", "F&B"), ("SM Investments", "Philippines", "Bán lẻ"),
    ("Ayala", "Philippines", "Đa ngành"), ("AirAsia", "Malaysia", "Hàng không"),
    ("Petronas", "Malaysia", "Năng lượng"), ("Genting", "Malaysia", "Giải trí"),
    ("Rakuten", "Nhật", "E-commerce"), ("Mercari", "Nhật", "C2C"),
    ("Zoho", "Ấn Độ", "Phần mềm"), ("Flipkart", "Ấn Độ", "E-commerce"),
    ("Oyo", "Ấn Độ", "Khách sạn"), ("Byju's", "Ấn Độ", "Edtech"),
    ("Airtel", "Ấn Độ", "Viễn thông"), ("Tata Group", "Ấn Độ", "Đa ngành"),
    ("M-Pesa (Safaricom)", "Kenya", "Fintech"), ("Jumia", "Nigeria", "E-commerce"),
    ("Naspers", "Nam Phi", "Đầu tư công nghệ"), ("Shopify", "Canada", "E-commerce"),
    ("Lululemon", "Canada", "Thể thao"), ("Arc'teryx (Amer Sports)", "Canada", "Thể thao"),
    ("Kikkoman", "Nhật", "Gia vị"), ("Ajinomoto", "Nhật", "Thực phẩm"),
    ("Shiseido", "Nhật", "Mỹ phẩm"), ("Casio", "Nhật", "Đồng hồ"),
    ("Pilot (bút)", "Nhật", "Văn phòng phẩm"), ("Moleskine", "Ý", "Văn phòng phẩm"),
    ("Fiskars", "Phần Lan", "Dụng cụ"), ("Marimekko", "Phần Lan", "Thờitrang"),
    ("H&M", "Thụy Điển", "Thờitrang"), ("Volvo", "Thụy Điển", "Ô tô"),
    ("Novartis", "Thụy Sĩ", "Dược"), ("Nestlé", "Thụy Sĩ", "Thực phẩm"),
    ("Swatch", "Thụy Sĩ", "Đồng hồ"), ("Richemont", "Thụy Sĩ", "Hàng hiệu"),
    ("Budweiser (AB InBev)", "Bỉ", "Bia"), ("Hoegaarden?", "", ""),
    ("Adidas", "Đức", "Thể thao"), ("Puma", "Đức", "Thể thao"),
    ("Aldi", "Đức", "Bán lẻ"), ("Lidl", "Đức", "Bán lẻ"),
    ("Ryanair", "Ireland", "Hàng không giá rẻ"), ("Guinness", "Ireland", "Bia"),
    ("Natura (Natura &Co)", "Brazil", "Mỹ phẩm"), ("Embraer", "Brazil", "Hàng không"),
    ("Mercado Libre", "Argentina", "E-commerce"), ("Globant", "Argentina", "Phần mềm"),
    ("Kaspersky", "Nga", "An ninh mạng"), ("Yandex", "Nga", "Công nghệ"),
    ("Kakao", "Hàn Quốc", "Công nghệ"), ("Coupang", "Hàn Quốc", "E-commerce"),
    ("Hyundai", "Hàn Quốc", "Ô tô"), ("Amorepacific", "Hàn Quốc", "Mỹ phẩm"),
]
BRANDS = [b for b in BRANDS if b[1] and b[2]]  # lọc mục placeholder

# ---------- Tiện ích ----------

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"sent": [], "brands_done": []}

def save_state(state):
    os.makedirs("data", exist_ok=True)
    state["sent"] = state["sent"][-200:]
    state["brands_done"] = state["brands_done"][-150:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def http_json(url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def gemini(text, max_tokens=300):
    last_err = None
    for model in GEMINI_MODELS:
        try:
            data = http_json(GEMINI_BASE.format(model=model), {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {"temperature": 0.6, "maxOutputTokens": max_tokens},
            })
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:400]
            print(f"Model {model} -> HTTP {e.code}: {body}")
            last_err = e
        except Exception as e:
            print(f"Model {model} lỗi: {e}")
            last_err = e
    raise last_err

# ---------- Chọn brand hôm nay ----------

def pick_brand(state):
    done = set(state.get("brands_done", []))
    candidates = [b for b in BRANDS if b[0] not in done]
    if not candidates:
        state["brands_done"] = []           # đã kể hết 1 vòng -> reset
        candidates = BRANDS
    pool = random.sample(candidates, min(5, len(candidates)))
    if GEMINI_KEY:
        try:
            listing = "\n".join(f'- {n} ({c}, {i})' for n, c, i in pool)
            ans = gemini(
                "Bạn là biên tập viên chuyên mục câu chuyện kinh doanh. Hôm nay ta chọn "
                "1 brand để kể chuyện cho độc giả Việt thích chiến lược, bài học vượt khó "
                "và case study (từ brand lớn đến startup). Trong các ứng viên sau, chọn "
                f"brand có câu chuyện đáng kể/đáng học nhất, ưu tiên brand ít phổ biến với "
                f"ngườidoc Việt Nam:\n{listing}\n\nChỉ trả về đúng tên brand, không giải thích.")
            for b in pool:
                if b[0].lower() in ans.lower():
                    return b
        except Exception as e:
            print(f"Gemini chọn brand lỗi, chọn ngẫu nhiên: {e}")
    return random.choice(pool)

# ---------- Lấy tin ----------

def fetch_news(brand):
    q = urllib.parse.quote(f'"{brand}"')
    # Thử tiếng Anh trước (phủ brand quốc tế tốt hơn), thất bại thì tiếng Việt
    for hl, gl, ceid in [("en-US", "US", "US:en"), ("vi", "VN", "VN:vi")]:
        url = f"https://news.google.com/rss/search?q={q}+when:1d&hl={hl}&gl={gl}&ceid={ceid}"
        try:
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
            if items:
                return items
        except Exception as e:
            print(f"RSS lỗi ({hl}): {e}")
    return []

# ---------- Tóm tắt ----------

def summarize(brand, country, industry, title, desc):
    text = gemini(
        f"Bạn là chuyên gia phân tích chiến lược kinh doanh. Độc giả thích chiến lược, "
        f"câu chuyện vượt khó và case study. Brand: {brand} ({country}, {industry}).\n"
        f"Tin: {title}\nTrích dẫn: {desc}\n\n"
        "Trả lờI đúng cấu trúc sau, không viết thêm gì:\n"
        "TOMTAT: 2-3 câu tóm tắt tin bằng tiếng Việt, đơn giản.\n"
        "BAIHOC: 1 câu bài học chiến lược cho ngườI kinh doanh.")
    m1 = re.search(r"TOMTAT:\s*(.+?)(?=\nBAIHOC:)", text, re.S)
    m2 = re.search(r"BAIHOC:\s*(.+)", text, re.S)
    return {"tom_tat": (m1.group(1) if m1 else text).strip(),
            "bai_hoc": (m2.group(1).strip() if m2 else "")}

# ---------- Telegram ----------

def send_telegram(text):
    text = html.unescape(text)  # tránh double-escape
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status == 200

def shorten_url(url):
    try:
        api = "http://tinyurl.com/api-create.php?url=" + urllib.parse.quote(url)
        with urllib.request.urlopen(api, timeout=15) as r:
            return r.read().decode()
    except Exception:
        return url

# ---------- Main ----------

def main():
    state = load_state()
    brand, country, industry = pick_brand(state)
    news = fetch_news(brand)
    today = datetime.now().strftime("%d/%m/%Y")

    header = f"🌍 <b>Brand hôm nay: {html.escape(brand)}</b> — {html.escape(country)} · {html.escape(industry)}\n📅 {today}"
    if not news:
        send_telegram(header + "\n\nHôm nay brand này không có tin mới trên báo. "
                                "Ngày mai khám phá brand khác nhé!")
        state["brands_done"].append(brand)
        save_state(state)
        print(f"{brand}: không có tin")
        return

    fresh = []
    for n in news:
        h = hashlib.md5(n["link"].encode()).hexdigest()
        if h not in state["sent"]:
            fresh.append((h, n))

    lines = [header + "\n"]
    if not fresh:
        lines.append("Không có tin mới so với lần gửi trước.")
    used_ai = 0
    for i, (h, n) in enumerate(fresh[:MAX_STORIES], 1):
        title = html.escape(n["title"].split(" - ")[0])
        block = f"<b>{i}. {title}</b>\n"
        if GEMINI_KEY:
            try:
                s = summarize(brand, country, industry, n["title"], n["desc"])
                block += f'📝 {html.escape(s["tom_tat"])}\n💡 <i>Bài học: {html.escape(s["bai_hoc"])}</i>\n'
                used_ai += 1
            except Exception as e:
                print(f"Tóm tắt lỗi, gửi bản thường: {e}")
        block += f'🔗 <a href="{shorten_url(n["link"])}">đọc bài gốc</a>'
        lines.append(block)
    for h, n in fresh:
        state["sent"].append(h)

    state["brands_done"].append(brand)
    save_state(state)
    ok = send_telegram("\n\n".join(lines))
    print(f"OK={ok} | brand={brand} | tin mới={len(fresh)} | AI={used_ai}")

if __name__ == "__main__":
    main()
