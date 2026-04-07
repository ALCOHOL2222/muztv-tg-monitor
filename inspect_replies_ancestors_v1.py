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

for i, node in enumerate(reply_nodes[:5], start=1):
    text = node.get_text(" ", strip=True)
    nums = re.findall(r'[\d.,]+[KMB]?', text, flags=re.I)
    comments_count = nums[0] if nums else ""

    print(f"\n=== NODE {i} ===")
    print(f"COMMENTS_COUNT: {comments_count}")
    print(f"NODE_HTML: {str(node)[:1200]}")

    parent = node
    level = 0
    while parent is not None and level < 10:
        attrs = {}
        for k, v in parent.attrs.items():
            attrs[k] = v
        print(f"LEVEL {level}: TAG={parent.name} ATTRS={attrs}")
        parent = parent.parent
        level += 1
