from api.src.core.config import settings
from api.src.services.ffmpeg_transcoder import (
    CLEAN_MP3_FILTERS,
    build_clean_mp3_command,
)


def test_build_clean_mp3_command_for_regular_audio():
    command = build_clean_mp3_command("/tmp/input.wav", "/tmp/output.mp3")

    assert command[:2] == ["ffmpeg", "-nostdin"]
    assert "-f" not in command[2:8]
    assert "-i" in command
    assert "/tmp/input.wav" in command
    assert "-af" in command
    assert CLEAN_MP3_FILTERS in command
    assert command[-3:] == ["-ar", "44100", "/tmp/output.mp3"]


def test_build_clean_mp3_command_for_pcm_input():
    command = build_clean_mp3_command("/tmp/input.pcm", "/tmp/output.mp3")

    assert command[:2] == ["ffmpeg", "-nostdin"]
    assert command[3:9] == [
        "-f",
        "s16le",
        "-ar",
        str(settings.sample_rate),
        "-ac",
        "1",
    ]
    assert command[-3:] == ["-ar", "44100", "/tmp/output.mp3"]
