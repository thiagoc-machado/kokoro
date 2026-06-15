import json

import pytest

from api.src.services import transcript_writer as transcript_writer_module
from api.src.services.transcript_writer import (
    TranscriptSegment,
    build_timestamped_script,
    build_transcript_payload,
    ensure_transcript_artifacts,
    format_timestamp,
    load_transcript_metadata,
    persist_transcript_metadata,
    register_transcript_segments,
    segment_from_chunk,
    transcript_metadata_file_name,
    transcript_file_names,
    write_transcript_artifacts,
)


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00.000"
    assert format_timestamp(5.2412) == "00:00:05.241"
    assert format_timestamp(3661.234) == "01:01:01.234"


def test_build_timestamped_script():
    script = build_timestamped_script(
        [
            TranscriptSegment(
                id=0,
                text="First line.",
                start=0.0,
                end=1.25,
                duration=1.25,
            ),
            TranscriptSegment(
                id=1,
                text="Second line.",
                start=1.25,
                end=3.5,
                duration=2.25,
            ),
        ]
    )

    assert script == (
        "[00:00:00.000 --> 00:00:01.250]\n"
        "First line.\n\n"
        "[00:00:01.250 --> 00:00:03.500]\n"
        "Second line.\n"
    )


def test_build_transcript_payload():
    payload = build_transcript_payload(
        "speech.mp3",
        24000,
        [
            TranscriptSegment(
                id=0,
                text="First line.",
                start=0.0,
                end=1.2349,
                duration=1.2349,
            )
        ],
    )

    assert payload["audio"] == "speech.mp3"
    assert payload["sampleRate"] == 24000
    assert payload["totalDuration"] == 1.235
    assert payload["segments"][0]["start"] == 0.0
    assert payload["segments"][0]["end"] == 1.235
    assert payload["segments"][0]["duration"] == 1.235


def test_transcript_file_names():
    txt_name, json_name = transcript_file_names("speech.mp3")
    assert txt_name == "speech_timestamps.txt"
    assert json_name == "speech_timestamps.json"


def test_segment_from_chunk():
    chunk = type(
        "Chunk",
        (),
        {
            "segment_text": "Hello world",
            "segment_start": 1.5,
            "segment_end": 3.0,
            "segment_duration": 1.5,
        },
    )()

    segment = segment_from_chunk(chunk, 7)
    assert segment is not None
    assert segment.id == 7
    assert segment.text == "Hello world"
    assert segment.start == 1.5
    assert segment.end == 3.0
    assert segment.duration == 1.5


@pytest.mark.asyncio
async def test_write_transcript_artifacts(tmp_path):
    segments = [
        TranscriptSegment(
            id=0,
            text="First line.",
            start=0.0,
            end=1.25,
            duration=1.25,
        )
    ]

    txt_path, json_path = await write_transcript_artifacts(
        str(tmp_path),
        "speech.mp3",
        24000,
        segments,
    )

    assert tmp_path.joinpath("speech_timestamps.txt").exists()
    assert tmp_path.joinpath("speech_timestamps.json").exists()

    txt_content = tmp_path.joinpath("speech_timestamps.txt").read_text(encoding="utf-8")
    json_content = json.loads(
        tmp_path.joinpath("speech_timestamps.json").read_text(encoding="utf-8")
    )

    assert txt_path.endswith("speech_timestamps.txt")
    assert json_path.endswith("speech_timestamps.json")
    assert "00:00:00.000 --> 00:00:01.250" in txt_content
    assert json_content["audio"] == "speech.mp3"


@pytest.mark.asyncio
async def test_on_demand_transcript_artifacts(tmp_path):
    segments = [
        TranscriptSegment(
            id=0,
            text="First line.",
            start=0.0,
            end=1.25,
            duration=1.25,
        )
    ]

    await register_transcript_segments("speech.mp3", 24000, segments)
    await persist_transcript_metadata(str(tmp_path), "speech.mp3", 24000, segments)
    transcript_writer_module._TRANSCRIPT_CACHE.clear()

    metadata_name = transcript_metadata_file_name("speech.mp3")
    assert tmp_path.joinpath(metadata_name).exists()

    sample_rate, cached_segments = await load_transcript_metadata(
        str(tmp_path), "speech.mp3"
    )

    assert sample_rate == 24000
    assert cached_segments[0].text == "First line."

    txt_path, json_path = await ensure_transcript_artifacts(str(tmp_path), "speech.mp3")
    assert tmp_path.joinpath("speech_timestamps.txt").exists()
    assert tmp_path.joinpath("speech_timestamps.json").exists()
    assert txt_path.endswith("speech_timestamps.txt")
    assert json_path.endswith("speech_timestamps.json")


@pytest.mark.asyncio
async def test_transcript_artifacts_can_be_rebuilt_after_cache_loss(tmp_path):
    segments = [
        TranscriptSegment(
            id=0,
            text="First line.",
            start=0.0,
            end=1.25,
            duration=1.25,
        )
    ]

    await persist_transcript_metadata(str(tmp_path), "speech.mp3", 24000, segments)
    transcript_writer_module._TRANSCRIPT_CACHE.clear()

    txt_path, json_path = await ensure_transcript_artifacts(str(tmp_path), "speech.mp3")
    assert tmp_path.joinpath("speech_timestamps.txt").exists()
    assert tmp_path.joinpath("speech_timestamps.json").exists()
    assert txt_path.endswith("speech_timestamps.txt")
    assert json_path.endswith("speech_timestamps.json")

    sample_rate, cached_segments = await load_transcript_metadata(
        str(tmp_path), "speech.mp3"
    )
    assert sample_rate == 24000
    assert cached_segments[0].text == "First line."
