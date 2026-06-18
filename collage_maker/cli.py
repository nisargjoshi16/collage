"""Command-line interface for collage maker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .collage import create_collage
from .designs import CORNER_CHOICES, list_presets, load_design


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create image collages from a folder using a design template.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Design input can be:
  - A preset name: {", ".join(list_presets())}
  - A path to a JSON design file
  - An inline JSON string

Examples:
  python main.py ./photos --design grid_3x3 -o collage.png
  python main.py ./photos --design designs/grid_2x2.json --logo logo.png
  python main.py ./photos --design designs/featured.json --logo logo.png --logo-corner top-right
        """,
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing source images",
    )
    parser.add_argument(
        "--design", "-d",
        required=True,
        help="Collage design: preset name, JSON file path, or JSON string",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("output/collage.png"),
        help="Output image path (default: output/collage.png)",
    )
    parser.add_argument(
        "--logo", "-l",
        type=Path,
        default=None,
        help="Logo image to place in a corner (overrides design file logo)",
    )
    parser.add_argument(
        "--logo-corner",
        choices=CORNER_CHOICES,
        default="bottom-right",
        help="Corner for logo placement (default: bottom-right)",
    )
    parser.add_argument(
        "--logo-size",
        type=float,
        default=0.12,
        help="Logo size as fraction of canvas width (default: 0.12)",
    )
    parser.add_argument(
        "--logo-padding",
        type=int,
        default=24,
        help="Padding from canvas edge in pixels (default: 24)",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Maximum number of images to include",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available design presets and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        print("Available presets:")
        for name in list_presets():
            print(f"  - {name}")
        return 0

    try:
        design = load_design(args.design)

        if args.logo:
            from .designs import LogoConfig

            design.logo = LogoConfig(
                path=args.logo,
                corner=args.logo_corner,
                size_ratio=args.logo_size,
                padding=args.logo_padding,
            )

        output = create_collage(
            image_folder=args.folder,
            design=design,
            output_path=args.output,
            max_images=args.max_images,
        )
        print(f"Collage saved to {output}")
        return 0

    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())