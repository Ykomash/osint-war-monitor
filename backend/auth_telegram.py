"""Run this once to authenticate your Telegram session."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    from telethon import TelegramClient
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_path = str(__import__('pathlib').Path(__file__).parent / "data" / "telegram")

    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()  # will prompt for phone + OTP interactively
    print("✓ Telegram session saved. You can now start the server normally.")
    await client.disconnect()

asyncio.run(main())
