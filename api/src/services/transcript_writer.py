"""Utilities for timestamped transcript artifacts."""

from __future__ import annotations

import json
import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import aiofiles
import aiofiles.os


@dataclass(slots=True)
class TranscriptSegment:
    """A single transcript segment aligned to the rendered audio timeline."""

    id: int
    text: str
    start: float
    end: float
    duration: float


_TRANSCRIPT_CACHE: dict[str, tuple[int, list[TranscriptSegment]]] = {}
_TRANSCRIPT_CACHE_LOCK = asyncio.Lock()


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def build_timestamped_script(segments: Sequence[TranscriptSegment]) -> str:
    """Render a plain-text transcript with timestamp headers."""
    blocks: list[str] = []
    for segment in segments:
        blocks.append(
            f"[{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}]"
        )
        blocks.append(segment.text.strip())
        blocks.append("")
    return "\n".join(blocks).rstrip() + ("\n" if blocks else "")


def build_transcript_payload(
    audio_filename: str,
    sample_rate: int,
    segments: Sequence[TranscriptSegment],
) -> dict:
    """Build the JSON payload for the transcript artifact."""
    total_duration = segments[-1].end if segments else 0.0
    return {
        "audio": audio_filename,
        "sampleRate": sample_rate,
        "totalDuration": round(total_duration, 3),
        "segments": [
            {
                **asdict(segment),
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "duration": round(segment.duration, 3),
            }
            for segment in segments
        ],
    }


def transcript_file_names(audio_filename: str) -> tuple[str, str]:
    """Return the TXT and JSON filenames derived from an audio download."""
    stem = Path(audio_filename).stem
    return f"{stem}_timestamps.txt", f"{stem}_timestamps.json"


def transcript_metadata_file_name(audio_filename: str) -> str:
    """Return the persistent sidecar filename for transcript metadata."""
    stem = Path(audio_filename).stem
    return f"{stem}_transcript.meta.json"


def _parse_transcript_payload(payload: dict) -> tuple[int, list[TranscriptSegment]]:
    """Convert a transcript metadata payload into typed segments."""
    sample_rate = int(payload["sampleRate"])
    segments: list[TranscriptSegment] = []

    for index, segment in enumerate(payload.get("segments", [])):
        segments.append(
            TranscriptSegment(
                id=int(segment.get("id", index)),
                text=str(segment.get("text", "")).strip(),
                start=float(segment["start"]),
                end=float(segment["end"]),
                duration=float(segment["duration"]),
            )
        )

    return sample_rate, segments


async def register_transcript_segments(
    audio_filename: str, sample_rate: int, segments: Sequence[TranscriptSegment]
) -> None:
    """Cache transcript metadata until the user explicitly requests it."""
    async with _TRANSCRIPT_CACHE_LOCK:
        _TRANSCRIPT_CACHE[audio_filename] = (sample_rate, list(segments))


async def get_registered_transcript_segments(
    audio_filename: str,
) -> tuple[int, list[TranscriptSegment]]:
    """Return cached transcript metadata for a generated audio file."""
    async with _TRANSCRIPT_CACHE_LOCK:
        if audio_filename not in _TRANSCRIPT_CACHE:
            raise KeyError(audio_filename)
        sample_rate, segments = _TRANSCRIPT_CACHE[audio_filename]
        return sample_rate, list(segments)


async def persist_transcript_metadata(
    temp_dir: str,
    audio_filename: str,
    sample_rate: int,
    segments: Sequence[TranscriptSegment],
) -> str:
    """Persist transcript metadata so it survives process restarts."""
    output_dir = Path(temp_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / transcript_metadata_file_name(audio_filename)

    metadata = build_transcript_payload(audio_filename, sample_rate, segments)
    async with aiofiles.open(metadata_path, mode="w", encoding="utf-8") as meta_file:
        await meta_file.write(json.dumps(metadata, ensure_ascii=False, indent=2))

    return str(metadata_path)


async def load_transcript_metadata(
    temp_dir: str,
    audio_filename: str,
) -> tuple[int, list[TranscriptSegment]]:
    """Load transcript metadata from its persisted sidecar file."""
    metadata_path = Path(temp_dir) / transcript_metadata_file_name(audio_filename)
    if not await aiofiles.os.path.exists(str(metadata_path)):
        raise KeyError(audio_filename)

    async with aiofiles.open(metadata_path, mode="r", encoding="utf-8") as meta_file:
        payload = json.loads(await meta_file.read())

    return _parse_transcript_payload(payload)


def segment_from_chunk(chunk, segment_id: int) -> TranscriptSegment | None:
    """Convert a generated audio chunk into a transcript segment."""
    text = getattr(chunk, "segment_text", "") or ""
    start = getattr(chunk, "segment_start", None)
    end = getattr(chunk, "segment_end", None)
    duration = getattr(chunk, "segment_duration", None)

    if not text.strip():
        return None
    if start is None or end is None:
        return None
    if duration is None:
        duration = max(0.0, float(end) - float(start))

    return TranscriptSegment(
        id=segment_id,
        text=text.strip(),
        start=float(start),
        end=float(end),
        duration=float(duration),
    )


async def write_transcript_artifacts(
    temp_dir: str,
    audio_filename: str,
    sample_rate: int,
    segments: Sequence[TranscriptSegment],
) -> tuple[str, str]:
    """Write TXT and JSON transcript files next to the generated audio."""
    txt_name, json_name = transcript_file_names(audio_filename)
    output_dir = Path(temp_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_path = output_dir / txt_name
    json_path = output_dir / json_name

    transcript_text = build_timestamped_script(segments)
    transcript_json = json.dumps(
        build_transcript_payload(audio_filename, sample_rate, segments),
        ensure_ascii=False,
        indent=2,
    )

    async with aiofiles.open(txt_path, mode="w", encoding="utf-8") as txt_file:
        await txt_file.write(transcript_text)

    async with aiofiles.open(json_path, mode="w", encoding="utf-8") as json_file:
        await json_file.write(transcript_json)

    return str(txt_path), str(json_path)


async def ensure_transcript_artifacts(
    temp_dir: str,
    audio_filename: str,
) -> tuple[str, str]:
    """Materialize transcript TXT and JSON files from cached metadata."""
    txt_name, json_name = transcript_file_names(audio_filename)
    output_dir = Path(temp_dir)
    txt_path = output_dir / txt_name
    json_path = output_dir / json_name

    if await aiofiles.os.path.exists(str(txt_path)) and await aiofiles.os.path.exists(
        str(json_path)
    ):
        return str(txt_path), str(json_path)

    try:
        sample_rate, segments = await get_registered_transcript_segments(audio_filename)
    except KeyError:
        sample_rate, segments = await load_transcript_metadata(temp_dir, audio_filename)

    return await write_transcript_artifacts(temp_dir, audio_filename, sample_rate, segments)
