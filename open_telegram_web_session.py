from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "playwright_telegram_profile"


def main():
    PROFILE_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 960},
        )

        page = context.new_page()
        page.goto("https://web.telegram.org", wait_until="domcontentloaded", timeout=60000)
        print("Открыл Telegram Web.")
        print("Войди в аккаунт вручную.")
        print("Когда полностью войдешь и увидишь чаты, вернись в терминал и нажми Enter.")

        input()

        page.screenshot(path=str(BASE_DIR / "telegram_web_logged_in.png"), full_page=True)
        print(f"Профиль сохранен в: {PROFILE_DIR}")
        print("Скрин сохранен: telegram_web_logged_in.png")

        context.close()


if __name__ == "__main__":
    main()
