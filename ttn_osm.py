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
MAP_PATH = os.path.join(MAP_DIR, "map.png")
DEST_DIR = os.path.expanduser("~/outputs/ttn")
TZ = "America/Los_Angeles"
TIMEOUT_SECONDS = 300  # Give up after 5 minutes

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(MAP_DIR, exist_ok=True)
os.makedirs(DEST_DIR, exist_ok=True)

def check_map_exists():
    """Checks if map.png exists in ~/temp/map."""
    if os.path.exists(MAP_PATH):
        try:
            with Image.open(MAP_PATH) as img:
                img.verify()
            print(f"Base map found at {MAP_PATH}")
            return True
        except Exception:
            print("Existing map.png is corrupted or invalid.")
            return False
    return False

def download_basemap(lat1, lon1, lat2, lon2):
    """Downloads a basemap from an OSM api and resizes to 512x512."""
    print(f"Downloading basemap from provider: ({lat1}, {lon1}) to ({lat2}, {lon2})")
    
    # Use zoom level 7 for higher detail (still manageable tile count)
    zoom = 7
    
    # Calculate tile coordinates for both corners
    def lat_lon_to_tile(lat, lon, z):
        n = 2.0 ** z
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
        return x, y
    
    tile_x1, tile_y1 = lat_lon_to_tile(lat1, lon1, zoom)
    tile_x2, tile_y2 = lat_lon_to_tile(lat2, lon2, zoom)
    
    min_x = min(tile_x1, tile_x2)
    max_x = max(tile_x1, tile_x2)
    min_y = min(tile_y1, tile_y2)
    max_y = max(tile_y1, tile_y2)
    
    # Download tiles and composite
    tile_size = 256
    canvas_width = (max_x - min_x + 1) * tile_size
    canvas_height = (max_y - min_y + 1) * tile_size
    canvas = Image.new("RGB", (canvas_width, canvas_height))
    
    # Pulls a map from an OpenMapTiles API. 
    # You have to fill this in yourself for legal reasons.
    # A list of providers is here: https://wiki.openstreetmap.org/wiki/Raster_tile_providers. 
    # Look at the tiles url column and enter on LINE 78
    # Be sure to comply with the api provider rules and update the attribution tag on LINE 293
  
    tile_urls = []
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            url = f"https://[ENTER THE OSM PROVIDER DETAILS HERE]/{zoom}/{x}/{y}.png"
            tile_urls.append((x, y, url))
    
    print(f"Downloading {len(tile_urls)} tiles at zoom level {zoom}...")
    
    for x, y, url in tile_urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                tile_img = Image.open(response).convert("RGB")
                canvas.paste(tile_img, ((x - min_x) * tile_size, (y - min_y) * tile_size))
        except Exception as e:
            print(f"Warning: Failed to download tile {x},{y}: {e}")
    
    # Convert lat/lon to pixel coordinates within the canvas
    def lat_lon_to_pixel(lat, lon, min_x, min_y, zoom):
        n = 2.0 ** zoom
        tile_size = 256
        x_pixel = ((lon + 180.0) / 360.0 * n * tile_size) - min_x * tile_size
        y_pixel = ((1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n * tile_size) - min_y * tile_size
        return int(x_pixel), int(y_pixel)
    
    px1, py1 = lat_lon_to_pixel(lat1, lon1, min_x, min_y, zoom)
    px2, py2 = lat_lon_to_pixel(lat2, lon2, min_x, min_y, zoom)
    
    crop_left = min(px1, px2)
    crop_right = max(px1, px2)
    crop_top = min(py1, py2)
    crop_bottom = max(py1, py2)
    
    # Ensure crop bounds are valid
    crop_left = max(0, crop_left)
    crop_top = max(0, crop_top)
    crop_right = min(canvas_width, crop_right)
    crop_bottom = min(canvas_height, crop_bottom)
    
    # Crop to exact bounding box
    basemap = canvas.crop((crop_left, crop_top, crop_right, crop_bottom))
    
    # Resize to 512x512
    basemap = basemap.resize((512, 512), Image.Resampling.LANCZOS)
    basemap.save(MAP_PATH)
    print(f"Basemap saved to {MAP_PATH} with dimensions {basemap.size}")

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
                print(f"Progress: {tmt_count}/9 Traffic tiles | {dwro_count}/1 Weather overlay | {txt_count}/2 TXTs")
                last_tmt_count, last_dwro_count, last_txt_count = tmt_count, dwro_count, txt_count
            
            if tmt_count >= 9 and dwro_count >= 1 and txt_count >= 2:
                print("Target conditions reached successfully!")
                break
                
            time.sleep(1)
    finally:
        print("Terminating nrsc5 process...")
        process.terminate()
        process.wait()

def parse_gps_coordinates(txt_file_path):
    """Extracts bounding box coordinates from the DWRI text file."""
    pattern = re.compile(r'Coordinates="\((-?\d+\.\d+),(-?\d+\.\d+)\)";"\((-?\d+\.\d+),(-?\d+\.\d+)\)"')
    with open(txt_file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                return float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))
    return None

def extract_and_download_basemap():
    """Extracts coordinates from DWRI file and downloads basemap if not already present."""
    if check_map_exists():
        return
    
    dwri_files = glob.glob(os.path.join(TEMP_DIR, "*_DWRI_*.txt"))
    if not dwri_files:
        print("No DWRI file found. Cannot download basemap.")
        return
    
    coords = parse_gps_coordinates(dwri_files[0])
    if not coords:
        print("Could not parse coordinates from DWRI file.")
        return
    
    lat1, lon1, lat2, lon2 = coords
    download_basemap(lat1, lon1, lat2, lon2)

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
    """Stitches 3x3 TMT grid and adds the timestamp."""
    print("Processing TMT traffic map...")
    tmt_files = glob.glob(os.path.join(TEMP_DIR, "*_TMT_*.png"))
    
    if not tmt_files:
        print("No traffic tiles collected. Skipping traffic map generation.")
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

def crop_and_overlay_weather():
    """Overlays DWRO on the basemap with timestamps and attribution."""
    print("Processing DWRO weather overlay...")
    dwro_files = glob.glob(os.path.join(TEMP_DIR, "*_DWRO_*.png"))
    
    if not dwro_files:
        print("Missing DWRO files. Skipping weather map step.")
        return

    if not os.path.exists(MAP_PATH):
        print("Base map file missing.")
        return

    base_map = Image.open(MAP_PATH).convert("RGBA")
    
    dwro_img = Image.open(dwro_files[0]).convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
    final_weather = Image.alpha_composite(base_map, dwro_img)
    
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
    
    # Add provider attribution at bottom right in 8pt font
    attribution_text = "© PROVIDER © OpenMapTiles © OpenStreetMap"
    attribution_font = get_large_font(size=8)
    
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), attribution_text, font=attribution_font)
    text_width = bbox[2] - bbox[0]
    attr_x = (512 - text_width)
    attr_y = 512 - 9

    # Attribution Text Fill Color should be set so it doesn't stick out too much.
    draw.text((attr_x, attr_y), attribution_text, fill="gray", font=attribution_font)
    
    final_weather.save(os.path.join(TEMP_DIR, "weatherimgTTN.png"))
    print("Weather map generated successfully with timestamp and attribution.")

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
    monitor_and_harvest()
    extract_and_download_basemap()
    process_traffic_grid()
    crop_and_overlay_weather()
    move_final_outputs()
    cleanup_temp()
