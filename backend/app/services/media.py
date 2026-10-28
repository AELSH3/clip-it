import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.errors import PermanentProcessingError


@dataclass
class MediaInfo:
    duration_sec: float | None
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool
    has_video: bool
    format_name: str | None


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PermanentProcessingError(f"{cmd[0]} is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "media tool failed"
        raise PermanentProcessingError(tail[:500]) from exc


def _fps(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        if float(den) == 0:
            return None
        return float(num) / float(den)
    return float(value)


def probe(path: Path) -> MediaInfo:
    completed = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise PermanentProcessingError("ffprobe returned data this file could not explain.") from exc
    streams = payload.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if video is None:
        raise PermanentProcessingError("This file does not contain a video stream.")
    duration_raw = (payload.get("format") or {}).get("duration") or video.get("duration")
    duration = float(duration_raw) if duration_raw not in (None, "N/A") else None
    return MediaInfo(
        duration_sec=duration,
        width=video.get("width"),
        height=video.get("height"),
        fps=_fps(video.get("avg_frame_rate")),
        has_audio=audio is not None,
        has_video=True,
        format_name=(payload.get("format") or {}).get("format_name"),
    )


def extract_audio(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def extract_frames(src: Path, dest_dir: Path, interval: float) -> list[tuple[float, Path]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("frame_*.jpg"):
        old.unlink()
    rate = 1.0 / max(interval, 0.25)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            f"fps={rate:.6f},scale=640:-2",
            "-q:v",
            "3",
            str(dest_dir / "frame_%04d.jpg"),
        ]
    )
    frames = sorted(dest_dir.glob("frame_*.jpg"))
    if not frames:
        raise PermanentProcessingError("No frames could be read from this video.")
    return [((index) * interval, frame) for index, frame in enumerate(frames)]


def write_thumbnail(frames: list[tuple[float, Path]], dest: Path) -> None:
    if not frames:
        raise PermanentProcessingError("No thumbnail frame is available.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(frames[0][1].read_bytes())
