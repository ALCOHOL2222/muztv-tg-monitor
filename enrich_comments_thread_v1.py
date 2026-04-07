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


def find_archive_file() -> Path:
    candidates = [
        OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact.xlsx",
        OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Не найден enriched_exact архив.")


def load_archive(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)


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


def extract_comments_from_html(html: str, post_url: str) -> int:
    soup = BeautifulSoup(html, "lxml")

    m = re.search(r"https://t\.me/(?:s/)?([^/]+)/([0-9]+)", str(post_url or ""))
    if not m:
        return 0

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

    reply_node = target_block.select_one(".tgme_widget_message_replies")
    if reply_node:
        return parse_metric_text(reply_node.get_text(" ", strip=True))

    # запасные варианты по тексту
    patterns = [
        r'([\d.,]+[KMB]?)\s+(comments|comment)',
        r'([\d.,]+[KMB]?)\s+(replies|reply)',
        r'comments?\s*[:\-]?\s*([\d.,]+[KMB]?)',
        r'replies?\s*[:\-]?\s*([\d.,]+[KMB]?)',
    ]

    for pattern in patterns:
        mm = re.search(pattern, block_text, flags=re.I)
        if mm:
            value = mm.group(1) if mm.lastindex else ""
            return parse_metric_text(value)

    return 0
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


def extract_comments_from_html(html: str, post_url: str) -> int:
    soup = BeautifulSoup(html, "lxml")

    m = re.search(r"https://t\.me/(?:s/)?([^/]+)/([0-9]+)", str(post_url or ""))
    if not m:
        return 0

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

    reply_node = target_block.select_one(".tgme_widget_message_replies")
    if reply_node:
        return parse_metric_text(reply_node.get_text(" ", strip=True))

    # запасные варианты по тексту
    patterns = [
        r'([\d.,]+[KMB]?)\s+(comments|comment)',
        r'([\d.,]+[KMB]?)\s+(replies|reply)',
        r'comments?\s*[:\-]?\s*([\d.,]+[KMB]?)',
        r'replies?\s*[:\-]?\s*([\d.,]+[KMB]?)',
    ]

    for pattern in patterns:
        mm = re.search(pattern, block_text, flags=re.I)
        if mm:
            value = mm.group(1) if mm.lastindex else ""
            return parse_metric_text(value)

    return 0
def main():
    archive_path = find_archive_file()
    print(f"Архив: {archive_path}")

    df = load_archive(archive_path)

    if df.empty:
        print("Архив пустой.")
        return

    session = requests.Session()
    out_rows = []
    total = len(df)

    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        post_url = str(row.get("post_url", "") or "").strip()
        if not post_url:
            continue

        print(f"[{idx}/{total}] {post_url}")

        try:
            html = fetch_html(post_url, session)
            comments_visible = extract_comments_from_html(html, post_url)
        except Exception as e:
            print(f"  ОШИБКА: {e}")
            comments_visible = int(row.get("comments_visible", 0) or 0)

        out_rows.append({
            "source": row.get("source", "telegram"),
            "channel_name": row.get("channel_name", "muztv"),
            "post_id": row.get("post_id", ""),
            "post_url": post_url,
            "published_at": row.get("published_at", ""),
            "post_text": row.get("post_text", ""),
            "views": int(row.get("views", 0) or 0),
            "likes_visible": int(row.get("likes_visible", 0) or 0),
            "comments_visible": int(comments_visible or 0),
            "reposts_visible": int(row.get("reposts_visible", 0) or 0),
            "page_number": row.get("page_number", ""),
            "raw_html": row.get("raw_html", ""),
        })

        time.sleep(0.4)

    result_df = pd.DataFrame(out_rows)

    out_csv = OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact_comments.csv"
    out_xlsx = OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact_comments.xlsx"

    result_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    result_df.to_excel(out_xlsx, index=False)

    print("\nГОТОВО.")
    print(f"Обработано постов: {len(result_df)}")
    print("Файлы:")
    print(f" - {out_csv}")
    print(f" - {out_xlsx}")


if __name__ == "__main__":
    main()
