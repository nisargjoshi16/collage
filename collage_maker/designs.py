"""Collage design definitions and presets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CORNER_CHOICES = ("top-left", "top-right", "bottom-left", "bottom-right")

PRESETS: dict[str, dict[str, Any]] = {
    "grid_2x2": {
        "layout": "grid",
        "rows": 2,
        "cols": 2,
        "output_size": [1200, 1200],
        "gap": 8,
        "background": "#FFFFFF",
    },
    "grid_3x3": {
        "layout": "grid",
        "rows": 3,
        "cols": 3,
        "output_size": [1500, 1500],
        "gap": 6,
        "background": "#FFFFFF",
    },
    "horizontal_strip": {
        "layout": "horizontal",
        "output_size": [1920, 600],
        "gap": 10,
        "background": "#1a1a1a",
    },
    "vertical_strip": {
        "layout": "vertical",
        "output_size": [600, 1920],
        "gap": 10,
        "background": "#1a1a1a",
    },
    "featured_left": {
        "layout": "featured",
        "featured_ratio": 0.65,
        "featured_side": "left",
        "output_size": [1600, 900],
        "gap": 8,
        "background": "#FFFFFF",
    },
    "featured_top": {
        "layout": "featured",
        "featured_ratio": 0.6,
        "featured_side": "top",
        "output_size": [1200, 1600],
        "gap": 8,
        "background": "#FFFFFF",
    },
}


@dataclass
class LogoConfig:
    path: Path
    corner: str = "bottom-right"
    size_ratio: float = 0.12
    padding: int = 24
    opacity: float = 1.0

    def __post_init__(self) -> None:
        if self.corner not in CORNER_CHOICES:
            raise ValueError(
                f"Invalid logo corner '{self.corner}'. "
                f"Choose from: {', '.join(CORNER_CHOICES)}"
            )
        if not 0 < self.size_ratio <= 0.5:
            raise ValueError("logo size_ratio must be between 0 and 0.5")
        if not 0 < self.opacity <= 1.0:
            raise ValueError("logo opacity must be between 0 and 1")


@dataclass
class CollageDesign:
    layout: str
    output_size: tuple[int, int]
    gap: int = 8
    background: str = "#FFFFFF"
    rows: int = 2
    cols: int = 2
    featured_ratio: float = 0.6
    featured_side: str = "left"
    logo: LogoConfig | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollageDesign:
        layout = data.get("layout", "grid")
        output_size = tuple(data.get("output_size", [1200, 1200]))
        if len(output_size) != 2:
            raise ValueError("output_size must be [width, height]")

        logo = None
        if "logo" in data:
            logo_data = data["logo"]
            if isinstance(logo_data, str):
                logo = LogoConfig(path=Path(logo_data))
            else:
                logo = LogoConfig(
                    path=Path(logo_data["path"]),
                    corner=logo_data.get("corner", "bottom-right"),
                    size_ratio=logo_data.get("size_ratio", logo_data.get("size", 0.12)),
                    padding=logo_data.get("padding", 24),
                    opacity=logo_data.get("opacity", 1.0),
                )

        return cls(
            layout=layout,
            output_size=(int(output_size[0]), int(output_size[1])),
            gap=int(data.get("gap", 8)),
            background=data.get("background", "#FFFFFF"),
            rows=int(data.get("rows", 2)),
            cols=int(data.get("cols", 2)),
            featured_ratio=float(data.get("featured_ratio", 0.6)),
            featured_side=data.get("featured_side", "left"),
            logo=logo,
        )

    def validate(self) -> None:
        valid_layouts = ("grid", "horizontal", "vertical", "featured")
        if self.layout not in valid_layouts:
            raise ValueError(
                f"Invalid layout '{self.layout}'. "
                f"Choose from: {', '.join(valid_layouts)}"
            )
        if self.gap < 0:
            raise ValueError("gap must be non-negative")
        if self.layout == "grid" and (self.rows < 1 or self.cols < 1):
            raise ValueError("grid layout requires rows and cols >= 1")
        if self.layout == "featured" and not 0.2 <= self.featured_ratio <= 0.85:
            raise ValueError("featured_ratio must be between 0.2 and 0.85")
        if self.featured_side not in ("left", "right", "top", "bottom"):
            raise ValueError("featured_side must be left, right, top, or bottom")


def load_design(source: str | Path) -> CollageDesign:
    """Load a design from a preset name, JSON file path, or JSON string."""
    source_str = str(source).strip()

    if source_str in PRESETS:
        design = CollageDesign.from_dict(PRESETS[source_str])
        design.validate()
        return design

    path = Path(source_str)
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        design = CollageDesign.from_dict(data)
        design.validate()
        return design

    try:
        data = json.loads(source_str)
        design = CollageDesign.from_dict(data)
        design.validate()
        return design
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Design '{source}' is not a preset, valid file, or JSON string."
        ) from exc


def list_presets() -> list[str]:
    return sorted(PRESETS.keys())