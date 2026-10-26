#!/usr/bin/env python3
"""Regenerate images/og/nodecontrol-share.png (1200×630).

From the repo root:

    python3 images/og/render_share.py

The card uses the mark in images/logo-simple.svg, with that file's wordmark
and old tagline removed, plus a large NodeControl wordmark and one line from
the homepage description.

The framed accent is a crop of images/screenshots/nc-l2-topology.png.
That screenshot shows device hostnames and private addresses, so the accent
is scaled down and blurred until those labels are not readable.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
LOGO = ROOT / "images" / "logo-simple.svg"
SCREENSHOT = ROOT / "images" / "screenshots" / "nc-l2-topology.png"
OUTPUT = ROOT / "images" / "og" / "nodecontrol-share.png"

WIDTH = 1200
HEIGHT = 630
TAGLINE = "Desktop network operations for network engineers"

# Hostname and address fragments read off nc-l2-topology.png. The blurred
# accent must not still contain them.
LABEL_FRAGMENTS = (
    "hq-",
    "noc-",
    "edge",
    "sdwan",
    "vstack",
    "10.10",
    "254",
)


def logo_mark_svg() -> str:
    """The icon from logo-simple.svg, without its wordmark or old tagline."""
    svg = LOGO.read_text(encoding="utf-8")
    svg = re.sub(r"<text\b[^>]*>.*?</text>", "", svg, flags=re.DOTALL)
    if "AUTOMATE" in svg or "<text" in svg:
        raise SystemExit("logo mark still contains text from logo-simple.svg")
    return svg


def blurred_accent(path: Path) -> None:
    """Crop the topology map and blur it so hostnames and addresses are gone."""
    image = Image.open(SCREENSHOT).convert("RGB")
    # Drop the left device list and the window chrome. Labels on the nodes
    # themselves are removed by the scale-down and blur below.
    crop = image.crop((380, 56, 1880, 1040))
    accent = crop.resize((560, 340), Image.Resampling.LANCZOS)
    accent = accent.filter(ImageFilter.GaussianBlur(radius=10))
    accent.save(path, "PNG")
    _assert_labels_gone(path)


def _assert_labels_gone(path: Path) -> None:
    text = subprocess.check_output(
        ["tesseract", str(path), "stdout", "--psm", "6"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    lowered = text.lower()
    if re.search(r"\d{1,3}(?:\.\d{1,3}){3}", lowered):
        raise SystemExit(f"an address is still readable in the accent:\n{text}")
    for fragment in LABEL_FRAGMENTS:
        if fragment in lowered:
            raise SystemExit(
                f"{fragment!r} is still readable in the accent:\n{text}"
            )


def inter_font(style: str) -> Path:
    listed = subprocess.check_output(
        ["fc-list", f"Inter:style={style}", "file"],
        text=True,
    )
    for line in listed.splitlines():
        path = Path(line.split(":", 1)[0].strip())
        if path.is_file():
            return path
    raise SystemExit(f"Inter {style} is not installed (fc-list Inter:style={style})")


def card_html(svg: str) -> str:
    regular = inter_font("Medium")
    semibold = inter_font("SemiBold")
    bold = inter_font("Bold")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NodeControl share image</title>
<style>
  @font-face {{
    font-family: Inter;
    font-weight: 500;
    src: url("{regular}") format("truetype");
  }}
  @font-face {{
    font-family: Inter;
    font-weight: 600;
    src: url("{semibold}") format("truetype");
  }}
  @font-face {{
    font-family: Inter;
    font-weight: 700;
    src: url("{bold}") format("truetype");
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    overflow: hidden;
    background: #0b0f14;
  }}
  .card {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    position: relative;
    background:
      radial-gradient(ellipse 720px 520px at 16% 46%, rgba(0, 229, 255, 0.14), transparent 68%),
      radial-gradient(ellipse 460px 340px at 94% 86%, rgba(255, 152, 0, 0.11), transparent 72%),
      #0b0f14;
    font-family: Inter, sans-serif;
    color: #d7e1ea;
  }}
  .wrap {{
    position: absolute;
    inset: 0;
    padding: 0 80px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 48px;
  }}
  .copy {{
    width: 720px;
    flex: none;
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 24px;
  }}
  .logo {{
    width: 112px;
    height: 112px;
    flex: none;
  }}
  .logo svg {{
    width: 112px;
    height: 112px;
    display: block;
  }}
  .word {{
    font-size: 76px;
    line-height: 0.95;
    font-weight: 700;
    letter-spacing: -0.04em;
    color: #ffffff;
  }}
  .word span {{
    color: #00e5ff;
    font-weight: 600;
  }}
  .rule {{
    width: 164px;
    height: 4px;
    border-radius: 4px;
    margin: 28px 0 22px;
    background: linear-gradient(90deg, #00e5ff 0%, #ff9800 100%);
  }}
  .tagline {{
    font-size: 30px;
    line-height: 1.2;
    font-weight: 500;
    letter-spacing: -0.02em;
    color: #d7e1ea;
    white-space: nowrap;
  }}
  .frame {{
    width: 272px;
    flex: none;
    background: #111b26;
    border: 1px solid #1f2a36;
    border-radius: 16px;
    padding: 8px;
    box-shadow:
      0 18px 44px rgba(0, 0, 0, 0.5),
      0 0 0 1px rgba(0, 229, 255, 0.14);
  }}
  .frame img {{
    display: block;
    width: 100%;
    height: 148px;
    object-fit: cover;
    border-radius: 10px;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="wrap">
      <div class="copy">
        <div class="brand">
          <div class="logo">{svg}</div>
          <div class="word">Node<span>Control</span></div>
        </div>
        <div class="rule"></div>
        <p class="tagline">{TAGLINE}</p>
      </div>
      <div class="frame" aria-hidden="true">
        <img src="accent.png" alt="">
      </div>
    </div>
  </div>
</body>
</html>
"""


def render_png(html_dir: Path, dest: Path) -> None:
    html_path = html_dir / "card.html"
    user_dir = html_dir / "chrome-profile"
    screenshot = html_dir / "card.png"
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if not chrome:
        raise SystemExit("google-chrome is required to render the share image")
    # Headless Chrome writes the screenshot and then often stays up on this
    # image. Wait until the file size settles, then stop the process group.
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--user-data-dir={user_dir}",
            f"--window-size={WIDTH},{HEIGHT}",
            f"--screenshot={screenshot}",
            "--default-background-color=FF0B0F14",
            html_path.resolve().as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 25
        stable = False
        while time.time() < deadline:
            if screenshot.exists() and screenshot.stat().st_size > 1000:
                size_a = screenshot.stat().st_size
                time.sleep(0.4)
                if screenshot.exists() and screenshot.stat().st_size == size_a:
                    stable = True
                    break
            if proc.poll() is not None and screenshot.exists():
                stable = True
                break
            time.sleep(0.2)
        if not stable:
            raise SystemExit("chrome did not write a screenshot")
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
    image = Image.open(screenshot)
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(f"rendered {image.size}, expected {(WIDTH, HEIGHT)}")
    image.convert("RGB").save(dest, "PNG", optimize=True)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nc-og-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        blurred_accent(work / "accent.png")
        (work / "card.html").write_text(card_html(logo_mark_svg()), encoding="utf-8")
        render_png(work, OUTPUT)
    size = OUTPUT.stat().st_size
    print(f"wrote {OUTPUT} ({size} bytes)")
    if size > 300 * 1024:
        raise SystemExit(f"share image is {size} bytes, over the 300 KB target")


if __name__ == "__main__":
    main()
