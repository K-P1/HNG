from PIL import Image, ImageDraw
import os
from app.config import settings

def generate_summary_image(top_countries, total, timestamp):
    cache_dir = settings.BASE_DIR / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    img = Image.new("RGB", (600, 400), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    y = 20
    draw.text((20, y), f"Total Countries: {total}", fill="white")
    y += 40
    draw.text((20, y), "Top 5 by Estimated GDP:", fill="white")
    y += 30

    for idx, c in enumerate(top_countries[:5]):
        draw.text((40, y + idx*30), f"{idx+1}. {c.name} - {round(c.estimated_gdp or 0, 2)}", fill="white")

    y += 200
    draw.text((20, y), f"Last Refresh: {timestamp}", fill="gray")
    img.save(str(cache_dir / "summary.png"))
