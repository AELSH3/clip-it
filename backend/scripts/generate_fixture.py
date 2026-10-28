"""Build short local fixture videos with macOS say + ffmpeg. Not downloaded third-party media."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "fixtures" / "videos"

CLIPS = {
    "lecture-deadlocks": "The instructor explains deadlocks when two processes wait on each other forever.",
    "demo-docker": "The presenter runs the docker command to start the container.",
    "lecture-queues": "This lecture explains message queues and how workers pull jobs.",
}


def main() -> None:
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        print("Need the macOS say command and ffmpeg.", file=sys.stderr)
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    font = "/System/Library/Fonts/Supplemental/Arial.ttf"
    for key, sentence in CLIPS.items():
        audio = OUT / f"{key}.aiff"
        video = OUT / f"{key}.mp4"
        subprocess.run(["say", "-v", "Samantha", "-o", str(audio), sentence], check=True)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(audio),
                "-f", "lavfi", "-i", "color=c=0x1a1c19:s=640x360:r=15",
                "-shortest",
                "-vf", f"drawtext=fontfile={font}:text='Lecture':fontsize=36:fontcolor=white:x=40:y=40",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(video),
            ],
            check=True,
        )
    diagram = OUT / "architecture.png"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=white:s=640x360:d=1",
            "-vf", f"drawtext=fontfile={font}:text='Architecture Diagram':fontsize=36:fontcolor=black:x=40:y=160",
            "-frames:v", "1", str(diagram),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(diagram), "-t", "8",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
            str(OUT / "slide-architecture.mp4"),
        ],
        check=True,
    )
    print(f"Wrote videos in {OUT}")


if __name__ == "__main__":
    main()
