import os
import random
import asyncio
import aiohttp
import logging
import time
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# ============ CONFIG ============
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("API_ID, API_HASH, and BOT_TOKEN must be set.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Client(
    "gofile_uploader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ============ HELPERS ============
def human_readable_size(size, decimal_places=2):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024
    return f"{size:.{decimal_places}f} PB"


async def progress(current, total, message, status_message, start_time, file_name):
    now = time.time()
    diff = now - start_time or 1
    percentage = current * 100 / total
    speed = current / diff
    eta = (total - current) / speed if speed > 0 else 0

    progress_str = "⫷{}{}⫸".format(
        "●" * int(percentage // 10),
        "○" * (10 - int(percentage // 10))
    )

    text = (
        f"**📂 File:** `{file_name}`\n"
        f"**📦 Size:** `{human_readable_size(total)}`\n\n"
        f"**⬇️ Downloading...**\n"
        f"{progress_str} `{percentage:.2f}%`\n"
        f"**⚡ Speed:** `{human_readable_size(speed)}/s`\n"
        f"**⏱️ ETA:** `{int(eta)}s`"
    )

    try:
        await status_message.edit(text)
    except:
        pass


# ============ SERVER FETCH ============
async def get_best_server():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.gofile.io/servers", timeout=10) as resp:
                data = await resp.json()
                servers = data["data"]["servers"]
                best = min(servers, key=lambda s: s.get("load", 9999))["name"]
                logger.info(f"✅ Selected server: {best}")
                return best
    except Exception as e:
        logger.error(f"Server fetch error: {e}")
        return "store1"


# ============ UPLOAD ============
async def upload_to_gofile(file_path):
    filename = os.path.basename(file_path)
    server = await get_best_server()
    upload_url = f"https://{server}.gofile.io/uploadFile"

    timeout = aiohttp.ClientTimeout(total=900)
    retries = 3

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                with open(file_path, "rb") as f:
                    form = aiohttp.FormData()
                    form.add_field("file", f, filename=filename)

                    logger.info(f"Uploading {filename} (attempt {attempt})")
                    async with session.post(upload_url, data=form) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["data"]["downloadPage"]
                        else:
                            logger.warning(await resp.text())
        except Exception as e:
            logger.error(f"Upload attempt {attempt} failed: {e}")

        await asyncio.sleep(random.uniform(2, 5))

    raise Exception("Upload failed after retries")


# ============ FILE HANDLER ============
@bot.on_message(filters.document | filters.video | filters.audio)
async def handle_file(_, message):
    file = message.document or message.video or message.audio
    file_name = file.file_name
    file_size = file.file_size

    if file_size > 4 * 1024 * 1024 * 1024:
        await message.reply("❌ File too large. Max 4GB.")
        return

    status = await message.reply(
        f"📂 `{file_name}`\n📦 `{human_readable_size(file_size)}`\n\n⬇️ Downloading..."
    )

    start_time = time.time()
    file_path = await message.download(
        progress=progress,
        progress_args=(message, status, start_time, file_name)
    )

    try:
        await status.edit("📤 Uploading to GoFile...")
        link = await upload_to_gofile(file_path)

        await status.edit(
            f"✅ **Upload Complete**\n\n"
            f"📂 `{file_name}`\n"
            f"📦 `{human_readable_size(file_size)}`\n\n"
            f"🔗 [Download Link]({link})",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download", url=link)]
            ])
        )
    except Exception as e:
        await status.edit(f"❌ Upload failed:\n`{e}`")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# ============ START ============
@bot.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "👋 **Welcome to GoFile Uploader Bot**\n\n"
        "📤 Send any file up to **4GB** and get a GoFile link instantly."
    )


# ============ FLASK KEEP-ALIVE ============
def start_flask():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "Bot is alive!"

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


# ============ MAIN ============
async def main():
    Thread(target=start_flask, daemon=True).start()
    await bot.start()
    logger.info("🚀 GoFile Uploader Bot started successfully!")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
