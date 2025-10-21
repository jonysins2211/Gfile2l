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

bot = Client("gofile_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# ============ HELPERS ============
def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"


async def progress(current, total, message, status_message, start_time, file_name):
    now = time.time()
    diff = now - start_time or 1
    percentage = current * 100 / total
    speed = current / diff
    eta = (total - current) / speed
    progress_str = "⫷{0}{1}⫸".format(
        ''.join(["●" for _ in range(int(percentage // 10))]),
        ''.join(["○" for _ in range(10 - int(percentage // 10))])
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
    """Pick the least-loaded GoFile server for max speed"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.gofile.io/servers", timeout=10) as resp:
                data = await resp.json()
                servers = data['data']['servers']
                best = sorted(servers, key=lambda s: s.get('load', 9999))[0]['name']
                logger.info(f"✅ Selected server: {best}")
                return best
    except Exception as e:
        logger.error(f"Error fetching servers: {e}")
        return "store1"  # fallback


# ============ UPLOAD FUNCTION ============
async def upload_to_gofile(file_path):
    """Upload file to GoFile with retries, timeout & pooling"""
    filename = os.path.basename(file_path)
    server = await get_best_server()
    upload_url = f"https://{server}.gofile.io/uploadFile"

    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=900)  # 15 min max upload
    retries = 3

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                with open(file_path, 'rb') as f:
                    form = aiohttp.FormData()
                    form.add_field("file", f, filename=filename)

                    logger.info(f"Uploading {filename} → {upload_url} (attempt {attempt})")
                    async with session.post(upload_url, data=form) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            return result["data"]["downloadPage"]
                        else:
                            text = await resp.text()
                            logger.warning(f"⚠️ Upload failed (status {resp.status}): {text}")
        except asyncio.TimeoutError:
            logger.warning(f"⏳ Timeout during upload (attempt {attempt})")
        except Exception as e:
            logger.error(f"Upload error (attempt {attempt}): {e}")

        await asyncio.sleep(random.uniform(2, 5))

    raise Exception("Upload failed after 3 attempts.")


# ============ FILE HANDLER ============
@bot.on_message(filters.document | filters.video | filters.audio)
async def handle_file(client, message):
    file = message.document or message.video or message.audio
    file_name = file.file_name
    file_size = file.file_size

    status = await message.reply(
        f"📥 **Processing File**\n\n"
        f"📂 **Name:** `{file_name}`\n"
        f"📦 **Size:** `{human_readable_size(file_size)}`\n\n"
        "⚙️ Starting download..."
    )

    if file_size > 4 * 1024 * 1024 * 1024:
        await status.edit("❌ File too large. Limit is 4GB.")
        return

    start_time = time.time()
    file_path = await message.download(
        progress=progress, progress_args=(message, status, start_time, file_name)
    )

    await status.edit(
        f"📤 **Uploading to GoFile**\n\n"
        f"📂 **File:** `{file_name}`\n"
        f"📦 **Size:** `{human_readable_size(file_size)}`\n\n"
        "⏳ Please wait..."
    )

    try:
        link = await upload_to_gofile(file_path)
        await status.edit(
            f"✅ **Upload Complete!**\n\n"
            f"📂 **File:** `{file_name}`\n"
            f"📦 **Size:** `{human_readable_size(file_size)}`\n\n"
            f"🔗 **Download Link:** [Click Here]({link})\n\n"
            "🚀 Powered by @Opleech_WD",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download Now", url=link)],
                [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/Movie_Loverzz")]
            ])
        )
    except Exception as e:
        await status.edit(f"❌ Upload failed: `{e}`")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# ============ START & HELP ============
@bot.on_message(filters.command("start"))
async def start(client, message):
    image_url = "https://graph.org/file/4e8a1172e8ba4b7a0bdfa.jpg"
    caption = (
        "**Welcome to GoFile Uploader Bot!**\n\n"
        "Send any file (video, audio, or document) and I'll upload it to GoFile.\n\n"
        "⚡ Max file size: 4GB\n"
        "✅ Fast & Free\n\n"
        "__Powered by @Movie_Loverzz__"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/Movie_loverzz")],
        [InlineKeyboardButton("🤖 How to Use", callback_data="help")]
    ])

    await message.reply_photo(photo=image_url, caption=caption, reply_markup=keyboard)


@bot.on_callback_query(filters.regex("^help$"))
async def help_callback(client, callback_query):
    help_text = (
        "**📚 GoFile Uploader Bot Help**\n\n"
        "1. Upload files up to 4GB (videos, audios, documents)\n"
        "2. Real-time progress & ETA shown\n"
        "3. Fastest GoFile server selected automatically\n"
        "4. Retries upload if stuck or timed out\n\n"
        "⚠️ Files inactive for 10 days auto-delete (GoFile policy)\n\n"
        "🚀 Powered by @Opleech_WD"
    )

    await callback_query.message.edit(
        text=help_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")],
            [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/movie_Loverzz")]
        ]),
        disable_web_page_preview=True
    )


@bot.on_callback_query(filters.regex("^back_to_start$"))
async def back_to_start(client, callback_query):
    image_url = "https://graph.org/file/4e8a1172e8ba4b7a0bdfa.jpg"
    caption = (
        "**Welcome to GoFile Uploader Bot!**\n\n"
        "Send any file (video, audio, or document) and I'll upload it to GoFile.\n\n"
        "⚡ Max file size: 4GB\n"
        "✅ Fast & Free\n\n"
        "__Powered by @Movie_Loverzz__"
    )
    await callback_query.message.delete()
    await callback_query.message.reply_photo(
        photo=image_url,
        caption=caption,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/Opleech_WD")],
            [InlineKeyboardButton("🤖 How to Use", callback_data="help")]
        ])
    )


# ============ FLASK KEEP ALIVE ============
def run():
    app = Flask(__name__)

    @app.route('/')
    def home():
        return 'Bot is alive!'

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


Thread(target=run).start()

# ============ START BOT ============
logger.info("🚀 GoFile Uploader Bot started successfully!")
bot.run()
