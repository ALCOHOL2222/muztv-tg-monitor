from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "playwright_telegram_profile"


def main():
    post_url = input("Ссылка на пост: ").strip()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 960},
        )

        page = context.new_page()
        page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        print("Пост открыт.")
        print("Если есть кнопка OPEN IN WEB / VIEW IN CHANNEL — нажми ее вручную.")
        print("Если откроется обсуждение или станет видно счетчик комментариев, вернись в терминал и нажми Enter.")

        input()

        html = page.content()
        (BASE_DIR / "debug_loggedin_post.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(BASE_DIR / "debug_loggedin_post.png"), full_page=True)

        print("Сохранено:")
        print(" - debug_loggedin_post.html")
        print(" - debug_loggedin_post.png")

        context.close()


if __name__ == "__main__":
    main()
