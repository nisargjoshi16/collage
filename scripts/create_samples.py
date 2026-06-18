"""Generate sample images for testing."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLORS = [
    "#E63946", "#F4A261", "#2A9D8F", "#264653",
    "#8338EC", "#FF006E", "#3A86FF", "#FB5607", "#FFBE0B",
]

def make_sample(path: Path, color: str, label: str) -> None:
    img = Image.new("RGB", (400, 400), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 380, 380], outline="#FFFFFF", width=4)
    draw.text((200, 200), label, fill="#FFFFFF", anchor="mm")
    img.save(path)


def make_logo(path: Path) -> None:
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([20, 20, 180, 180], fill="#2563EB")
    draw.text((100, 100), "LOGO", fill="#FFFFFF", anchor="mm")
    img.save(path)


if __name__ == "__main__":
    samples = Path("samples")
    samples.mkdir(exist_ok=True)
    assets = Path("assets")
    assets.mkdir(exist_ok=True)

    for i, color in enumerate(COLORS):
        make_sample(samples / f"photo_{i + 1}.png", color, str(i + 1))

    make_logo(assets / "logo.png")
    print("Sample images created in samples/ and assets/logo.png")