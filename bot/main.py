import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

from bot.agent import parse_request
from bot.api import app as api_app
from bot.database import init_db, save_job
from bot.searcher import search_clips

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
dp = Dispatcher()

UPLOAD_DIR = Path("data/uploads")


@dp.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    await msg.answer(
        "👁️ *Anime Editor*\n\n"
        "Пиши запрос:\n"
        "`aggressive edit kurumi` — найду клипы сам\n"
        "`smooth lofi rem` — другой стиль\n\n"
        "Или кидай видос с подписью — обработаю твои исходники\n\n"
        "Стили: `aggressive` `smooth` `dark` `lofi`",
        parse_mode="Markdown",
    )


@dp.message(F.video | F.document)
async def handle_video(msg: Message) -> None:
    caption = (msg.caption or "aggressive edit").strip()
    chat_id = msg.chat.id

    file_obj = msg.video or msg.document
    file = await bot.get_file(file_obj.file_id)

    save_dir = UPLOAD_DIR / str(chat_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    local_path = save_dir / Path(file.file_path).name
    await bot.download_file(file.file_path, local_path)

    job = parse_request(caption, chat_id)
    job.clip_urls = [f"local:{local_path.absolute()}"]
    save_job(job)

    await msg.answer(
        f"✅ Получил!\nJob `{job.id[:8]}`\nСтиль: `{job.style.value}`\n\nОтправил на телефон...",
        parse_mode="Markdown",
    )


@dp.message(F.audio | F.voice)
async def handle_music(msg: Message) -> None:
    await msg.answer(
        "🎵 Музыку получил! Чтобы прикрепить к эдиту — отправь её *вместе* с видео-исходниками одним сообщением (album).",
        parse_mode="Markdown",
    )


@dp.message()
async def handle_text(msg: Message) -> None:
    text = (msg.text or "").strip()
    if not text:
        return

    chat_id = msg.chat.id
    status_msg = await msg.answer("🔍 Ищу клипы...")

    job = parse_request(text, chat_id)

    if not job.character:
        await status_msg.edit_text(
            "❓ Не понял персонажа.\nПример: `aggressive edit Kurumi Tokisaki`",
            parse_mode="Markdown",
        )
        return

    urls = search_clips(job.character, job.style.value)
    if not urls:
        await status_msg.edit_text(
            f"😔 Не нашёл клипы для *{job.character}*. Попробуй уточнить.",
            parse_mode="Markdown",
        )
        return

    job.clip_urls = urls
    save_job(job)

    await status_msg.edit_text(
        f"✅ Нашёл {len(urls)} клипов для *{job.character}*\n"
        f"Стиль: `{job.style.value}` · Job `{job.id[:8]}`\n\n"
        "Рендерю на телефоне... ⚙️",
        parse_mode="Markdown",
    )


def _start_api() -> None:
    uvicorn.run(api_app, host="0.0.0.0", port=8080, log_level="warning")


async def main() -> None:
    init_db()
    threading.Thread(target=_start_api, daemon=True).start()
    log.info("Bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
