#!/usr/bin/env python3

import datetime
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

# Configurations
HOME_DIR = Path.home()
DEST_DIR = Path("/somewhere")
TARGET_COUNT = 10
COMMAND = ["nrsc5", "97.3", "0", "-o", "1.png", "--dump-aas-files", str(HOME_DIR)]


def get_captured_files():
    """Finds all matching PNG files dumped by nrsc5 in the home directory."""
    pattern = re.compile(
        r"^\d+_(trafficMap_[0-2]_[0-2]|WeatherImage_[0-2]_[0-2])_[a-zA-Z0-9]+\.png$"
    )
    all_pngs = HOME_DIR.glob("*.png")
    return [f for f in all_pngs if pattern.match(f.name)]


def get_font(size):
    """Attempts to load a standard TrueType font to support custom sizing."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "Arial.ttf",
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            continue

    print("Warning: Could not find TrueType font. Falling back to default.")
    return ImageFont.load_default()


def process_images(files):
    """Stitches traffic map tiles, overlays weather data, and moves results."""
    print("Processing captured images...")

    traffic_tiles = {}
    weather_file = None

    for f in files:
        if "trafficMap" in f.name:
            match = re.search(r"trafficMap_([0-2])_([0-2])", f.name)
            if match:
                row, col = map(int, match.groups())
                traffic_tiles[(row, col)] = f
        elif "WeatherImage" in f.name:
            weather_file = f

    # 1. Assemble the 3x3 Traffic Map
    canvas = Image.new("RGBA", (600, 600))
    for (row, col), filepath in traffic_tiles.items():
        with Image.open(filepath) as tile:
            tile = tile.resize((200, 200))
            canvas.paste(tile, (col * 200, row * 200))

    # 2. Add Timestamp to Traffic Map (Pacific Time, Black, Larger with Overlay Box)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pacific_tz = ZoneInfo("America/Los_Angeles")
    timestamp = datetime.datetime.now(pacific_tz).strftime("%m/%d %H:%M")

    font = get_font(size=24)

    # Calculate exact text dimensions to size the background box dynamically
    text_bbox = draw.textbbox((0, 0), timestamp, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Target position for the text (bottom-right area)
    text_x = 580 - text_width
    text_y = 580 - text_height

    # Define background box padding
    padding_x = 8
    padding_y = 6

    box_x1 = text_x - padding_x
    box_y1 = text_y - padding_y
    box_x2 = text_x + text_width + padding_x
    box_y2 = text_y + text_height + padding_y

    # Draw semi-transparent white box (Alpha = 180 out of 255)
    draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(255, 255, 255, 180))

    # Draw the text in black color on top of the box
    draw.text((text_x, text_y), timestamp, fill="black", font=font)

    # Composite the overlay layer onto the main map canvas
    canvas = Image.alpha_composite(canvas, overlay)

    traffic_path = HOME_DIR / "trafficmap.png"
    canvas.save(traffic_path)
    print(f"Created base traffic map: {traffic_path}")

    # 3. Create Weather Overlay Image
    if weather_file and weather_file.exists():
        weather_canvas = canvas.copy()
        with Image.open(weather_file) as weather_img:
            weather_img = weather_img.resize((600, 600)).convert("RGBA")
            weather_canvas.alpha_composite(weather_img)

        weather_path = HOME_DIR / "weatherimg.png"
        weather_canvas.save(weather_path)
        print(f"Created weather overlay map: {weather_path}")
    else:
        print("Warning: WeatherImage overlay file missing. Skipping overlay.")
        weather_path = None

    # 4. Move outputs to destination folder using shutil.move (cross-drive safe)
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    if traffic_path.exists():
        shutil.move(str(traffic_path), str(DEST_DIR / "trafficmap.png"))
    if weather_path and weather_path.exists():
        shutil.move(str(weather_path), str(DEST_DIR / "weatherimg.png"))

    print(f"Successfully moved final files to {DEST_DIR}")


def cleanup_home():
    """Deletes all png and jpg files from the home directory."""
    print("Cleaning up image files from home directory...")
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        for filepath in HOME_DIR.glob(ext):
            try:
                filepath.unlink()
            except Exception as e:
                print(f"Could not delete {filepath.name}: {e}")
    print("Cleanup complete.")


def main():
    print(f"Starting nrsc5 command...")
    process = subprocess.Popen(
        COMMAND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    try:
        while True:
            captured_files = get_captured_files()
            count = len(captured_files)
            print(f"Downloaded {count}/{TARGET_COUNT} files...", end="\r")

            if count >= TARGET_COUNT:
                print(f"\nTarget of {TARGET_COUNT} files reached.")
                break

            time.sleep(2)

    finally:
        print("Terminating nrsc5 process...")
        process.terminate()
        process.wait()

    captured_files = get_captured_files()
    if len(captured_files) >= TARGET_COUNT:
        process_images(captured_files)

    cleanup_home()


if __name__ == "__main__":
    main()
