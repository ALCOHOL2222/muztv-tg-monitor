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


def find_matches_file() -> Path:
    candidates = [
        OUTPUT_DIR / "tg_artist_matches_v3.xlsx",
        OUTPUT_DIR / "tg_artist_matches_v3.csv",
        OUTPUT_DIR / "tg_artist_matches_v2.xlsx",
        OUTPUT_DIR / "tg_artist_matches_v2.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Не найден файл совпадений. Сначала запусти search_artist_v3.py.")


def load_matches(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)
def fetch_html(url: str, session: requests.Session) -> str:
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def extract_post_metrics_from_html(html: str):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    views = 0
    likes_visible = 0
    comments_visible = 0
    reposts_visible = 0

    view_node = soup.select_one(".tgme_widget_message_views")
    if view_node:
        views = parse_metric_text(view_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+views', text, flags=re.I)
        if m:
            views = parse_metric_text(m.group(1))

    reply_node = soup.select_one(".tgme_widget_message_replies")
    if reply_node:
        comments_visible = parse_metric_text(reply_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+(comments|comment|replies|reply)', text, flags=re.I)
        if m:
            comments_visible = parse_metric_text(m.group(1))

    reaction_nodes = soup.select(".tgme_widget_message_reactions, .tgme_widget_message_reaction")
    if reaction_nodes:
        total = 0
        for node in reaction_nodes:
            nums = re.findall(r'[\d.,]+[KMB]?', node.get_text(" ", strip=True), flags=re.I)
            for num in nums:
                total += parse_metric_text(num)
        likes_visible = total
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+(reactions|reaction|likes|like)', text, flags=re.I)
        if m:
            likes_visible = parse_metric_text(m.group(1))

    forward_node = soup.select_one(".tgme_widget_message_forwards")
    if forward_node:
        reposts_visible = parse_metric_text(forward_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+(forwards|forwarded|shares|share)', text, flags=re.I)
        if m:
            reposts_visible = parse_metric_text(m.group(1))

    return {
        "views": views,
        "likes_visible": likes_visible,
        "comments_visible": comments_visible,
        "reposts_visible": reposts_visible,
    }
def main():
    matches_path = find_matches_file()
    print(f"Файл совпадений: {matches_path}")

    df = load_matches(matches_path)

    if df.empty:
        print("Файл совпадений пустой.")
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
            metrics = extract_post_metrics_from_html(html)
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
            "artist_name": row.get("artist_name", ""),
            "matched_alias": row.get("matched_alias", ""),
            "post_id": row.get("post_id", ""),
            "post_url": post_url,
            "published_at": row.get("published_at", ""),
            "post_text": row.get("post_text", ""),
            "views": int(metrics.get("views", 0) or 0),
            "likes_visible": int(metrics.get("likes_visible", 0) or 0),
            "comments_visible": int(metrics.get("comments_visible", 0) or 0),
            "reposts_visible": int(metrics.get("reposts_visible", 0) or 0),
            "page_number": row.get("page_number", ""),
        })

        time.sleep(0.4)

    result_df = pd.DataFrame(enriched_rows)

    out_csv = OUTPUT_DIR / "tg_artist_matches_enriched.csv"
    out_xlsx = OUTPUT_DIR / "tg_artist_matches_enriched.xlsx"

    result_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    result_df.to_excel(out_xlsx, index=False)

    print("\nГОТОВО.")
    print(f"Обработано постов: {len(result_df)}")
    print("Файлы:")
    print(f" - {out_csv}")
    print(f" - {out_xlsx}")


if __name__ == "__main__":
    main()
