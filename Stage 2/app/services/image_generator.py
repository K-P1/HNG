from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import PIL
import os
from app.config import settings


def _text(draw: ImageDraw.ImageDraw, xy, text: str, fill=(34, 34, 34), anchor=None, font=None):
    try:
        draw.text(xy, text, fill=fill, anchor=anchor, font=font)
    except TypeError:
        draw.text(xy, text, fill=fill, font=font)


def _right_text(draw: ImageDraw.ImageDraw, x_right: int, y: int, text: str, fill=(34, 34, 34), font=None):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
    except Exception:
        width = len(text) * 6  # rough fallback
    _text(draw, (x_right - width, y), text, fill=fill, font=font)


def generate_summary_image(top_countries, total, timestamp):
    """Generate a clean summary image with a simple table of the top 5 GDP countries.

    Columns: Rank | Country | Estimated GDP
    Footer: Total countries and last refresh timestamp.
    """
    cache_dir = settings.BASE_DIR / "cache"
    os.makedirs(cache_dir, exist_ok=True)

    # Canvas
    W, H = 800, 480
    bg = (255, 255, 255)
    fg = (34, 34, 34)
    grid = (225, 230, 240)
    header_bg = (245, 247, 250)
    accent = (60, 99, 243)

    img = Image.new("RGB", (W, H), color=bg)
    draw = ImageDraw.Draw(img)

    def _resolve_font_path(font_filename: str) -> Path | None:
        base = Path(PIL.__file__).parent
        candidates = [
            base / font_filename,
            base / "fonts" / font_filename,
            base.parent / font_filename,
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def _load_ttf(name: str, size: int):
        p = _resolve_font_path(name)
        if p is not None:
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
        return None

    font_title = _load_ttf("DejaVuSans-Bold.ttf", 20) or ImageFont.load_default()
    font_meta = _load_ttf("DejaVuSans.ttf", 16) or ImageFont.load_default()
    font_header = _load_ttf("DejaVuSans-Bold.ttf", 16) or ImageFont.load_default()
    font_cell = _load_ttf("DejaVuSans.ttf", 16) or ImageFont.load_default()

    # Title
    margin = 24
    y = margin
    _text(draw, (margin, y), "Country Currency & Exchange — Summary", fill=accent, font=font_title)
    y += 30
    _text(draw, (margin, y), f"Total Countries: {total}  •  Last Refresh: {timestamp}", fill=(90, 90, 90), font=font_meta)
    y += 24

    # Table geometry
    table_top = y + 10
    table_left = margin
    table_right = W - margin
    row_h = 38
    header_h = 40

    # Columns (Rank | Country | Estimated GDP)
    col_rank_w = 70
    col_country_w = int((table_right - table_left - col_rank_w) * 0.6)
    col_gdp_w = (table_right - table_left) - col_rank_w - col_country_w

    x_rank = table_left
    x_country = x_rank + col_rank_w
    x_gdp = x_country + col_country_w

    # Header background
    draw.rectangle([table_left, table_top, table_right, table_top + header_h], fill=header_bg)
    # Header text
    _text(draw, (x_rank + 12, table_top + 11), "#", fill=fg, font=font_header)
    _text(draw, (x_country + 12, table_top + 11), "Country", fill=fg, font=font_header)
    _right_text(draw, x_gdp + col_gdp_w - 12, table_top + 11, "Estimated GDP (USD)", fill=fg, font=font_header)

    # Header bottom line
    draw.line([table_left, table_top + header_h, table_right, table_top + header_h], fill=grid, width=1)

    # Rows
    y_row = table_top + header_h
    max_rows = 5
    rows = list(top_countries[:max_rows])

    def _fmt_currency_compact(val):
        if val is None:
            return "-"
        try:
            n = float(val)
        except Exception:
            return "-"
        absn = abs(n)
        suffix = ""
        div = 1.0
        if absn >= 1_000_000_000_000:
            suffix = "T"; div = 1_000_000_000_000
        elif absn >= 1_000_000_000:
            suffix = "B"; div = 1_000_000_000
        elif absn >= 1_000_000:
            suffix = "M"; div = 1_000_000
        elif absn >= 1_000:
            suffix = "K"; div = 1_000
        if suffix:
            num = n / div
            s = f"{num:.1f}".rstrip("0").rstrip(".")
            return f"${s}{suffix}"
        # for smaller numbers, keep separators
        return f"${n:,.0f}"
    for i in range(max_rows):
        if i % 2 == 0:
            draw.rectangle([table_left, y_row, table_right, y_row + row_h], fill=(252, 253, 255))

        if i < len(rows):
            c = rows[i]
            rank = str(i + 1)
            name = getattr(c, "name", "-") or "-"
            gdp_val = getattr(c, "estimated_gdp", None)
            gdp = _fmt_currency_compact(gdp_val)

            _text(draw, (x_rank + 12, y_row + 10), rank, fill=fg, font=font_cell)
            _text(draw, (x_country + 12, y_row + 10), name, fill=fg, font=font_cell)
            _right_text(draw, x_gdp + col_gdp_w - 12, y_row + 10, gdp, fill=fg, font=font_cell)

        # Row separator
        draw.line([table_left, y_row + row_h, table_right, y_row + row_h], fill=grid, width=1)
        y_row += row_h

    # Outline table
    draw.rectangle([table_left, table_top, table_right, y_row], outline=grid, width=1)

    # Footer note
    footer_y = y_row + 16
    _text(draw, (margin, footer_y), "Data sources: Rest Countries API, Exchange Rates API (base USD)", fill=(110, 110, 110), font=font_meta)

    img.save(str(cache_dir / "summary.png"))
