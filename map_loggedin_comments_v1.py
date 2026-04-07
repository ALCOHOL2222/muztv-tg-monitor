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

for i, node in enumerate(reply_nodes[:20], start=1):
    text = node.get_text(" ", strip=True)
    nums = re.findall(r'[\d.,]+[KMB]?', text, flags=re.I)
    comments_count = nums[0] if nums else ""

    parent = node
    mapped_url = None

    for _ in range(12):
        if parent is None:
            break
        links = parent.select('a[href*="https://t.me/muztv/"], a[href*="https://t.me/muztv?"], a[href*="/muztv/"]')
        for a in links:
            href = a.get("href", "")
            if "/muztv/" in href:
                mapped_url = href
                break
        if mapped_url:
            break
        parent = parent.parent

    print(f"[{i}] COMMENTS_COUNT: {comments_count}")
    print(f"[{i}] MAPPED_URL: {mapped_url}")
    print("---")
