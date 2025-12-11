# Python script that takes an input `manifest.json` downloaded from Liiive
# extracts and crops to SVG polygon an image for every 
# very brittle, not sure if it will work for shapes other than Polygons (e.g. rectangles)
# absolutely vibecoded and not suitable for robust use


import json
import os
import re
import requests
from PIL import Image, ImageDraw
from io import BytesIO
from xml.etree import ElementTree as ET

# --- Configuration ---
LOCAL_MANIFEST_PATH = "manifest.json"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_polygon_points(svg_value):
    """Extract (x, y) tuples from SvgSelector polygon"""
    root = ET.fromstring(svg_value)
    polygon = root.find(".//{http://www.w3.org/2000/svg}polygon")
    if polygon is None:
        polygon = root.find(".//polygon")  # fallback if no namespace
    if polygon is None:
        return []
    points_str = polygon.attrib["points"]
    points = []
    for pt in points_str.strip().split():
        x_str, y_str = pt.split(",")
        points.append((float(x_str), float(y_str)))
    return points

def polygon_to_bbox(points):
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    x0, y0 = min(xs), min(ys)
    x1, y1 = max(xs), max(ys)
    return int(x0), int(y0), int(x1), int(y1)

def crop_polygon_from_image(img, points, scale=4):
    """
    Crop the image to the polygon with anti-aliased edges.
    
    Args:
        img: PIL.Image instance
        points: list of (x, y) tuples
        scale: supersampling factor for anti-aliasing
    """
    # Scale up coordinates
    scaled_size = (img.width * scale, img.height * scale)
    scaled_points = [(x * scale, y * scale) for x, y in points]

    # Create high-res mask
    mask = Image.new("L", scaled_size, 0)
    ImageDraw.Draw(mask).polygon(scaled_points, outline=1, fill=255)

    # Downsample mask with ANTIALIAS
    mask = mask.resize(img.size, Image.Resampling.LANCZOS)

    # Apply mask to original image
    result = Image.new("RGBA", img.size)
    result.paste(img, mask=mask)

    # Crop to bounding box for smaller file
    bbox = polygon_to_bbox(points)
    result = result.crop(bbox)
    return result


def fetch_iiif_region(iiif_base, bbox, max_width=2000):
    """Fetch a cropped IIIF region via IIIF Image API"""
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    region_str = f"{x0},{y0},{width},{height}"
    size_str = f"{width}," if width > height else f",{height}"
    url = f"{iiif_base}/{region_str}/full/0/default.jpg"
    resp = requests.get(url)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content))

def main():
    with open(LOCAL_MANIFEST_PATH) as f:
        manifest = json.load(f)

    count = 1
    for canvas in manifest.get("items", []):
        # --- Get the IIIF image service from painting annotation ---
        painting_annotation = None
        try:
            painting_annotation = canvas["items"][0]["items"][0]
        except (KeyError, IndexError):
            continue

        iiif_base = painting_annotation.get("body", {}).get("service", [{}])[0].get("@id")
        if not iiif_base:
            continue

        # --- Process polygon annotations ---
        for annotation_page in canvas.get("annotations", []):
            for annotation in annotation_page.get("items", []):
                target = annotation.get("target", {})
                selector = target.get("selector")
                if not selector or selector.get("type") != "SvgSelector":
                    continue
                points = extract_polygon_points(selector["value"])
                if not points:
                    continue
                bbox = polygon_to_bbox(points)
                # Fetch IIIF region
                try:
                    img = fetch_iiif_region(iiif_base, bbox)
                    # Crop polygon exactly
                    cropped = crop_polygon_from_image(img, [(x - bbox[0], y - bbox[1]) for x, y in points])
                    filename = os.path.join(OUTPUT_DIR, f"{count:04d}.png")
                    cropped.save(filename)
                    print(f"Saved {filename}")
                    count += 1
                except Exception as e:
                    print(f"Failed to process annotation {annotation.get('id')}: {e}")

if __name__ == "__main__":
    main()
