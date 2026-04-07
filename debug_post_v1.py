import requests
from pathlib import Path

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

    if url.startswith("https://t.me/"):
        parts = url.replace("https://t.me/", "").split("/")
        if len(parts) >= 2:
            channel = parts[0]
            post_id = parts[1]
            return f"https://t.me/s/{channel}/{post_id}?single"

    return url


def main():
    post_url = input("Ссылка на пост: ").strip()
    public_url = normalize_public_post_url(post_url)

    print(f"PUBLIC_URL: {public_url}")

    response = requests.get(public_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    html = response.text

    out_path = BASE_DIR / "debug_post_24876.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"HTML_SAVED: {out_path}")


if __name__ == "__main__":
    main()
