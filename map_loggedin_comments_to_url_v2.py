from pathlib import Path
from bs4 import BeautifulSoup
import re

BASE_DIR = Path(__file__).resolve().parent
html_path = BASE_DIR / "debug_loggedin_post.html"

if not html_path.exists():
    raise FileNotFoundError(f"Не найден файл: {html_path}")

html = html_path.read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "lxml")

reply_nodes = soup.select("replies-element")
print(f"REPLIES_NODES: {len(reply_nodes)}")

for i, node in enumerate(reply_nodes[:10], start=1):
    text = node.get_text(" ", strip=True)
    nums = re.findall(r'[\d.,]+[KMB]?', text, flags=re.I)
    comments_count = nums[0] if nums else ""

    bubble = node
    while bubble is not None:
        classes = bubble.attrs.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        if bubble.name == "div" and "bubble" in classes:
            break
        bubble = bubble.parent

    mapped = []
    if bubble is not None:
        for a in bubble.select("a[href]"):
            href = a.get("href", "")
            if "/muztv/" in href:
                mapped.append(href)

    print(f"[{i}] COMMENTS_COUNT: {comments_count}")
    print(f"[{i}] BUBBLE_FOUND: {bubble is not None}")
    print(f"[{i}] URLS: {mapped[:10]}")
    print("---")
