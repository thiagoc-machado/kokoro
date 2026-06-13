"""Helpers for ffmpeg-based audio transcoding."""

from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import which

import aiofiles.os
from loguru import logger

from ..core.config import settings
from ..core.paths import _find_file

# A subtle "clean" preset that stays compatible with stock ffmpeg builds.
# It avoids aggressive compression/EQ and instead uses speech-oriented denoise
# plus de-essing to suppress hiss/whistle artifacts without changing the voice
# character too much.
CLEAN_MP3_FILTERS = (
    "highpass=f=60,"
    "afftdn=nr=6:nf=-45:nt=w,"
    "deesser=i=0.18:m=0.35:f=0.58,"
    "lowpass=f=11000,"
    "alimiter=limit=0.995"
)
CLEAN_MP3_PRESET_VERSION = "v2"


def build_clean_mp3_command(source_path: str, target_path: str) -> list[str]:
    """Build the ffmpeg command used for the clean MP3 transcode."""
    command = ["ffmpeg", "-nostdin", "-y"]

    if Path(source_path).suffix.lower() == ".pcm":
        command.extend(
            [
                "-f",
                "s16le",
                "-ar",
                str(settings.sample_rate),
                "-ac",
                "1",
            ]
        )

    command.extend(
        [
            "-i",
            source_path,
            "-vn",
            "-af",
            CLEAN_MP3_FILTERS,
            "-c:a",
            "libmp3lame",
            "-q:a",
            "0",
            "-ar",
            "44100",
            target_path,
        ]
    )
    return command


async def transcode_clean_mp3(source_filename: str) -> tuple[str, str]:
    """Transcode a temporary audio file into a cleaned MP3 download."""
    if which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not available on this system")

    source_path = await _find_file(source_filename, [settings.temp_file_dir])
    source_name = Path(source_filename).name
    target_name = f"{Path(source_name).stem}_clean_{CLEAN_MP3_PRESET_VERSION}.mp3"
    target_path = Path(settings.temp_file_dir) / target_name

    await aiofiles.os.makedirs(settings.temp_file_dir, exist_ok=True)

    if await aiofiles.os.path.exists(str(target_path)):
        source_stat = await aiofiles.os.stat(source_path)
        target_stat = await aiofiles.os.stat(str(target_path))
        if target_stat.st_mtime >= source_stat.st_mtime:
            return str(target_path), target_name

    command = build_clean_mp3_command(source_path, str(target_path))
    logger.info("Transcoding clean MP3: {}", " ".join(command))

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        if await aiofiles.os.path.exists(str(target_path)):
            await aiofiles.os.remove(str(target_path))

        stderr_text = stderr.decode("utf-8", errors="ignore").strip()
        stdout_text = stdout.decode("utf-8", errors="ignore").strip()
        message = stderr_text or stdout_text or "ffmpeg transcoding failed"
        raise RuntimeError(message)

    return str(target_path), target_name
