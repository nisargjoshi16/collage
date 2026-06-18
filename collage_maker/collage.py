"""Core collage generation logic."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from .designs import CollageDesign, LogoConfig, resolve_asset_path
from .smart_crop import smart_cover_image

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


def cover_image(image: Image.Image, size: tuple[int, int], fit_mode: str = "smart") -> Image.Image:
    """Resize and crop an image to fill the target using the selected fit strategy."""
    if fit_mode != "cover":
        return smart_cover_image(image, size, fit_mode=fit_mode)

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


def _cell_sizes(total: int, count: int, gap: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [total]
    usable = total - gap * (count - 1)
    base, remainder = divmod(usable, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _cell_positions(sizes: list[int], gap: int) -> list[int]:
    positions: list[int] = []
    offset = 0
    for index, size in enumerate(sizes):
        positions.append(offset)
        offset += size + (gap if index < len(sizes) - 1 else 0)
    return positions


def auto_grid_dimensions(count: int, output_size: tuple[int, int]) -> tuple[int, int]:
    """Pick rows/cols that fill the canvas without empty cells."""
    if count <= 1:
        return 1, 1

    width, height = output_size
    target_aspect = width / height if height else 1.0
    best: tuple[float, int, int] | None = None

    for cols in range(1, count + 1):
        rows = math.ceil(count / cols)
        empty = rows * cols - count
        grid_aspect = cols / rows
        aspect_penalty = abs(math.log(grid_aspect / target_aspect)) if target_aspect > 0 else 0.0
        score = empty * 1000 + aspect_penalty
        if best is None or score < best[0]:
            best = (score, rows, cols)

    assert best is not None
    return best[1], best[2]


def resolve_grid_dimensions(
    design: CollageDesign,
    image_count: int,
) -> tuple[int, int]:
    if design.auto_fit or image_count > design.rows * design.cols:
        return auto_grid_dimensions(image_count, design.output_size)

    if image_count < design.rows * design.cols:
        return auto_grid_dimensions(image_count, design.output_size)

    return design.rows, design.cols


def compute_cells(design: CollageDesign, image_count: int) -> list[tuple[int, int, int, int]]:
    width, height = design.output_size
    gap = design.gap

    if design.layout == "grid":
        rows, cols = resolve_grid_dimensions(design, image_count)
        col_sizes = _cell_sizes(width, cols, gap)
        row_sizes = _cell_sizes(height, rows, gap)
        col_positions = _cell_positions(col_sizes, gap)
        row_positions = _cell_positions(row_sizes, gap)

        cells = []
        for index in range(image_count):
            row = index // cols
            col = index % cols
            cells.append((
                col_positions[col],
                row_positions[row],
                col_sizes[col],
                row_sizes[row],
            ))
        return cells

    if design.layout == "horizontal":
        col_sizes = _cell_sizes(width, image_count, gap)
        col_positions = _cell_positions(col_sizes, gap)
        return [
            (col_positions[index], 0, col_sizes[index], height)
            for index in range(image_count)
        ]

    if design.layout == "vertical":
        row_sizes = _cell_sizes(height, image_count, gap)
        row_positions = _cell_positions(row_sizes, gap)
        return [
            (0, row_positions[index], width, row_sizes[index])
            for index in range(image_count)
        ]

    if design.layout == "featured":
        ratio = design.featured_ratio
        side = design.featured_side
        cells: list[tuple[int, int, int, int]] = []
        thumb_count = max(1, image_count - 1)

        if side in ("left", "right"):
            if gap == 0:
                main_w = int(width * ratio)
                thumb_w = width - main_w
            else:
                main_w = int((width - gap) * ratio)
                thumb_w = width - main_w - gap

            main_h = height
            row_sizes = _cell_sizes(main_h, thumb_count, gap)
            row_positions = _cell_positions(row_sizes, gap)

            if side == "left":
                cells.append((0, 0, main_w, main_h))
                thumb_x = main_w + gap
                for index in range(thumb_count):
                    cells.append((
                        thumb_x,
                        row_positions[index],
                        thumb_w,
                        row_sizes[index],
                    ))
            else:
                for index in range(thumb_count):
                    cells.append((
                        0,
                        row_positions[index],
                        thumb_w,
                        row_sizes[index],
                    ))
                cells.append((thumb_w + gap, 0, main_w, main_h))
        else:
            if gap == 0:
                main_h = int(height * ratio)
                thumb_h = height - main_h
            else:
                main_h = int((height - gap) * ratio)
                thumb_h = height - main_h - gap

            main_w = width
            col_sizes = _cell_sizes(main_w, thumb_count, gap)
            col_positions = _cell_positions(col_sizes, gap)

            if side == "top":
                cells.append((0, 0, main_w, main_h))
                thumb_y = main_h + gap
                for index in range(thumb_count):
                    cells.append((
                        col_positions[index],
                        thumb_y,
                        col_sizes[index],
                        thumb_h,
                    ))
            else:
                for index in range(thumb_count):
                    cells.append((
                        col_positions[index],
                        0,
                        col_sizes[index],
                        thumb_h,
                    ))
                cells.append((0, thumb_h + gap, main_w, main_h))

        return cells

    raise ValueError(f"Unsupported layout: {design.layout}")


def apply_logo(canvas: Image.Image, logo_config: LogoConfig) -> Image.Image:
    logo_path = resolve_asset_path(
        logo_config.path,
        [Path.cwd(), logo_config.path.parent],
    )

    logo = Image.open(logo_path).convert("RGBA")
    canvas_w, canvas_h = canvas.size
    max_logo_w = max(1, int(canvas_w * logo_config.size_ratio))
    max_logo_h = max(1, int(canvas_h * logo_config.size_ratio))

    logo_w, logo_h = logo.size
    scale = min(max_logo_w / logo_w, max_logo_h / logo_h)
    new_w = max(1, int(logo_w * scale))
    new_h = max(1, int(logo_h * scale))
    logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if logo_config.opacity < 1.0:
        alpha = logo.split()[3]
        alpha = alpha.point(lambda value: int(value * logo_config.opacity))
        logo.putalpha(alpha)

    padding = logo_config.padding
    positions = {
        "top-left": (padding, padding),
        "top-right": (canvas_w - new_w - padding, padding),
        "bottom-left": (padding, canvas_h - new_h - padding),
        "bottom-right": (canvas_w - new_w - padding, canvas_h - new_h - padding),
    }
    position = positions[logo_config.corner]

    result = canvas.convert("RGBA")
    result.paste(logo, position, logo)
    return result


def save_image(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()

    if suffix in {".jpg", ".jpeg"}:
        image.convert("RGB").save(output_path, quality=95)
    elif suffix == ".webp":
        image.save(output_path, quality=95)
    else:
        image.save(output_path)


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
            fitted = cover_image(img, (w, h), fit_mode=design.fit_mode)
            canvas.paste(fitted, (x, y), fitted)

    if design.logo:
        canvas = apply_logo(canvas, design.logo)

    save_image(canvas, output_path)
    return output_path