import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup

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


def parse_metric_text(value: str) -> int:
    raw = (value or "").replace("\xa0", " ").strip().upper().replace(",", ".")
    if not raw:
        return 0

    mult = 1
    if raw.endswith("K"):
        mult = 1000
        raw = raw[:-1]
    elif raw.endswith("M"):
        mult = 1000000
        raw = raw[:-1]
    elif raw.endswith("B"):
        mult = 1000000000
        raw = raw[:-1]

    raw = re.sub(r"[^\d.]", "", raw)
    if not raw:
        return 0

    try:
        return int(round(float(raw) * mult))
    except Exception:
        return 0
def main():
    post_url = input("Ссылка на пост: ").strip()
    public_url = normalize_public_post_url(post_url)

    print(f"PUBLIC_URL: {public_url}")

    m = re.search(r"https://t\.me/(?:s/)?([^/]+)/(\d+)", post_url)
    if not m:
        raise ValueError("Не удалось вытащить channel/post_id из ссылки")

    channel = m.group(1)
    post_id = m.group(2)
    data_post_value = f"{channel}/{post_id}"

    response = requests.get(public_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    html = response.text
    soup = BeautifulSoup(html, "lxml")

    blocks = soup.select("div.tgme_widget_message")
    print(f"BLOCKS_FOUND: {len(blocks)}")

    target_block = None
    for block in blocks:
        if block.get("data-post") == data_post_value:
            target_block = block
            break

    if target_block is None:
        raise ValueError(f"Не найден точный блок поста: {data_post_value}")

    views = 0
    likes = 0

    view_node = target_block.select_one(".tgme_widget_message_views")
    if view_node:
        views = parse_metric_text(view_node.get_text(" ", strip=True))

    reactions_node = target_block.select_one(".tgme_widget_message_reactions")
    if reactions_node:
        nums = re.findall(r'[\d.,]+[KMB]?', reactions_node.get_text(" ", strip=True), flags=re.I)
        likes = sum(parse_metric_text(x) for x in nums)

    out_path = BASE_DIR / "debug_exact_post_block.html"
    out_path.write_text(str(target_block), encoding="utf-8")

    print(f"DATA_POST: {data_post_value}")
    print(f"VIEWS: {views}")
    print(f"LIKES_SUM: {likes}")
    print(f"BLOCK_SAVED: {out_path}")


if __name__ == "__main__":
    main()
