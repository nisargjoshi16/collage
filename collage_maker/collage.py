"""Core collage generation logic."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .designs import CollageDesign, LogoConfig

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}


def collect_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Image folder not found: {folder}")

    images = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not images:
        raise ValueError(f"No supported images found in {folder}")
    return images


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    if target_w <= 0 or target_h <= 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    img = image.convert("RGBA")
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def compute_cells(design: CollageDesign, image_count: int) -> list[tuple[int, int, int, int]]:
    width, height = design.output_size
    gap = design.gap

    if design.layout == "grid":
        rows, cols = design.rows, design.cols
        cell_w = (width - gap * (cols + 1)) // cols
        cell_h = (height - gap * (rows + 1)) // rows
        cells = []
        for index in range(min(image_count, rows * cols)):
            row = index // cols
            col = index % cols
            x = gap + col * (cell_w + gap)
            y = gap + row * (cell_h + gap)
            cells.append((x, y, cell_w, cell_h))
        return cells

    if design.layout == "horizontal":
        count = image_count
        cell_w = (width - gap * (count + 1)) // count
        cell_h = height - 2 * gap
        return [
            (gap + i * (cell_w + gap), gap, cell_w, cell_h)
            for i in range(count)
        ]

    if design.layout == "vertical":
        count = image_count
        cell_w = width - 2 * gap
        cell_h = (height - gap * (count + 1)) // count
        return [
            (gap, gap + i * (cell_h + gap), cell_w, cell_h)
            for i in range(count)
        ]

    if design.layout == "featured":
        ratio = design.featured_ratio
        side = design.featured_side
        cells: list[tuple[int, int, int, int]] = []

        if side in ("left", "right"):
            main_w = int((width - 3 * gap) * ratio)
            thumb_w = width - main_w - 3 * gap
            main_h = height - 2 * gap
            thumb_count = max(1, image_count - 1)
            thumb_h = (main_h - gap * (thumb_count - 1)) // thumb_count

            if side == "left":
                cells.append((gap, gap, main_w, main_h))
                for i in range(thumb_count):
                    x = gap + main_w + gap
                    y = gap + i * (thumb_h + gap)
                    cells.append((x, y, thumb_w, thumb_h))
            else:
                for i in range(thumb_count):
                    x = gap
                    y = gap + i * (thumb_h + gap)
                    cells.append((x, y, thumb_w, thumb_h))
                cells.append((gap + thumb_w + gap, gap, main_w, main_h))
        else:
            main_h = int((height - 3 * gap) * ratio)
            thumb_h = height - main_h - 3 * gap
            main_w = width - 2 * gap
            thumb_count = max(1, image_count - 1)
            thumb_w = (main_w - gap * (thumb_count - 1)) // thumb_count

            if side == "top":
                cells.append((gap, gap, main_w, main_h))
                for i in range(thumb_count):
                    x = gap + i * (thumb_w + gap)
                    y = gap + main_h + gap
                    cells.append((x, y, thumb_w, thumb_h))
            else:
                for i in range(thumb_count):
                    x = gap + i * (thumb_w + gap)
                    y = gap
                    cells.append((x, y, thumb_w, thumb_h))
                cells.append((gap, gap + thumb_h + gap, main_w, main_h))

        return cells

    raise ValueError(f"Unsupported layout: {design.layout}")


def apply_logo(canvas: Image.Image, logo_config: LogoConfig) -> Image.Image:
    logo_path = logo_config.path
    if not logo_path.is_file():
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    logo = Image.open(logo_path).convert("RGBA")
    canvas_w, canvas_h = canvas.size
    max_logo_w = int(canvas_w * logo_config.size_ratio)
    max_logo_h = int(canvas_h * logo_config.size_ratio)

    logo.thumbnail((max_logo_w, max_logo_h), Image.Resampling.LANCZOS)

    if logo_config.opacity < 1.0:
        alpha = logo.split()[3]
        alpha = alpha.point(lambda p: int(p * logo_config.opacity))
        logo.putalpha(alpha)

    padding = logo_config.padding
    lw, lh = logo.size

    positions = {
        "top-left": (padding, padding),
        "top-right": (canvas_w - lw - padding, padding),
        "bottom-left": (padding, canvas_h - lh - padding),
        "bottom-right": (canvas_w - lw - padding, canvas_h - lh - padding),
    }
    position = positions[logo_config.corner]

    result = canvas.convert("RGBA")
    result.paste(logo, position, logo)
    return result


def create_collage(
    image_folder: Path,
    design: CollageDesign,
    output_path: Path,
    max_images: int | None = None,
) -> Path:
    design.validate()

    images = collect_images(image_folder)
    if max_images is not None:
        images = images[:max_images]

    cells = compute_cells(design, len(images))
    if not cells:
        raise ValueError("Design produced no placement cells for the given images")

    bg_color = hex_to_rgb(design.background)
    canvas = Image.new("RGB", design.output_size, bg_color)

    for image_path, (x, y, w, h) in zip(images, cells):
        with Image.open(image_path) as img:
            fitted = fit_image(img, (w, h))
            if fitted.mode == "RGBA":
                canvas.paste(fitted, (x, y), fitted)
            else:
                canvas.paste(fitted, (x, y))

    if design.logo:
        canvas = apply_logo(canvas, design.logo)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)
    return output_path