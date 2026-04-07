import re
import asyncio
from telethon import TelegramClient

def extract_post_parts(post_url: str):
    m = re.search(r"^https://t\.me/([^/]+)/([0-9]+)$", str(post_url or "").strip())
    if not m:
        raise ValueError("Нужна ссылка вида https://t.me/channel/12345")
    return m.group(1), int(m.group(2))


async def main():
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()
    phone = input("phone (в формате +7...): ").strip()
    post_url = input("post_url: ").strip()

    channel_username, post_id = extract_post_parts(post_url)

    client = TelegramClient("muztv_user_session", api_id, api_hash)

    await client.start(phone=phone)

    channel = await client.get_entity(channel_username)

    count = 0
    async for _ in client.iter_messages(channel, reply_to=post_id):
        count += 1

    print(f"COMMENTS_COUNT: {count}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
