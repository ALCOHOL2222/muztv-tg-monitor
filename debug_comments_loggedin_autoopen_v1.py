import re
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "playwright_telegram_profile"
CHANNEL_OFFSET = 4294967296


def extract_post_id(post_url: str) -> int:
    m = re.search(r"^https://t\.me/([^/]+)/([0-9]+)$", str(post_url or "").strip())
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


def try_click(page, texts):
    for txt in texts:
        locator = page.get_by_text(txt, exact=False)
        try:
            if locator.count() > 0:
                locator.first.click(timeout=3000)
                page.wait_for_timeout(3000)
                return txt
        except Exception:
            pass
    return None


def main():
    post_url = input("Ссылка на пост: ").strip()
    target_post_id = extract_post_id(post_url)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 960},
        )

        page = context.new_page()
        page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        clicked = try_click(page, [
            "Open in Web",
            "OPEN IN WEB",
            "View in Channel",
            "VIEW IN CHANNEL",
            "Open",
            "OPEN",
        ])

        if clicked:
            print(f"CLICKED: {clicked}")
            page.wait_for_timeout(5000)
        else:
            print("CLICKED: NONE")

        html = page.content()
        (BASE_DIR / "debug_comments_loggedin_autoopen.html").write_text(html, encoding="utf-8")

        comments_count = get_comments_count_from_html(html, target_post_id)

        print(f"COMMENTS_COUNT: {comments_count}")

        context.close()


if __name__ == "__main__":
    main()
