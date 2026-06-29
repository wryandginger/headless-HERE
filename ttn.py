#!/usr/bin/env python3
import os
import re
import glob
import time
import math
import shutil
import subprocess
import urllib.request
from zoneinfo import ZoneInfo
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
FREQ = "95.7"
CHANNEL = "0"
TEMP_DIR = os.path.expanduser("~/temp")
MAP_DIR = os.path.join(TEMP_DIR, "map")
US_MAP_PATH = os.path.join(MAP_DIR, "us.png")
DEST_DIR = os.path.expanduser("~/outputs/ttn")
TZ = "America/Los_Angeles"
TIMEOUT_SECONDS = 300  # Give up after 5 minutes

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(MAP_DIR, exist_ok=True)
os.makedirs(DEST_DIR, exist_ok=True)

def download_us_map():
    """Downloads the base United States map from GitHub if missing or unreadable."""
    is_valid_image = False
    if os.path.exists(US_MAP_PATH):
        try:
            with Image.open(US_MAP_PATH) as img:
                img.verify()
            is_valid_image = True
        except Exception:
            print("Existing us.png is corrupted or invalid. Deleting and re-downloading...")
            os.remove(US_MAP_PATH)

    if not is_valid_image:
        print("Downloading base US map from GitHub...")
        url = "https://github.com/wryandginger/hdfm/blob/master/maps/us_map.png?raw=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as response, open(US_MAP_PATH, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            print(f"Base map successfully saved and verified at {US_MAP_PATH}")
        except Exception as e:
            print(f"Error downloading base map: {e}")

def monitor_and_harvest():
    """Runs nrsc5 and prints progress, terminating gracefully if target is reached or timeout occurs."""
    cmd = ["nrsc5", FREQ, CHANNEL, "-o", os.path.join(TEMP_DIR, "1.png"), "--dump-aas-files", TEMP_DIR]
    print(f"Starting command: {' '.join(cmd)}")
    
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Monitoring incoming HD Radio files...")
    
    last_tmt_count, last_dwro_count, last_txt_count = -1, -1, -1
    tmt_pattern = re.compile(r'_TMT_.*_([1-3])_([1-3])_')
    
    start_time = time.time()
    
    try:
        while True:
            # Check timeout condition
            elapsed_time = time.time() - start_time
            if elapsed_time >= TIMEOUT_SECONDS:
                print(f"Reached timeout of {TIMEOUT_SECONDS} seconds. Exiting data collection gracefully...")
                break

            png_files = glob.glob(os.path.join(TEMP_DIR, "*.png"))
            txt_files = glob.glob(os.path.join(TEMP_DIR, "*.txt"))
            
            found_tmt_slots = set()
            dwro_count = 0
            for f in png_files:
                basename = os.path.basename(f)
                match = tmt_pattern.search(basename)
                if match:
                    found_tmt_slots.add((match.group(1), match.group(2)))
                elif "_DWRO_" in basename:
                    dwro_count += 1
                    
            tmt_count = len(found_tmt_slots)
            txt_count = len(txt_files)
            
            if tmt_count != last_tmt_count or dwro_count != last_dwro_count or txt_count != last_txt_count:
                print(f"Progress: {tmt_count}/9 unique TMT tiles | {dwro_count}/1 DWRO overlay | {txt_count}/2 TXTs")
                last_tmt_count, last_dwro_count, last_txt_count = tmt_count, dwro_count, txt_count
            
            if tmt_count >= 9 and dwro_count >= 1 and txt_count >= 2:
                print("Target conditions reached successfully!")
                break
                
            time.sleep(1)
    finally:
        print("Terminating nrsc5 process...")
        process.terminate()
        process.wait()

def get_large_font(size):
    """Attempts to load a standard system font at a larger size, falling back safely if missing."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "Arial Bold.ttf"
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            continue
    return ImageFont.load_default()

def process_traffic_grid():
    """Stitches 3x3 TMT grid and adds a large custom time zone timestamp."""
    print("Processing TMT traffic map...")
    tmt_files = glob.glob(os.path.join(TEMP_DIR, "*_TMT_*.png"))
    
    if not tmt_files:
        print("No TMT files collected. Skipping traffic map generation.")
        return

    grid_map = {}
    pattern = re.compile(r'_TMT_.*_(\d)_(\d)_')
    for f in tmt_files:
        match = pattern.search(os.path.basename(f))
        if match:
            grid_map[(int(match.group(1)), int(match.group(2)))] = f

    canvas = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    for (row, col), filepath in grid_map.items():
        try:
            tile = Image.open(filepath).convert("RGBA")
            canvas.paste(tile, ((col - 1) * 200, (row - 1) * 200))
        except Exception as e:
            print(f"Failed to paste tile {row}_{col}: {e}")

    # Enforce configured time zone for timestamping
    draw = ImageDraw.Draw(canvas)
    local_time = datetime.now(ZoneInfo(TZ))
    timestamp_str = local_time.strftime("%m/%d %H:%M")
    
    font = get_large_font(size=24)
    
    # Calculate box bounds dynamically or use padding adjustments
    text_w = 170
    text_h = 30
    text_x = 600 - text_w - 10
    text_y = 600 - text_h - 10
    
    # Draw background box and text overlay
    draw.rectangle([text_x - 5, text_y - 2, 590, 590], fill="black")
    draw.text((text_x, text_y), timestamp_str, fill="white", font=font)
    
    output_path = os.path.join(TEMP_DIR, "trafficmapTTN.png")
    canvas.save(output_path)
    print(f"Traffic map saved to {output_path}")

def parse_gps_coordinates(txt_file_path):
    """Extracts bounding box coordinates from the DWRI text file."""
    pattern = re.compile(r'Coordinates="\((-?\d+\.\d+),(-?\d+\.\d+)\)";"\((-?\d+\.\d+),(-?\d+\.\d+)\)"')
    with open(txt_file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                return float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))
    return None

def crop_and_overlay_weather():
    """Crops the base US map using your specialized ratio equations, then overlays DWRO with a timestamp."""
    print("Processing DWRI coordinates and DWRO weather overlay...")
    dwri_files = glob.glob(os.path.join(TEMP_DIR, "*_DWRI_*.txt"))
    dwro_files = glob.glob(os.path.join(TEMP_DIR, "*_DWRO_*.png"))
    
    if not dwri_files or not dwro_files:
        print("Missing DWRI or DWRO files. Skipping weather map step.")
        return

    coords = parse_gps_coordinates(dwri_files[0])
    if not coords:
        print("Could not parse coordinates from DWRI file.")
        return
    lat1, lon1, lat2, lon2 = coords

    if not os.path.exists(US_MAP_PATH):
        print("Base map file missing.")
        return
        
    US_map = Image.open(US_MAP_PATH)

    y_top_coord = math.asinh(math.tan(math.radians(52.482780)))

    linear_lat1 = y_top_coord - math.asinh(math.tan(math.radians(lat1)))
    linear_lat2 = y_top_coord - math.asinh(math.tan(math.radians(lat2)))

    pixel_x1 = (lon1 + 130.781250) * 7162 / 39.34135
    pixel_x2 = (lon2 + 130.781250) * 7162 / 39.34135

    pixel_y1 = linear_lat1 * 3565 / (y_top_coord - math.asinh(math.tan(math.radians(38.898))))
    pixel_y2 = linear_lat2 * 3565 / (y_top_coord - math.asinh(math.tan(math.radians(38.898))))

    x_min, x_max = min(pixel_x1, pixel_x2), max(pixel_x1, pixel_x2)
    y_min, y_max = min(pixel_y1, pixel_y2), max(pixel_y1, pixel_y2)

    cropped_map = US_map.crop((int(x_min), int(y_min), int(x_max), int(y_max)))
    cropped_map = cropped_map.resize((512, 512), Image.Resampling.LANCZOS).convert("RGBA")
    cropped_map.save(os.path.join(TEMP_DIR, "map.png"))

    dwro_img = Image.open(dwro_files[0]).convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
    final_weather = Image.alpha_composite(cropped_map, dwro_img)
    
    # Add large timestamp on the weather map using configured time zone
    draw = ImageDraw.Draw(final_weather)
    local_time = datetime.now(ZoneInfo(TZ))
    timestamp_str = local_time.strftime("%m/%d %H:%M")
    
    font = get_large_font(size=20)
    
    text_w = 145
    text_h = 25
    text_x = 512 - text_w - 10
    text_y = 512 - text_h - 10
    
    draw.rectangle([text_x - 5, text_y - 2, 502, 502], fill="black")
    draw.text((text_x, text_y), timestamp_str, fill="white", font=font)
    
    final_weather.save(os.path.join(TEMP_DIR, "weatherimgTTN.png"))
    print("Weather map generated successfully with timestamp.")

def move_final_outputs():
    """Moves final compiled files to the destination directory."""
    print(f"Moving final images to {DEST_DIR}...")
    targets = ["trafficmapTTN.png", "weatherimgTTN.png"]
    for t in targets:
        src = os.path.join(TEMP_DIR, t)
        if os.path.exists(src):
            shutil.move(src, os.path.join(DEST_DIR, t))

def cleanup_temp():
    """Deletes temporary working image/text files, keeping the base map folder."""
    print("Cleaning up temp directory extensions...")
    extensions = ("*.png", "*.jpg", "*.jpeg", "*.txt")
    for ext in extensions:
        files = glob.glob(os.path.join(TEMP_DIR, ext))
        for f in files:
            try:
                os.remove(f)
            except Exception as e:
                print(f"Error removing {f}: {e}")

if __name__ == "__main__":
    download_us_map()
    monitor_and_harvest()
    process_traffic_grid()
    crop_and_overlay_weather()
    move_final_outputs()
    cleanup_temp()
