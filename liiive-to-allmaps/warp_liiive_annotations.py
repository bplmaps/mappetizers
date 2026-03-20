#!/usr/bin/env python3
"""
warp_liiive_annotations.py

Warps commenting annotations from a liiive/IIIF manifest into geographic GeoJSON by:
  1. Parsing the liiive manifest to extract per-canvas commenting annotations
  2. Fetching a Georeference Annotation — either from --georef (explicit) or by
     deriving it from the manifest's own "id" field via the Allmaps API
     (https://annotations.allmaps.org/?url=<manifest_id>)
  3. Matching each annotation's canvas to the correct georef map entry
  4. Extracting pixel-space SVG geometry and classifying it as LINE or POLYGON
  5. Piping each SVG through `allmaps transform svg` to warp to WGS84 GeoJSON
  6. Writing two output files to --output directory:
       polygon.geojson  — filled shapes (polygon, ellipse, rect, xywh)
       line.geojson     — open paths (polyline, path element)
     Annotations with no selector, or an unresolvable selector, are skipped.

Shape classification
--------------------
  POLYGON  : <polygon>, <ellipse>, <rect>, <circle>, or an xywh fragment selector
  LINE     : <polyline>, <path>
  (no selector / unsupported element → skipped with a warning)

Image ID matching
-----------------
  The georef index is keyed by IIIF image service URL
  (e.g. https://iiif.digitalcommonwealth.org/iiif/2/commonwealth:63960f677).
  The liiive manifest may or may not include painting annotations with an
  explicit image body.  When a painting body is absent (as in stripped-down
  liiive exports), the image service URL is reconstructed from the canvas ID:
  the final path segment of the canvas ID is taken as the image identifier
  and each known image-service base URL from the georef index is tried in turn.

Prerequisites:
  npm install -g @allmaps/cli
  (verify with: allmaps --version)

Usage:
  # Auto-fetch georef, write to current directory:
  python warp_liiive_annotations.py --liiive path/to/liiive-manifest.json

  # Explicit georef, write to a specific directory:
  python warp_liiive_annotations.py \\
    --liiive  path/to/liiive-manifest.json \\
    --georef  https://annotations.allmaps.org/manifests/3a4dfc37b2bc9acf \\
    --output  /path/to/output/dir
"""

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional


# Shape-type constants
SHAPE_POLYGON = "polygon"
SHAPE_LINE    = "line"


# ---------------------------------------------------------------------------
# 1. Loading data
# ---------------------------------------------------------------------------

def load_json(path_or_url: str) -> dict:
    """Load JSON from a local file path or an http(s) URL."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        print(f"  Fetching {path_or_url} ...")
        req = urllib.request.Request(
            path_or_url,
            headers={"Accept": "application/json, application/ld+json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    else:
        with open(path_or_url, "r", encoding="utf-8") as fh:
            return json.load(fh)


def fetch_georef_for_manifest(manifest: dict) -> dict:
    """
    Derive the Allmaps Georeference Annotation for a manifest by hitting:

        https://annotations.allmaps.org/?url=<manifest["id"]>

    Raises ValueError if the manifest has no "id", or if the API returns an
    empty / unrecognised response.
    """
    manifest_url = manifest.get("id", "").strip()
    if not manifest_url:
        raise ValueError(
            'The liiive manifest has no top-level "id" field, '
            "so a georef annotation cannot be derived automatically. "
            "Please supply --georef explicitly."
        )

    lookup_url = f"https://annotations.allmaps.org/?url={manifest_url}"
    print(f"  No --georef supplied; looking up georef annotation via Allmaps API:")
    print(f"  {lookup_url}")

    req = urllib.request.Request(
        lookup_url,
        headers={"Accept": "application/json, application/ld+json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"Allmaps API returned HTTP {exc.code} for {lookup_url}. "
            "The manifest may not have been georeferenced yet, or the URL "
            "may be unreachable."
        ) from exc

    items = data.get("items", [])
    if not items:
        raise ValueError(
            f"Allmaps API returned an empty AnnotationPage for {manifest_url}. "
            "The manifest may not have been georeferenced yet."
        )

    print(f"  Retrieved georef annotation with {len(items)} map(s).")
    return data


# ---------------------------------------------------------------------------
# 2. Parse the liiive manifest
# ---------------------------------------------------------------------------

def extract_liiive_annotations(manifest: dict) -> list:
    """
    Walk manifest['items'] (canvases) and collect every *commenting* annotation.

    Canvas width/height are read directly from the canvas object — this works
    whether or not painting annotations are present in the manifest.

    Returns a flat list of dicts, each with:
      - annotation_id    : the annotation's own ID
      - canvas_id        : the canvas the annotation lives on
      - canvas_label     : human-readable label for the canvas
      - canvas_width     : pixel width of the canvas (from canvas object)
      - canvas_height    : pixel height of the canvas (from canvas object)
      - comment_value    : raw HTML/text value of the comment
      - comment_creator  : creator string (if present)
      - comment_created  : ISO timestamp (if present)
      - selector         : raw selector dict (SvgSelector or fragment string)
      - selector_type    : "svg" | "xywh" | "none"
      - svg_element      : detected SVG element name within the selector, or None
      - shape_class      : SHAPE_POLYGON | SHAPE_LINE | None (None = skip)
    """
    results = []

    for canvas in manifest.get("items", []):
        canvas_id     = canvas.get("id", "")
        canvas_label  = _first_label(canvas.get("label", {}))
        canvas_width  = canvas.get("width",  0)
        canvas_height = canvas.get("height", 0)

        for ann_page in canvas.get("annotations", []):
            for ann in ann_page.get("items", []):
                if ann.get("motivation") != "commenting":
                    continue

                body_list = ann.get("body", [])
                if isinstance(body_list, dict):
                    body_list = [body_list]

                comment_value   = ""
                comment_creator = ""
                comment_created = ""
                for body in body_list:
                    comment_value   = _strip_html(body.get("value",   comment_value))
                    comment_creator = body.get("creator", comment_creator)
                    comment_created = body.get("created", comment_created)

                target             = ann.get("target", "")
                selector, sel_type = _parse_target_selector(target)
                svg_element        = _detect_svg_element(selector, sel_type)
                shape_class        = _classify_shape(sel_type, svg_element)

                results.append({
                    "annotation_id":   ann.get("id", ""),
                    "canvas_id":       canvas_id,
                    "canvas_label":    canvas_label,
                    "canvas_width":    canvas_width,
                    "canvas_height":   canvas_height,
                    "comment_value":   comment_value,
                    "comment_creator": comment_creator,
                    "comment_created": comment_created,
                    "selector":        selector,
                    "selector_type":   sel_type,
                    "svg_element":     svg_element,
                    "shape_class":     shape_class,
                })

    return results


def _first_label(label_obj: dict) -> str:
    for values in label_obj.values():
        if values:
            # Return the first non-empty string found
            for v in values:
                if v and v.strip():
                    return v.strip()
    return ""


def _parse_target_selector(target) -> tuple:
    """
    Parse a IIIF annotation target into (selector_dict, selector_type).

    Handles:
      - Plain fragment URI:  "...canvas/id#xywh=x,y,w,h"
      - SpecificResource with SvgSelector
      - SpecificResource with FragmentSelector (xywh)
      - Missing / empty target → ({}, "none")
    """
    if not target:
        return {}, "none"

    if isinstance(target, str):
        if "#xywh=" in target:
            xywh_str = target.split("#xywh=")[1]
            return {"type": "xywh", "value": xywh_str}, "xywh"
        return {}, "none"

    selector = target.get("selector", {})
    if not selector:
        return {}, "none"

    sel_type = selector.get("type", "")
    if sel_type == "SvgSelector":
        return selector, "svg"
    if sel_type == "FragmentSelector":
        value = selector.get("value", "")
        if value.startswith("xywh="):
            return {"type": "xywh", "value": value[5:]}, "xywh"

    return selector, "unknown"


# ---------------------------------------------------------------------------
# 3. Shape classification
# ---------------------------------------------------------------------------

# SVG element names → POLYGON output (closed / filled shapes)
_POLYGON_ELEMENTS = {"polygon", "ellipse", "rect", "circle"}
# SVG element names → LINE output (open paths)
_LINE_ELEMENTS    = {"polyline", "path"}


def _detect_svg_element(selector: dict, selector_type: str) -> Optional[str]:
    """
    Inspect the SvgSelector value and return the first non-<svg> element tag
    name found (lowercase), e.g. "polygon", "ellipse", "polyline", "path".
    Returns None for xywh selectors or missing/empty SVG values.
    """
    if selector_type != "svg":
        return None
    svg_value = selector.get("value", "")
    for m in re.finditer(r"<(\w+)", svg_value):
        tag = m.group(1).lower()
        if tag != "svg":
            return tag
    return None


def _classify_shape(selector_type: str, svg_element: Optional[str]) -> Optional[str]:
    """
    Return SHAPE_POLYGON, SHAPE_LINE, or None (= skip).

    Rules:
      - xywh fragment  → POLYGON  (always a rectangle)
      - svg selector   → depends on the element tag
      - none / unknown → None (skip)
    """
    if selector_type == "xywh":
        return SHAPE_POLYGON
    if selector_type == "svg" and svg_element:
        if svg_element in _POLYGON_ELEMENTS:
            return SHAPE_POLYGON
        if svg_element in _LINE_ELEMENTS:
            return SHAPE_LINE
    return None


# ---------------------------------------------------------------------------
# 4. Georef index and canvas→image matching
# ---------------------------------------------------------------------------

def index_georef(georef: dict) -> tuple[dict, list]:
    """
    Build two structures from the georef AnnotationPage:

      image_index : { image_service_url -> georef_item }
        Keyed by the IIIF image service URL from target.source.id.

      base_urls : [ distinct image-service base URLs ]
        E.g. ["https://iiif.digitalcommonwealth.org/iiif/2"] — used to
        reconstruct image IDs from bare canvas ID suffixes when the manifest
        contains no painting annotations.
    """
    image_index = {}
    base_url_set: set[str] = set()

    for item in georef.get("items", []):
        source_id = item.get("target", {}).get("source", {}).get("id", "")
        if not source_id:
            continue
        image_index[source_id] = item
        # The base URL is everything up to (but not including) the last path segment
        # e.g. "https://iiif.digitalcommonwealth.org/iiif/2/commonwealth:63960f677"
        #   → "https://iiif.digitalcommonwealth.org/iiif/2"
        base_url_set.add(source_id.rsplit("/", 1)[0])

    return image_index, list(base_url_set)


def match_canvas_to_georef(canvas_id: str, image_index: dict, base_urls: list) -> Optional[dict]:
    """
    Find the georef entry for a given canvas ID.

    Strategy 1 — direct lookup:
      The image_index may already be keyed by a URL that contains the same
      identifier segment as the canvas ID.  Try the canvas ID itself first
      (unlikely but harmless).

    Strategy 2 — suffix reconstruction:
      Extract the final path segment of the canvas ID (e.g. "63960f677") and
      combine it with each known image-service base URL to form a candidate
      image service URL, then look that up in the index.

      For digitalcommonwealth.org manifests the image ID takes the form
      "commonwealth:<suffix>", so we try both bare and prefixed variants.
    """
    # Strategy 1: direct hit (e.g. if canvas_id itself appears as a source id)
    if canvas_id in image_index:
        return image_index[canvas_id]

    # Strategy 2: reconstruct from the canvas ID's final path segment
    suffix = canvas_id.rstrip("/").rsplit("/", 1)[-1]

    for base in base_urls:
        # Try "commonwealth:<suffix>" (Digital Commonwealth convention)
        for candidate_id in [
            f"{base}/commonwealth:{suffix}",
            f"{base}/{suffix}",
        ]:
            if candidate_id in image_index:
                return image_index[candidate_id]

    return None


# ---------------------------------------------------------------------------
# 5. Convert selectors to SVG strings
# ---------------------------------------------------------------------------

def selector_to_svg_string(
    selector: dict,
    selector_type: str,
    img_width: int,
    img_height: int,
) -> Optional[str]:
    """
    Convert a liiive selector to an SVG string for `allmaps transform svg`.
    """
    if selector_type == "svg":
        raw_svg = selector.get("value", "")
        return _normalise_svg(raw_svg, img_width, img_height)

    if selector_type == "xywh":
        raw = selector.get("value", "")
        try:
            x, y, w, h = [int(v) for v in raw.split(",")]
        except ValueError:
            print(f"    WARNING: could not parse xywh '{raw}'", file=sys.stderr)
            return None
        pts = f"{x},{y} {x+w},{y} {x+w},{y+h} {x},{y+h}"
        return (
            f'<svg width="{img_width}" height="{img_height}">'
            f'<polygon points="{pts}" /></svg>'
        )

    return None


def _normalise_svg(svg_string: str, img_width: int, img_height: int) -> str:
    """
    Normalise an SVG string for the Allmaps CLI:
      - Convert <ellipse> → <polygon> (64-point sampled approximation)
      - Convert <rect>    → <polygon>
      - <polyline> and <path> are passed through unchanged
      - Ensure the <svg> root has width/height attributes
    """
    def ellipse_to_polygon(m):
        attrs = m.group(1)
        cx = float(_attr(attrs, "cx", "0"))
        cy = float(_attr(attrs, "cy", "0"))
        rx = float(_attr(attrs, "rx", "1"))
        ry = float(_attr(attrs, "ry", "1"))
        n  = 64
        pts = " ".join(
            f"{cx + rx * math.cos(2 * math.pi * i / n):.2f},"
            f"{cy + ry * math.sin(2 * math.pi * i / n):.2f}"
            for i in range(n)
        )
        return f'<polygon points="{pts}" />'

    svg_string = re.sub(r"<ellipse([^/]*/?)>",  ellipse_to_polygon, svg_string, flags=re.IGNORECASE)
    svg_string = re.sub(r"<ellipse([^>]+)/>",   ellipse_to_polygon, svg_string, flags=re.IGNORECASE)

    def rect_to_polygon(m):
        attrs = m.group(1)
        x = float(_attr(attrs, "x", "0"))
        y = float(_attr(attrs, "y", "0"))
        w = float(_attr(attrs, "width",  "0"))
        h = float(_attr(attrs, "height", "0"))
        pts = f"{x},{y} {x+w},{y} {x+w},{y+h} {x},{y+h}"
        return f'<polygon points="{pts}" />'

    svg_string = re.sub(r"<rect([^>]+)/>", rect_to_polygon, svg_string, flags=re.IGNORECASE)

    if img_width and img_height:
        svg_string = re.sub(
            r"<svg(?![^>]*\bwidth\b)",
            f'<svg width="{img_width}" height="{img_height}"',
            svg_string,
        )

    return svg_string


def _attr(attrs_str: str, name: str, default: str = "0") -> str:
    m = re.search(rf'\b{name}="([^"]+)"', attrs_str)
    return m.group(1) if m else default


# ---------------------------------------------------------------------------
# 6. Call `allmaps transform svg` via subprocess
# ---------------------------------------------------------------------------

def transform_svg_to_geojson(svg_string: str, georef_item: dict) -> Optional[dict]:
    """
    Pipe an SVG string through `allmaps transform svg --annotation <tmp>`.
    Returns a GeoJSON geometry dict, or None on failure.
    """
    annotation_page = {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "id": georef_item.get("id", ""),
        "type": "AnnotationPage",
        "items": [georef_item],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(annotation_page, tmp, ensure_ascii=False)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["allmaps", "transform", "svg", "--annotation", tmp_path],
            input=svg_string,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print(
            "\nERROR: `allmaps` command not found.\n"
            "Install it with:  npm install -g @allmaps/cli\n",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("    WARNING: allmaps transform timed out.", file=sys.stderr)
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        print(
            f"    WARNING: allmaps transform failed:\n    {result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    stdout = result.stdout.strip()
    if not stdout:
        print("    WARNING: allmaps transform returned empty output.", file=sys.stderr)
        return None

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(
            f"    WARNING: could not parse allmaps output as JSON: {exc}\n"
            f"    Raw output: {stdout[:200]}",
            file=sys.stderr,
        )
        return None

    if parsed.get("type") == "FeatureCollection":
        inner_features = parsed.get("features", [])
        if not inner_features:
            print("    WARNING: allmaps returned an empty FeatureCollection.", file=sys.stderr)
            return None
        if len(inner_features) > 1:
            geometries = [f["geometry"] for f in inner_features if f.get("geometry")]
            return {"type": "GeometryCollection", "geometries": geometries}
        return inner_features[0].get("geometry")

    return parsed


# ---------------------------------------------------------------------------
# 7. Build GeoJSON features and FeatureCollections
# ---------------------------------------------------------------------------

def build_geojson_feature(liiive_ann: dict, geojson_geometry: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": geojson_geometry,
        "properties": {
            "annotation_id":   liiive_ann["annotation_id"],
            "canvas_id":       liiive_ann["canvas_id"],
            "canvas_label":    liiive_ann["canvas_label"],
            "comment_value":   liiive_ann["comment_value"],
            "comment_creator": liiive_ann["comment_creator"],
            "comment_created": liiive_ann["comment_created"],
            "selector_type":   liiive_ann["selector_type"],
            "svg_element":     liiive_ann["svg_element"],
        },
    }


def build_feature_collection(features: list) -> dict:
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# 8. Main orchestration
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Warp liiive/IIIF commenting annotations to GeoJSON.\n\n"
            "Outputs two files in --output directory:\n"
            "  polygon.geojson  — closed shapes (polygon, ellipse, rect, xywh)\n"
            "  line.geojson     — open paths (polyline, path)\n\n"
            "If --georef is omitted the script fetches the Georeference Annotation\n"
            "automatically via https://annotations.allmaps.org/?url=<manifest_id>."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--liiive", required=True,
        help="Path or URL to the liiive manifest JSON.",
    )
    parser.add_argument(
        "--georef", default=None,
        help=(
            "Path or URL to the Allmaps Georeference AnnotationPage JSON. "
            "Omit to auto-fetch via the Allmaps API."
        ),
    )
    parser.add_argument(
        "--output", default=".",
        help=(
            "Directory to write polygon.geojson and line.geojson into. "
            "Defaults to the current directory."
        ),
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    polygon_path = output_dir / "polygon.geojson"
    line_path    = output_dir / "line.geojson"

    # -- Step 1: Load liiive manifest ----------------------------------------
    print("\n[1/5] Loading liiive manifest ...")
    liiive_manifest = load_json(args.liiive)

    # -- Step 2: Load or derive georef annotation ----------------------------
    print("[2/5] Loading Georeference Annotation ...")
    if args.georef:
        georef = load_json(args.georef)
    else:
        try:
            georef = fetch_georef_for_manifest(liiive_manifest)
        except ValueError as exc:
            print(f"\nERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    # -- Step 3: Extract and classify liiive annotations ---------------------
    print("[3/5] Extracting commenting annotations from liiive manifest ...")
    liiive_annotations = extract_liiive_annotations(liiive_manifest)

    n_polygon = sum(1 for a in liiive_annotations if a["shape_class"] == SHAPE_POLYGON)
    n_line    = sum(1 for a in liiive_annotations if a["shape_class"] == SHAPE_LINE)
    n_skip    = sum(1 for a in liiive_annotations if a["shape_class"] is None)
    print(
        f"      Found {len(liiive_annotations)} commenting annotation(s): "
        f"{n_polygon} polygon, {n_line} line, {n_skip} to skip."
    )

    # -- Step 4: Index georef -------------------------------------------------
    image_index, base_urls = index_georef(georef)
    print(f"      Georef covers {len(image_index)} image(s) across {len(base_urls)} base URL(s).")

    # -- Step 5: Warp each annotation ----------------------------------------
    print("[4/5] Warping annotations via `allmaps transform svg` ...")
    polygon_features = []
    line_features    = []
    skipped          = 0

    for ann in liiive_annotations:
        ann_id_short = ann["annotation_id"].split("/")[-1]
        canvas_id    = ann["canvas_id"]
        label        = ann["canvas_label"] or canvas_id.rsplit("/", 1)[-1]
        comment      = _strip_html(ann["comment_value"])
        shape_class  = ann["shape_class"]
        shape_hint   = ann["svg_element"] or ann["selector_type"] or "no selector"

        print(f"  -> {ann_id_short}  [{label}]  \"{comment}\"  ({shape_hint})")

        if shape_class is None:
            print("     SKIP: no selector or unrecognised SVG element.")
            skipped += 1
            continue

        georef_item = match_canvas_to_georef(canvas_id, image_index, base_urls)
        if georef_item is None:
            print(f"     SKIP: no georef entry found for canvas {canvas_id.rsplit('/', 1)[-1]}.")
            skipped += 1
            continue

        img_w = ann["canvas_width"]
        img_h = ann["canvas_height"]

        svg_string = selector_to_svg_string(
            ann["selector"], ann["selector_type"], img_w, img_h
        )
        if not svg_string:
            print("     SKIP: could not build SVG string from selector.")
            skipped += 1
            continue

        geojson_geom = transform_svg_to_geojson(svg_string, georef_item)
        if geojson_geom is None:
            skipped += 1
            continue

        feature = build_geojson_feature(ann, geojson_geom)
        if shape_class == SHAPE_POLYGON:
            polygon_features.append(feature)
        else:
            line_features.append(feature)

        print(f"     OK  → {shape_class}.geojson  (geometry: {geojson_geom.get('type')})")

    # -- Step 6: Write output ------------------------------------------------
    print(f"\n[5/5] Writing output to {output_dir} ...")
    if skipped:
        print(f"      ({skipped} annotation(s) skipped — see warnings above)")

    for path, features, label in [
        (polygon_path, polygon_features, "polygon"),
        (line_path,    line_features,    "line"),
    ]:
        fc = build_feature_collection(features)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(fc, fh, indent=2, ensure_ascii=False)
        print(f"      {label}.geojson — {len(features)} feature(s)  →  {path}")

    print("\nDone!\n")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


if __name__ == "__main__":
    main()