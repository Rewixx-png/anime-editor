import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, Filter
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

_pending_video: dict[int, dict] = {}
_pending_music: dict[int, dict] = {}


def _pending_status(chat_id: int) -> str:
    has_v = chat_id in _pending_video
    has_m = chat_id in _pending_music
    if has_v and has_m:
        return "✅ Исходник + 🎵 Музыка готовы — пиши `/render [стиль]` или просто `/render`"
    if has_v:
        return "✅ Исходник принят — кидай музыку или `/render`"
    if has_m:
        m = _pending_music[chat_id]
        return (
            f"🎵 Музыка готова (`{m['start']:.1f}s–{m['end']:.1f}s`, {m['bpm']} BPM)\n"
            "Кидай видео-исходник или пиши запрос"
        )
    return ""


async def _finalize_job(chat_id: int, caption: str, msg: Message) -> None:
    job = parse_request(caption, chat_id)

    vid = _pending_video.pop(chat_id, None)
    if vid:
        job.clip_urls = [f"tg:{vid['file_id']}"]
    else:
        status_msg = await msg.answer("🔍 Ищу клипы...")
        if not job.character:
            await status_msg.edit_text(
                "❓ Не понял персонажа.\nПример: `aggressive edit Kurumi`",
                parse_mode="Markdown",
            )
            return
        urls = search_clips(job.character, job.style.value)
        if not urls:
            await status_msg.edit_text(
                f"😔 Не нашёл клипы для *{job.character}*.",
                parse_mode="Markdown",
            )
            return
        job.clip_urls = urls

    mus = _pending_music.pop(chat_id, None)
    if mus:
        job.music_file_id = mus["file_id"]
        job.music_start = mus.get("start")
        job.music_end = mus.get("end")
        job.bpm = mus.get("bpm")

    save_job(job)

    effects_on = [k for k, v in job.effects.model_dump().items() if isinstance(v, bool) and v]
    music_note = (
        f"\n🎵 `{mus['start']:.1f}s–{mus['end']:.1f}s` · {mus['bpm']} BPM"
        if mus else ""
    )
    clips_note = "исходник" if vid else f"{len(job.clip_urls)} клипов для *{job.character}*"
    await msg.answer(
        f"⚙️ Job `{job.id[:8]}` · {clips_note}\n"
        f"Стиль: `{job.style.value}`{music_note}\n"
        f"Эффекты: `{', '.join(effects_on)}`\n\n"
        "Рендерю на телефоне...",
        parse_mode="Markdown",
    )


class IsOwner(Filter):
    async def __call__(self, msg: Message) -> bool:
        return msg.from_user.id == OWNER_ID


@dp.message(CommandStart(), IsOwner())
async def cmd_start(msg: Message) -> None:
    await msg.answer(
        "👁️ *Anime Editor*\n\n"
        "*Способ 1* — текстом:\n"
        "`aggressive edit kurumi` — найду клипы сам\n\n"
        "*Способ 2* — свои исходники:\n"
        "1. Кидай видео (любой порядок)\n"
        "2. Кидай аудио\n"
        "3. `/render dark` или просто `/render`\n\n"
        "*Способ 3* — смешанный:\n"
        "Кидай аудио → пиши `smooth rem edit`\n\n"
        "Стили: `aggressive` `smooth` `dark` `lofi`\n"
        "Эффекты: `time_remap` `interpolate` `vignette` `grain` `speed_lines`",
        parse_mode="Markdown",
    )


@dp.message(Command("render"), IsOwner())
async def cmd_render(msg: Message) -> None:
    args = (msg.text or "").replace("/render", "").strip()
    await _finalize_job(msg.chat.id, args or "aggressive edit", msg)


@dp.message(Command("pending"), IsOwner())
async def cmd_pending(msg: Message) -> None:
    status = _pending_status(msg.chat.id)
    await msg.answer(status or "Нет ничего в очереди.", parse_mode="Markdown")


@dp.message(Command("clear"), IsOwner())
async def cmd_clear(msg: Message) -> None:
    _pending_video.pop(msg.chat.id, None)
    _pending_music.pop(msg.chat.id, None)
    await msg.answer("🗑 Очередь очищена.")


@dp.message(F.video | F.document, IsOwner())
async def handle_video(msg: Message) -> None:
    chat_id = msg.chat.id
    caption = (msg.caption or "").strip()

    file_obj = msg.video or msg.document

    _pending_video[chat_id] = {"file_id": file_obj.file_id, "caption": caption}

    if caption:
        await _finalize_job(chat_id, caption, msg)
    else:
        await msg.answer(_pending_status(chat_id), parse_mode="Markdown")


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
        status = _pending_status(chat_id)
        await status_msg.edit_text(
            f"✅ Трек проанализирован!\n"
            f"🎯 `{analysis['start']:.1f}s – {analysis['end']:.1f}s` · "
            f"BPM `{analysis['bpm']}` · Энергия `{analysis['energy']}`\n\n"
            f"{status}",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.error("Music analysis failed: %s", e)
        await status_msg.edit_text("❌ Не смог проанализировать трек. Попробуй mp3/ogg/m4a.")


@dp.message(IsOwner())
async def handle_text(msg: Message) -> None:
    text = (msg.text or "").strip()
    if not text:
        return
    await _finalize_job(msg.chat.id, text, msg)


def _start_api() -> None:
    uvicorn.run(api_app, host="0.0.0.0", port=8080, log_level="warning")


async def main() -> None:
    init_db()
    threading.Thread(target=_start_api, daemon=True).start()
    log.info("Bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
