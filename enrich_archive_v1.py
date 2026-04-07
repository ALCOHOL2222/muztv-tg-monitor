import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}


def parse_metric_text(value: str) -> int:
    raw = (value or "").replace("\xa0", " ").strip().upper().replace(",", ".")
    if not raw:
        return 0

    multiplier = 1
    if raw.endswith("K"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("M"):
        multiplier = 1_000_000
        raw = raw[:-1]
    elif raw.endswith("B"):
        multiplier = 1_000_000_000
        raw = raw[:-1]

    raw = re.sub(r"[^\d.]", "", raw)
    if not raw:
        return 0

    try:
        return int(round(float(raw) * multiplier))
    except Exception:
        return 0


def find_archive_file() -> Path:
    candidates = [
        OUTPUT_DIR / "tg_muztv_archive_period_v2.xlsx",
        OUTPUT_DIR / "tg_muztv_archive_period_v2.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Не найден архив v2. Сначала запусти collect_archive_v2.py.")


def load_archive(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)
def normalize_public_post_url(url: str) -> str:
    url = str(url or "").strip()

    m = re.match(r"^https://t\.me/([^/]+)/([0-9]+)$", url)
    if m:
        return f"https://t.me/s/{m.group(1)}/{m.group(2)}?single"

    m = re.match(r"^https://t\.me/s/([^/]+)/([0-9]+)$", url)
    if m:
        return f"https://t.me/s/{m.group(1)}/{m.group(2)}?single"

    return url


def fetch_html(url: str, session: requests.Session) -> str:
    public_url = normalize_public_post_url(url)
    last_error = None

    for timeout_value in (20, 30, 40):
        try:
            response = session.get(public_url, headers=HEADERS, timeout=timeout_value)
            response.raise_for_status()
            return response.text
        except Exception as e:
            last_error = e
            time.sleep(1.2)

    raise last_error


def extract_post_metrics_from_html(html: str, post_url: str):
    soup = BeautifulSoup(html, "lxml")

    m = re.search(r"https://t\.me/(?:s/)?([^/]+)/([0-9]+)", str(post_url or ""))
    if not m:
        return {
            "views": 0,
            "likes_visible": 0,
            "comments_visible": 0,
            "reposts_visible": 0,
        }

    channel = m.group(1)
    post_id = m.group(2)
    data_post_value = f"{channel}/{post_id}"

    target_block = None
    for block in soup.select("div.tgme_widget_message"):
        if block.get("data-post") == data_post_value:
            target_block = block
            break

    if target_block is None:
        target_block = soup

    block_text = target_block.get_text(" ", strip=True)

    views = 0
    likes_visible = 0
    comments_visible = 0
    reposts_visible = 0

    view_node = target_block.select_one(".tgme_widget_message_views")
    if view_node:
        views = parse_metric_text(view_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+views', block_text, flags=re.I)
        if m:
            views = parse_metric_text(m.group(1))

    reactions_node = target_block.select_one(".tgme_widget_message_reactions")
    if reactions_node:
        nums = re.findall(r'[\d.,]+[KMB]?', reactions_node.get_text(" ", strip=True), flags=re.I)
        likes_visible = sum(parse_metric_text(x) for x in nums)
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+(reactions|reaction|likes|like)', block_text, flags=re.I)
        if m:
            likes_visible = parse_metric_text(m.group(1))

    reply_node = target_block.select_one(".tgme_widget_message_replies")
    if reply_node:
        comments_visible = parse_metric_text(reply_node.get_text(" ", strip=True))
    else:
        comments_visible = 0

    forward_node = target_block.select_one(".tgme_widget_message_forwards")
    if forward_node:
        reposts_visible = parse_metric_text(forward_node.get_text(" ", strip=True))
    else:
        reposts_visible = 0

    return {
        "views": views,
        "likes_visible": likes_visible,
        "comments_visible": comments_visible,
        "reposts_visible": reposts_visible,
    }
def main():
    archive_path = find_archive_file()
    print(f"Архив: {archive_path}")

    df = load_archive(archive_path)

    if df.empty:
        print("Архив пустой.")
        return

    session = requests.Session()
    enriched_rows = []

    total = len(df)

    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        post_url = str(row.get("post_url", "") or "").strip()
        if not post_url:
            continue

        print(f"[{idx}/{total}] {post_url}")

        try:
            html = fetch_html(post_url, session)
            metrics = extract_post_metrics_from_html(html, post_url)
        except Exception as e:
            print(f"  ОШИБКА: {e}")
            metrics = {
                "views": int(row.get("views", 0) or 0),
                "likes_visible": int(row.get("likes_visible", 0) or 0),
                "comments_visible": int(row.get("comments_visible", 0) or 0),
                "reposts_visible": int(row.get("reposts_visible", 0) or 0),
            }

        enriched_rows.append({
            "source": row.get("source", "telegram"),
            "channel_name": row.get("channel_name", "muztv"),
            "post_id": row.get("post_id", ""),
            "post_url": post_url,
            "published_at": row.get("published_at", ""),
            "post_text": row.get("post_text", ""),
            "views": int(metrics.get("views", 0) or 0),
            "likes_visible": int(metrics.get("likes_visible", 0) or 0),
            "comments_visible": int(metrics.get("comments_visible", 0) or 0),
            "reposts_visible": int(metrics.get("reposts_visible", 0) or 0),
            "page_number": row.get("page_number", ""),
            "raw_html": row.get("raw_html", ""),
        })

        time.sleep(0.4)

    result_df = pd.DataFrame(enriched_rows)

    out_csv = OUTPUT_DIR / "tg_muztv_archive_period_enriched.csv"
    out_xlsx = OUTPUT_DIR / "tg_muztv_archive_period_enriched.xlsx"

    result_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    result_df.to_excel(out_xlsx, index=False)

    print("\nГОТОВО.")
    print(f"Обработано постов: {len(result_df)}")
    print("Файлы:")
    print(f" - {out_csv}")
    print(f" - {out_xlsx}")


if __name__ == "__main__":
    main()
