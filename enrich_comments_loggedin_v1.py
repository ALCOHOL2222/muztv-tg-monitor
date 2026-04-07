import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PROFILE_DIR = BASE_DIR / "playwright_telegram_profile"

CHANNEL_OFFSET = 4294967296


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


def normalize_post_url(url: str) -> str:
    return str(url or "").strip()


def extract_post_id(post_url: str) -> int:
    m = re.search(r"^https://t\.me/([^/]+)/([0-9]+)$", normalize_post_url(post_url))
    if not m:
        raise ValueError(f"Не удалось вытащить post_id из ссылки: {post_url}")
    return int(m.group(2))


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
def get_comments_count_from_html(html: str, target_post_id: int) -> int:
    soup = BeautifulSoup(html, "lxml")

    for node in soup.select("replies-element"):
        text = node.get_text(" ", strip=True)
        nums = re.findall(r'[\d.,]+[KMB]?', text, flags=re.I)
        comments_count = parse_metric_text(nums[0]) if nums else 0

        bubble = node
        while bubble is not None:
            classes = bubble.attrs.get("class", [])
            if isinstance(classes, str):
                classes = [classes]
            if bubble.name == "div" and "bubble" in classes:
                break
            bubble = bubble.parent

        if bubble is None:
            continue

        data_mid = bubble.get("data-mid")
        if not data_mid:
            continue

        try:
            msg_id = int(data_mid) - CHANNEL_OFFSET
        except Exception:
            continue

        if msg_id == target_post_id:
            return comments_count

    return 0


def save_progress(df: pd.DataFrame, path_xlsx: Path, path_csv: Path):
    df.to_excel(path_xlsx, index=False)
    df.to_csv(path_csv, index=False, encoding="utf-8-sig")
def main():
    archive_path = find_archive_file()
    print(f"ARCHIVE: {archive_path}")

    df = load_archive(archive_path)

    out_xlsx = OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact_comments_loggedin.xlsx"
    out_csv = OUTPUT_DIR / "tg_muztv_archive_period_enriched_exact_comments_loggedin.csv"

    if out_xlsx.exists():
        print(f"RESUME_FROM: {out_xlsx}")
        existing = pd.read_excel(out_xlsx)

        if "post_url" in existing.columns:
            existing_map = existing.set_index("post_url").to_dict(orient="index")

            if "processed_comments" not in df.columns:
                df["processed_comments"] = False

            for idx, row in df.iterrows():
                post_url = str(row.get("post_url", "") or "").strip()
                if post_url in existing_map:
                    old = existing_map[post_url]
                    df.at[idx, "comments_visible"] = int(old.get("comments_visible", row.get("comments_visible", 0)) or 0)
                    df.at[idx, "processed_comments"] = bool(old.get("processed_comments", False))
    else:
        if "processed_comments" not in df.columns:
            df["processed_comments"] = False

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 960},
        )

        page = context.new_page()
        total = len(df)
        processed_now = 0

        for idx, row in df.iterrows():
            if bool(row.get("processed_comments", False)):
                continue

            post_url = normalize_post_url(row.get("post_url", ""))
            if not post_url:
                continue

            try:
                target_post_id = extract_post_id(post_url)
            except Exception as e:
                print(f"[{idx+1}/{total}] SKIP bad url: {post_url} | {e}")
                df.at[idx, "processed_comments"] = True
                continue

            print(f"[{idx+1}/{total}] {post_url}")

            try:
                page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3500)

                html = page.content()
                comments_count = get_comments_count_from_html(html, target_post_id)

                df.at[idx, "comments_visible"] = int(comments_count or 0)
                df.at[idx, "processed_comments"] = True

                print(f"  comments_visible = {int(comments_count or 0)}")

            except Exception as e:
                print(f"  ERROR: {e}")
                df.at[idx, "processed_comments"] = False

            processed_now += 1

            if processed_now % 25 == 0:
                save_progress(df, out_xlsx, out_csv)
                print(f"AUTOSAVED at {processed_now} new rows")

        save_progress(df, out_xlsx, out_csv)
        print("FINAL_SAVE_DONE")

        context.close()

    print("ГОТОВО.")
    print(f"Файлы:")
    print(f" - {out_xlsx}")
    print(f" - {out_csv}")


if __name__ == "__main__":
    main()
