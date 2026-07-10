"""Generate a screenshot-style image of the project folder structure."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "folder_structure.png"

IGNORE = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "scripts"}


def build_tree(path: Path, prefix: str = "") -> list[str]:
    lines: list[str] = []
    entries = sorted(
        [p for p in path.iterdir() if p.name not in IGNORE],
        key=lambda p: (p.is_file(), p.name.lower()),
    )
    for index, entry in enumerate(entries):
        is_last = index == len(entries) - 1
        branch = "`-- " if is_last else "|-- "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{prefix}{branch}{entry.name}{suffix}")
        if entry.is_dir():
            extension = "    " if is_last else "|   "
            lines.extend(build_tree(entry, prefix + extension))
    return lines


def main() -> None:
    tree_lines = [ROOT.name + "/"] + build_tree(ROOT)

    try:
        font = ImageFont.truetype("consola.ttf", 16)
        title_font = ImageFont.truetype("consolab.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
        title_font = font

    line_height = 24
    padding = 24
    width = 720
    height = padding * 2 + 40 + line_height * len(tree_lines)

    img = Image.new("RGB", (width, height), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, 56), fill=(30, 64, 175))
    draw.text((padding, 16), "Python Clean Architecture - Folder Structure", fill="white", font=title_font)

    y = 72
    for line in tree_lines:
        color = (15, 23, 42)
        if line.endswith("/"):
            color = (30, 64, 175)
        elif line.strip().startswith("|--") or line.strip().startswith("`--"):
            name = line.split(" ", 1)[-1]
            if name.endswith((".py", ".toml", ".txt", ".md", ".example")):
                color = (22, 101, 52)
        draw.text((padding, y), line, fill=color, font=font)
        y += line_height

    draw.rectangle((8, 8, width - 8, height - 8), outline=(203, 213, 225), width=2)
    img.save(OUTPUT)
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
