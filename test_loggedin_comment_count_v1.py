from pathlib import Path
from bs4 import BeautifulSoup
import re

BASE_DIR = Path(__file__).resolve().parent
html_path = BASE_DIR / "debug_loggedin_post.html"

if not html_path.exists():
    raise FileNotFoundError(f"Не найден файл: {html_path}")

TARGET_POST_ID = 24876
CHANNEL_OFFSET = 4294967296

html = html_path.read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "lxml")

found = False

for node in soup.select("replies-element"):
    text = node.get_text(" ", strip=True)
    nums = re.findall(r'[\d.,]+[KMB]?', text, flags=re.I)
    comments_count = nums[0] if nums else "0"

    bubble = node
    while bubble is not None:
        classes = bubble.attrs.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        if bubble.name == "div" and "bubble" in classes:
            break
        bubble = bubble.parent

    if bubble is None:
        continue

    data_mid = bubble.get("data-mid")
    if not data_mid:
        continue

    try:
        msg_id = int(data_mid) - CHANNEL_OFFSET
    except Exception:
        continue

    if msg_id == TARGET_POST_ID:
        print(f"TARGET_POST_ID: {TARGET_POST_ID}")
        print(f"DATA_MID: {data_mid}")
        print(f"COMMENTS_COUNT: {comments_count}")
        found = True
        break

if not found:
    print("TARGET_POST_NOT_FOUND")
