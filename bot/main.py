import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Filter
from aiogram.types import Message
from dotenv import load_dotenv

from bot.agent import parse_request
from bot.api import app as api_app
from bot.database import init_db, save_job
from bot.music_analyzer import analyze_music
from bot.searcher import search_clips

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
dp = Dispatcher()

UPLOAD_DIR = Path("data/uploads")
OWNER_ID = 7485721661

_pending_music: dict[int, dict] = {}


class IsOwner(Filter):
    async def __call__(self, msg: Message) -> bool:
        return msg.from_user.id == OWNER_ID


@dp.message(CommandStart(), IsOwner())
async def cmd_start(msg: Message) -> None:
    await msg.answer(
        "👁️ *Anime Editor*\n\n"
        "Пиши запрос:\n"
        "`aggressive edit kurumi` — найду клипы сам\n"
        "`smooth 60fps rem` — фрейм-интерполяция\n"
        "`dark timeremap zero two` — тайм-ремап по BPM\n\n"
        "Или кидай аудио — Gemini найдёт лучший момент\n"
        "Затем пиши запрос — музыка прикрепится автоматически\n\n"
        "Стили: `aggressive` `smooth` `dark` `lofi`\n"
        "Эффекты: `time_remap` `interpolate` `vignette` `grain` `speed_lines`",
        parse_mode="Markdown",
    )


@dp.message(F.video | F.document, IsOwner())
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

    music_data = _pending_music.pop(chat_id, None)
    if music_data:
        job.music_file_id = music_data["file_id"]
        job.music_start = music_data.get("start")
        job.music_end = music_data.get("end")
        job.bpm = music_data.get("bpm")

    save_job(job)

    music_note = f"\n🎵 Музыка: `{music_data['start']:.1f}s–{music_data['end']:.1f}s` ({music_data['bpm']} BPM)" if music_data else ""
    await msg.answer(
        f"✅ Получил!\nJob `{job.id[:8]}`\nСтиль: `{job.style.value}`{music_note}\n\nОтправил на телефон...",
        parse_mode="Markdown",
    )


@dp.message(F.audio | F.voice, IsOwner())
async def handle_music(msg: Message) -> None:
    chat_id = msg.chat.id
    status_msg = await msg.answer("🎵 Анализирую трек через Gemini...")

    file_obj = msg.audio or msg.voice
    file = await bot.get_file(file_obj.file_id)

    save_dir = UPLOAD_DIR / str(chat_id)
    save_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.file_path).suffix or ".mp3"
    local_path = save_dir / f"music_{file_obj.file_id}{suffix}"
    await bot.download_file(file.file_path, local_path)

    try:
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(None, analyze_music, local_path)

        _pending_music[chat_id] = {
            "file_id": file_obj.file_id,
            "start": analysis["start"],
            "end": analysis["end"],
            "bpm": analysis["bpm"],
            "energy": analysis["energy"],
        }

        await status_msg.edit_text(
            f"✅ Трек проанализирован!\n\n"
            f"🎯 Лучший момент: `{analysis['start']:.1f}s – {analysis['end']:.1f}s`\n"
            f"🥁 BPM: `{analysis['bpm']}`\n"
            f"⚡ Энергия: `{analysis['energy']}`\n\n"
            f"Теперь пиши запрос на эдит — музыка прикрепится автоматически.",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.error("Music analysis failed: %s", e)
        await status_msg.edit_text(
            "❌ Не смог проанализировать трек.\n"
            "Попробуй другой формат (mp3, ogg, m4a) или отправь голосовое.",
        )


@dp.message(IsOwner())
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

    music_data = _pending_music.pop(chat_id, None)
    if music_data:
        job.music_file_id = music_data["file_id"]
        job.music_start = music_data.get("start")
        job.music_end = music_data.get("end")
        job.bpm = music_data.get("bpm")

    save_job(job)

    effects_on = [
        k for k, v in job.effects.model_dump().items()
        if isinstance(v, bool) and v
    ]
    music_note = f"\n🎵 BPM `{music_data['bpm']}` · {music_data['start']:.1f}s–{music_data['end']:.1f}s" if music_data else ""
    await status_msg.edit_text(
        f"✅ Нашёл {len(urls)} клипов для *{job.character}*\n"
        f"Стиль: `{job.style.value}` · Job `{job.id[:8]}`{music_note}\n"
        f"Эффекты: `{', '.join(effects_on)}`\n\n"
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
