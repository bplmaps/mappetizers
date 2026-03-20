# warp_liiive_annotations.py

> this code was written more or less with Claude in March 2026

Warps commenting annotations from a liiive/IIIF manifest into geographic GeoJSON by:

  1. Parsing the liiive manifest to extract per-canvas commenting annotations
  2. Fetching a Georeference Annotation, either from `--georef` (explicit) or by deriving it from the manifest's own "id" field via the Allmaps API (`https://annotations.allmaps.org/?url=<manifest_id>`)
  3. Matching each annotation's canvas to the correct georef map entry
  4. Extracting pixel-space SVG geometry and classifying it as LINE or POLYGON
  5. Piping each SVG through `allmaps transform svg` to warp to WGS84 GeoJSON
  6. Writing two output files to --output directory:

         polygon.geojson  — filled shapes (polygon, ellipse, rect, xywh)
         line.geojson     — open paths (polyline, path element)
   
   7. Annotations with no selector, or an unresolvable selector, are skipped.

## Shape classification

- POLYGON: <polygon>, <ellipse>, <rect>, <circle>, or an xywh fragment selector
- LINE: <polyline>, <path>
- No selector / unsupported element: skipped with a warning

## Image ID matching

The georef index is keyed by IIIF image service URL (e.g. https://iiif.digitalcommonwealth.org/iiif/2/commonwealth:63960f677). The liiive manifest may or may not include painting annotations with an explicit image body. When a painting body is absent (as in stripped-down liiive exports), the image service URL is reconstructed from the canvas ID: the final path segment of the canvas ID is taken as the image identifier and each known image-service base URL from the georef index is tried in turn.

## Prerequisites

```
# install
npm install -g @allmaps/cli

# verify
allmaps --version
```

## Usage

```bash
# Auto-fetch georef, write to current directory:
  python warp_liiive_annotations.py --liiive path/to/liiive-manifest.json

# Explicit georef, write to a specific directory:
  python warp_liiive_annotations.py \\
    --liiive  path/to/liiive-manifest.json \\
    --georef  https://annotations.allmaps.org/manifests/3a4dfc37b2bc9acf \\
    --output  /path/to/output/dir
```