import re
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}

def normalize_public_post_url(url: str) -> str:
    url = str(url or "").strip()

    if url.startswith("https://t.me/s/"):
        if "?single" not in url:
            return url + ("&single" if "?" in url else "?single")
        return url

    m = re.match(r"^https://t\.me/([^/]+)/([0-9]+)$", url)
    if m:
        return f"https://t.me/s/{m.group(1)}/{m.group(2)}?single"

    return url

def main():
    post_url = input("Ссылка на пост: ").strip()
    public_url = normalize_public_post_url(post_url)

    print(f"PUBLIC_URL: {public_url}")

    response = requests.get(public_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    html = response.text

    out_html = BASE_DIR / "debug_discussion_source.html"
    out_html.write_text(html, encoding="utf-8")

    print(f"HTML_SAVED: {out_html}")

    patterns = [
        "discussion",
        "comment",
        "comments",
        "reply",
        "replies",
        "widget",
        "iframe",
    ]

    print("MATCHES_START")
    lines = html.splitlines()

    found = 0
    for line in lines:
        lower = line.lower()
        if any(p in lower for p in patterns):
            snippet = line.strip()
            if snippet:
                print(snippet[:800])
                found += 1
            if found >= 40:
                break

    print("MATCHES_END")

if __name__ == "__main__":
    main()
