from pathlib import Path
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
html_path = BASE_DIR / "debug_loggedin_post.html"

if not html_path.exists():
    raise FileNotFoundError(f"Не найден файл: {html_path}")

html = html_path.read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "lxml")

print("=== URL CHECK ===")
for tag in soup.find_all(["a", "iframe"]):
    attrs = " ".join(str(v) for v in tag.attrs.values()).lower()
    if any(x in attrs for x in ["comment", "comments", "reply", "replies", "discussion"]):
        print(str(tag)[:1000])

print("=== TEXT CHECK ===")
full_text = soup.get_text(" ", strip=True)
for needle in ["comment", "comments", "reply", "replies", "discussion"]:
    if needle in full_text.lower():
        print(f"FOUND_TEXT: {needle}")

print("=== HTML SNIPPETS ===")
count = 0
for line in html.splitlines():
    low = line.lower()
    if any(x in low for x in ["comment", "comments", "reply", "replies", "discussion"]):
        print(line[:1000])
        count += 1
        if count >= 50:
            break

print("=== DONE ===")
