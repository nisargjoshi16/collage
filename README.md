# Collage Maker

Create image collages from a folder of photos using customizable design templates, with optional logo overlay in any corner.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Use a built-in preset
python main.py ./photos --design grid_3x3 -o output/collage.png

# Use a JSON design file
python main.py ./photos --design designs/grid_2x2.json -o output/collage.png

# Add a logo via CLI (overrides design file logo)
python main.py ./photos --design grid_2x2 --logo assets/logo.png --logo-corner bottom-right

# List available presets
python main.py --list-presets
```

## Design Input

Designs can be provided as:

1. **Preset name** — `grid_2x2`, `grid_3x3`, `horizontal_strip`, `vertical_strip`, `featured_left`, `featured_top`
2. **JSON file** — see `designs/` for examples
3. **Inline JSON** — pass a JSON string to `--design`

### Design Options

| Field | Description |
|-------|-------------|
| `layout` | `grid`, `horizontal`, `vertical`, or `featured` |
| `output_size` | `[width, height]` in pixels |
| `gap` | Spacing between images in pixels |
| `background` | Hex color for canvas background |
| `rows` / `cols` | Grid dimensions (grid layout) |
| `featured_ratio` | Size of main image (featured layout) |
| `featured_side` | `left`, `right`, `top`, or `bottom` |
| `logo` | Logo config: `path`, `corner`, `size_ratio`, `padding`, `opacity` |

### Logo Corners

`top-left`, `top-right`, `bottom-left`, `bottom-right`

## Supported Image Formats

JPEG, PNG, WebP, BMP, GIF, TIFF