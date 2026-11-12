"""Record docs/demo/demo.tape and add a caption bar: docs/demo/demo.gif.

Usage, from the repo root: uv run python docs/demo/render.py

The ffmpeg used by vhs has no drawtext filter, so each caption is drawn
with Pillow into a PNG strip and overlaid under the terminal while it
applies. Caption times come from the tape's commands (typing speed and
Sleeps), counted from `Show`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
TAPE = HERE / "demo.tape"
# A GIF, not an mp4: H.264 noise changes every pixel of every frame,
# which defeats the GIF's frame-to-frame compression (3x the size).
RAW = HERE / "raw.gif"
GIF = HERE / "demo.gif"

BAR_HEIGHT = 64
BACKGROUND = "#171717"  # vhs's default theme background
KEY_FILL, KEY_EDGE, KEY_TEXT = "#2f3338", "#6b7280", "#f3f4f6"
TYPED_TEXT, ARROW, DESCRIPTION = "#e5c07b", "#6b7280", "#d1d5db"
FPS = 10
# Fewer colours and lossy=40 roughly halve the size. Below ~64 colours
# the palette starts dropping rare ones (the red of highlighted errors).
COLORS = int(os.environ.get("DEMO_COLORS", "64"))
LOSSY = int(os.environ.get("DEMO_LOSSY", "40"))

_KEYS = {"Enter", "Space", "Escape", "Backspace", "Tab", "Up", "Down"}
_KEYS |= {"Left", "Right", "PageUp", "PageDown", "Delete"}


@dataclass
class Caption:
    start: float
    keys: str
    text: str
    end: float = 0.0


def _seconds(*, value: str) -> float:
    match = re.fullmatch(r"([\d.]+)(ms|s)?", value)
    if match is None:
        raise ValueError(f"not a duration: {value}")
    number = float(match.group(1))
    return number / 1000 if match.group(2) == "ms" else number


def read_captions(*, tape: Path) -> list[Caption]:
    """Each `#>` caption with the time it starts, counted from Show."""
    speed = 0.05
    now = 0.0
    recording = False
    captions: list[Caption] = []
    for line in tape.read_text().splitlines():
        line = line.strip()
        if line.startswith("#>"):
            keys, _, text = line[2:].partition("|")
            captions.append(Caption(now, keys.strip(), text.strip()))
            continue
        if not line or line.startswith("#"):
            continue
        command, _, rest = line.partition(" ")
        name, _, at = command.partition("@")
        if name == "Set" and rest.startswith("TypingSpeed"):
            speed = _seconds(value=rest.split()[1])
        elif name in ("Hide", "Show"):
            recording = name == "Show"
        elif not recording:
            continue
        elif name == "Sleep":
            now += _seconds(value=rest)
        elif name == "Type":
            each = _seconds(value=at) if at else speed
            now += each * len(rest.strip().strip('"'))
        elif name in _KEYS or name.startswith("Ctrl+"):
            each = _seconds(value=at) if at else speed
            now += each * (int(rest) if rest.strip() else 1)
    for caption, following in zip(captions, captions[1:], strict=False):
        caption.end = following.start
    captions[-1].end = now + 1
    return captions


def _font(*, pattern: str, size: int) -> ImageFont.FreeTypeFont:
    found = subprocess.run(
        ["fc-match", "-f", "%{file}", pattern],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return ImageFont.truetype(found, size)


def draw_caption(*, caption: Caption, width: int, path: Path) -> None:
    mono = _font(pattern="DejaVu Sans Mono:bold", size=22)
    sans = _font(pattern="Inter:medium", size=23)
    image = Image.new("RGB", (width, BAR_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    x, middle = 24, BAR_HEIGHT // 2
    for token in re.findall(
        r"\[[^\]]+\]|[^\s\[]+(?: [^\s\[]+)*", caption.keys
    ):
        if token.startswith("["):
            label = token[1:-1]
            box = draw.textbbox((0, 0), label, font=mono)
            key_width = max(box[2] - box[0] + 24, 40)
            draw.rounded_rectangle(
                (x, middle - 19, x + key_width, middle + 19),
                radius=7,
                fill=KEY_FILL,
                outline=KEY_EDGE,
                width=2,
            )
            draw.text(
                (x + key_width / 2, middle),
                label,
                font=mono,
                fill=KEY_TEXT,
                anchor="mm",
            )
            x += key_width + 10
        else:
            draw.text(
                (x, middle), token, font=mono, fill=TYPED_TEXT, anchor="lm"
            )
            x += int(draw.textlength(token, font=mono)) + 12
    draw.text((x + 6, middle), "→", font=sans, fill=ARROW, anchor="lm")
    draw.text(
        (x + 40, middle),
        caption.text,
        font=sans,
        fill=DESCRIPTION,
        anchor="lm",
    )
    image.save(path)


def _size(*, video: Path) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    width, height = out.strip().split(",")
    return int(width), int(height)


def render(*, record: bool) -> None:
    if record:
        subprocess.run(["vhs", str(TAPE)], check=True)
    width, height = _size(video=RAW)
    captions = read_captions(tape=TAPE)
    with tempfile.TemporaryDirectory() as folder:
        inputs: list[str] = ["-i", str(RAW)]
        steps = [f"[0]pad={width}:{height + BAR_HEIGHT}:0:0:{BACKGROUND}[v0]"]
        for number, caption in enumerate(captions, 1):
            strip = Path(folder) / f"caption{number}.png"
            draw_caption(caption=caption, width=width, path=strip)
            inputs += ["-i", str(strip)]
            steps.append(
                f"[v{number - 1}][{number}]overlay=0:{height}:"
                f"enable='between(t,{caption.start:.2f},{caption.end:.2f})'"
                f"[v{number}]"
            )
        # One palette for the whole GIF and no dithering: terminal colours
        # are flat, and dithering speckles dimmed backgrounds.
        steps.append(
            f"[v{len(captions)}]fps={FPS},split[a][b];"
            f"[a]palettegen=max_colors={COLORS}:stats_mode=full[p];"
            "[b][p]paletteuse=dither=none:diff_mode=rectangle"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                *inputs,
                "-filter_complex",
                ";".join(steps),
                str(GIF),
            ],
            check=True,
        )
    subprocess.run(
        ["gifsicle", "-O3", f"--lossy={LOSSY}", "-b", str(GIF)], check=True
    )
    if record:
        RAW.unlink()
    for caption in captions:
        print(f"{caption.start:6.2f}-{caption.end:6.2f}  {caption.text}")
    print(f"{GIF}: {GIF.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    if shutil.which("vhs") is None:
        raise SystemExit("vhs not found: https://github.com/charmbracelet/vhs")
    # --reuse: re-render from an existing raw.gif (kept), e.g. to try
    # caption or GIF settings without recording again.
    render(record="--reuse" not in sys.argv)
