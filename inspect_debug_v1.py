from pathlib import Path
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
html_path = BASE_DIR / "debug_post_24876.html"

if not html_path.exists():
    raise FileNotFoundError(f"Не найден файл: {html_path}")

html = html_path.read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "lxml")

print("=== BASIC SELECTORS ===")

selectors = [
    ".tgme_widget_message_views",
    ".tgme_widget_message_replies",
    ".tgme_widget_message_reactions",
    ".tgme_widget_message_reaction",
    ".tgme_widget_message_forwards",
    ".tgme_widget_message_footer",
    ".tgme_widget_message_info",
]

for sel in selectors:
    nodes = soup.select(sel)
    print(f"\nSELECTOR: {sel} | count={len(nodes)}")
    for i, node in enumerate(nodes[:5], start=1):
        text = node.get_text(' ', strip=True)
        print(f"  [{i}] {text}")

print("\n=== RAW TEXT SNIPPET ===")
full_text = soup.get_text(" ", strip=True)
print(full_text[:3000])
