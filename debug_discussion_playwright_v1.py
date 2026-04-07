import re
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent


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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(public_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        html = page.content()
        out_path = BASE_DIR / "debug_discussion_playwright.html"
        out_path.write_text(html, encoding="utf-8")

        print(f"HTML_SAVED: {out_path}")

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
            if any(pat in lower for pat in patterns):
                snippet = line.strip()
                if snippet:
                    print(snippet[:1000])
                    found += 1
                if found >= 60:
                    break
        print("MATCHES_END")

        browser.close()


if __name__ == "__main__":
    main()
