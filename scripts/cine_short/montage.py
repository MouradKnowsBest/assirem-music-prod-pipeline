"""
montage.py — FFmpeg : concat clips + mux audio + fade in/out.

All commands use ffmpeg in batch mode (-y to overwrite). Errors raise
subprocess.CalledProcessError with stderr captured for diagnosis.
"""

import shutil
import subprocess
from pathlib import Path


def _check_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg introuvable.\n"
            "→ macOS : brew install ffmpeg\n"
            "→ Linux : apt install ffmpeg"
        )


def _run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore")[:1500]
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd[:5])}...\n{stderr}") from e


def probe_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def concat_clips(clips: list[Path], output: Path) -> None:
    """
    Concat MP4 clips into a single video (no audio kept).
    Uses re-encode (not stream copy) to handle slight format mismatches between
    Leonardo Motion outputs.
    """
    _check_ffmpeg()
    output.parent.mkdir(parents=True, exist_ok=True)
    list_file = output.parent / "_clips.txt"
    list_file.write_text(
        "\n".join(f"file '{c.resolve()}'" for c in clips),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",  # drop audio (we'll add the music track next)
        str(output),
    ]
    _run(cmd)
    list_file.unlink(missing_ok=True)


def add_audio(video: Path, audio: Path, output: Path,
              loop_audio: bool = False) -> None:
    """
    Mux a music/SFX track on top of the silent concat.
    Trims output length to whichever is shorter (default).
    Set loop_audio=True if the audio is shorter than the video.
    """
    _check_ffmpeg()
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(video)]
    if loop_audio:
        cmd += ["-stream_loop", "-1"]
    cmd += [
        "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-map", "0:v:0", "-map", "1:a:0",
        str(output),
    ]
    _run(cmd)


def fade_in_out(video: Path, output: Path, fade_sec: float = 1.0) -> None:
    """Smooth fade-in + fade-out on both video and audio."""
    _check_ffmpeg()
    duration = probe_duration(video)
    fade_out_start = max(0.0, duration - fade_sec)
    has_audio = _has_audio_stream(video)

    vf = f"fade=t=in:st=0:d={fade_sec},fade=t=out:st={fade_out_start}:d={fade_sec}"
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
    ]
    if has_audio:
        af = f"afade=t=in:st=0:d={fade_sec},afade=t=out:st={fade_out_start}:d={fade_sec}"
        cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += [str(output)]
    _run(cmd)


def _has_audio_stream(video: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return bool(out)
