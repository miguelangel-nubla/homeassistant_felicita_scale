"""Render the integration's brand images from assets/icon.svg.

Usage: python assets/build_brand.py   (needs rsvg-convert, e.g. from librsvg)

Writes custom_components/felicita_scale/brand/{icon,dark_icon}{,@2x}.png.
The icon is square, so no separate logo files are needed: the logo falls back
to the icon.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icon.svg"
BRAND = ROOT / "custom_components" / "felicita_scale" / "brand"

# Light-background color -> dark-background color
DARK_COLORS = {
    "#2E2723": "#D9D0C8",  # body
    "#4A403A": "#F2ECE6",  # body highlight
    "#171311": "#2E2723",  # display
    "#C8733F": "#E08A52",  # cup
    "#A0938A": "#8C8078",  # steam
}

SIZES = {"": 256, "@2x": 512}


def render(svg: str, prefix: str) -> None:
    """Render one color variant at every size."""
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tmp:
        tmp.write(svg)
    try:
        for suffix, size in SIZES.items():
            out = BRAND / f"{prefix}icon{suffix}.png"
            subprocess.run(
                ["rsvg-convert", "-w", str(size), "-h", str(size), tmp.name, "-o", out],
                check=True,
            )
            if shutil.which("oxipng"):
                subprocess.run(
                    ["oxipng", "-q", "-o", "max", "--strip", "safe", out], check=True
                )
            print(f"wrote {out.relative_to(ROOT)} ({size}x{size})")
    finally:
        Path(tmp.name).unlink()


def main() -> None:
    """Render the light and dark variants."""
    BRAND.mkdir(parents=True, exist_ok=True)
    light = SOURCE.read_text()
    dark = light
    for old, new in DARK_COLORS.items():
        assert old in light, old
        dark = dark.replace(old, new)
    render(light, "")
    render(dark, "dark_")


if __name__ == "__main__":
    main()
