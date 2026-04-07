import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
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


def clean_text_from_html(fragment: str) -> str:
    if not fragment:
        return ""
    soup = BeautifulSoup(fragment, "lxml")
    text = soup.get_text("\n", strip=True)
    text = unescape(text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def get_next_page_url(html: str):
    match = re.search(r'<link rel="prev" href="([^"]+)"', html, flags=re.I)
    if not match:
        return None

    href = match.group(1).strip()
    if not href:
        return None

    if href.startswith("http"):
        return href

    return "https://t.me" + href
def extract_visible_metrics_from_block(block_html: str):
    soup = BeautifulSoup(block_html, "lxml")
    block_text = soup.get_text(" ", strip=True)

    views = 0
    comments_visible = 0
    likes_visible = 0
    reposts_visible = 0

    view_node = soup.select_one(".tgme_widget_message_views")
    if view_node:
        views = parse_metric_text(view_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+views', block_text, flags=re.I)
        if m:
            views = parse_metric_text(m.group(1))

    # Комментарии / replies
    reply_node = soup.select_one(".tgme_widget_message_replies")
    if reply_node:
        comments_visible = parse_metric_text(reply_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+(comments|comment|replies|reply)', block_text, flags=re.I)
        if m:
            comments_visible = parse_metric_text(m.group(1))

    # Репосты / shares / forwards
    share_node = soup.select_one(".tgme_widget_message_forwarded_from, .tgme_widget_message_forwards")
    if share_node:
        reposts_visible = parse_metric_text(share_node.get_text(" ", strip=True))
    else:
        m = re.search(r'([\d.,]+[KMB]?)\s+(shares|share|forwards|forwarded)', block_text, flags=re.I)
        if m:
            reposts_visible = parse_metric_text(m.group(1))

    # Реакции / likes
    reaction_nodes = soup.select(".tgme_widget_message_reactions, .tgme_widget_message_reaction")
    if reaction_nodes:
        total = 0
        for node in reaction_nodes:
            nums = re.findall(r'[\d.,]+[KMB]?', node.get_text(" ", strip=True), flags=re.I)
            for num in nums:
                total += parse_metric_text(num)
        likes_visible = total
    else:
        # запасной вариант: берем первое число рядом со словом reactions / likes
        m = re.search(r'([\d.,]+[KMB]?)\s+(reactions|reaction|likes|like)', block_text, flags=re.I)
        if m:
            likes_visible = parse_metric_text(m.group(1))

    return {
        "views": views,
        "comments_visible": comments_visible,
        "likes_visible": likes_visible,
        "reposts_visible": reposts_visible,
    }


def extract_posts_from_html(html: str, channel_name: str, page_number: int):
    prepared = html or ""
    prepared = prepared.replace('\\"', '"').replace("\\/", "/")

    blocks = re.split(r'<div class=\"tgme_widget_message\b', prepared, flags=re.I)[1:]
    posts = []

    for part in blocks:
        block = '<div class="tgme_widget_message ' + part

        data_post_match = re.search(r'data-post="([^"/]+)/(\d+)"', block, flags=re.I)
        if data_post_match:
            channel_from_block = data_post_match.group(1)
            post_id = data_post_match.group(2)
            post_url = f"https://t.me/{channel_from_block}/{post_id}"
        else:
            post_url_match = re.search(r'href="(https://t\\.me/([^"/]+)/(\d+))"', block, flags=re.I)
            if not post_url_match:
                continue
            post_url = post_url_match.group(1)
            channel_from_block = post_url_match.group(2)
            post_id = post_url_match.group(3)

        published_at = None
        time_match = re.search(r'datetime="([^"]+)"', block, flags=re.I)
        if time_match:
            published_at = time_match.group(1)

        text_match = re.search(r'<div class="tgme_widget_message_text[^"]*">([\s\S]*?)</div>', block, flags=re.I)
        post_text = clean_text_from_html(text_match.group(1)) if text_match else ""

        visible = extract_visible_metrics_from_block(block)

        posts.append({
            "source": "telegram",
            "channel_name": channel_name or channel_from_block,
            "post_id": post_id,
            "post_url": post_url,
            "published_at": published_at,
            "post_text": post_text,
            "views": visible["views"],
            "likes_visible": visible["likes_visible"],
            "comments_visible": visible["comments_visible"],
            "reposts_visible": visible["reposts_visible"],
            "page_number": page_number,
            "raw_html": block,
        })

    return posts
def main():
    channel_name = input("Канал Telegram (по умолчанию muztv): ").strip() or "muztv"
    date_from_raw = input("Дата с (YYYY-MM-DD): ").strip()
    date_to_raw = input("Дата по (YYYY-MM-DD): ").strip()
    max_pages_raw = input("Максимум страниц архива (например 300): ").strip() or "300"

    date_from = datetime.fromisoformat(date_from_raw).replace(tzinfo=timezone.utc)
    date_to = datetime.fromisoformat(date_to_raw).replace(tzinfo=timezone.utc)

    try:
        max_pages = max(1, int(max_pages_raw))
    except Exception:
        max_pages = 300

    session = requests.Session()
    next_url = f"https://t.me/s/{channel_name}"

    all_posts = []
    seen_urls = set()

    print("\\nНачинаю сбор архива v2...")

    for page_number in range(1, max_pages + 1):
        print(f"[{page_number}] GET {next_url}")

        try:
            response = session.get(next_url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            print(f"ОШИБКА загрузки страницы: {e}")
            break

        posts = extract_posts_from_html(html, channel_name, page_number)
        if not posts:
            print("На странице не найдено постов. Останавливаюсь.")
            break

        new_posts = 0
        oldest_date_on_page = None

        for post in posts:
            if post["post_url"] in seen_urls:
                continue
            seen_urls.add(post["post_url"])
            new_posts += 1

            published_at_raw = post.get("published_at")
            if published_at_raw:
                try:
                    published_dt = datetime.fromisoformat(
                        published_at_raw.replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                    if oldest_date_on_page is None or published_dt < oldest_date_on_page:
                        oldest_date_on_page = published_dt
                except Exception:
                    pass

            all_posts.append(post)

        print(f"  найдено новых постов: {new_posts}")

        if oldest_date_on_page:
            print(f"  самая старая дата на странице: {oldest_date_on_page.isoformat()}")

        if oldest_date_on_page and oldest_date_on_page < date_from:
            print("Дошли до даты раньше нужной. Останавливаюсь.")
            break

        next_candidate = get_next_page_url(html)
        if not next_candidate:
            print("Следующая страница не найдена. Останавливаюсь.")
            break

        next_url = next_candidate
        time.sleep(0.35)

    if not all_posts:
        print("\\nПосты не собраны.")
        return

    df = pd.DataFrame(all_posts)

    df["published_at_dt"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    filtered_df = df[
        (df["published_at_dt"].notna()) &
        (df["published_at_dt"] >= pd.Timestamp(date_from)) &
        (df["published_at_dt"] <= pd.Timestamp(date_to.replace(hour=23, minute=59, second=59)))
    ].copy()
    raw_csv = DATA_DIR / f"tg_{channel_name}_archive_raw_v2.csv"
    raw_xlsx = DATA_DIR / f"tg_{channel_name}_archive_raw_v2.xlsx"
    period_csv = OUTPUT_DIR / f"tg_{channel_name}_archive_period_v2.csv"
    period_xlsx = OUTPUT_DIR / f"tg_{channel_name}_archive_period_v2.xlsx"

    df.drop(columns=["published_at_dt"], errors="ignore").to_csv(raw_csv, index=False, encoding="utf-8-sig")
    df.drop(columns=["published_at_dt"], errors="ignore").to_excel(raw_xlsx, index=False)

    filtered_df.drop(columns=["published_at_dt"], errors="ignore").to_csv(period_csv, index=False, encoding="utf-8-sig")
    filtered_df.drop(columns=["published_at_dt"], errors="ignore").to_excel(period_xlsx, index=False)

    newest_post = df["published_at"].dropna().max() if "published_at" in df.columns else None
    oldest_post = df["published_at"].dropna().min() if "published_at" in df.columns else None

    print("\\nГОТОВО.")
    print(f"Всего уникальных постов собрано: {len(df)}")
    print(f"Постов в выбранном периоде: {len(filtered_df)}")
    print(f"Самый новый пост: {newest_post}")
    print(f"Самый старый пост: {oldest_post}")
    print("Файлы:")
    print(f" - {raw_csv}")
    print(f" - {raw_xlsx}")
    print(f" - {period_csv}")
    print(f" - {period_xlsx}")


if __name__ == "__main__":
    main()
