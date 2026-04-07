from pathlib import Path
from bs4 import BeautifulSoup
import re

BASE_DIR = Path(__file__).resolve().parent
html_path = BASE_DIR / "debug_loggedin_post.html"

if not html_path.exists():
    raise FileNotFoundError(f"Не найден файл: {html_path}")

html = html_path.read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "lxml")

# Ищем все replies-element
reply_nodes = soup.select("replies-element")

print(f"REPLIES_NODES: {len(reply_nodes)}")

for i, node in enumerate(reply_nodes[:20], start=1):
    text = node.get_text(" ", strip=True)
    nums = re.findall(r'[\d.,]+[KMB]?', text, flags=re.I)
    print(f"[{i}] TEXT: {text[:500]}")
    print(f"[{i}] NUMS: {nums}")
    print("---")
