# iiif-tiler-recursive

Recursively tile high-resolution images with this bash script. IIIF tiler script from [Glen Robson](https://github.com/glenrobson/iiif-tiler).

## Behavior

This script's behavior is to:
1. `cd` into each directory
2. for each file (image) in that directory:
    1. make a new subdirectory named for this file, to a user-defined character limit
    2. `cd` into that new subdirectory
    3. run `iiif-tiler.jar` on this file
    4. once the image is tiled, `cd ..` into parent directory

This

## Use

To use the script, download this repo as a `.zip` file.

Figure out how you want the IIIF pyramids to be sorted and organized.

For example, let's say you are tiling a bunch of images for an LMEC digital exhibition. You might use the following directory structure:

    tileImagesForExhibition/
    ├─ recursiveTiler.sh
    ├─ exhibitionTheme1/
    │  ├─ theme1_img1.1.tiff
    │  ├─ theme1_img1.2.tiff
    ├─ exhibitionTheme2/
    │  ├─ theme2_img2.1.tiff
    │  ├─ theme2_img2.2.tiff

The output of the script would resemble:

    tileImagesForExhibition/
    ├─ recursiveTiler.sh
    ├─ exhibitionTheme1/
    │  ├─ theme1_img1.1/
    │  │  ├─ iiif/...
    │  ├─ theme1_img1.2/
    │  │  ├─ iiif/...
    │  ├─ src/
    │  │  ├─ theme1_img1.1.tiff
    │  |  ├─ theme1_img1.2.tiff
    ├─ exhibitionTheme2/
    │  ├─ theme1_img2.1/
    │  │  ├─ iiif/...
    │  ├─ theme1_img2.2/
    │  │  ├─ iiif/...
    │  ├─ src/
    │  │  ├─ theme2_img2.1.tiff
    │  |  ├─ theme2_img2.2.tiff

The folders beginning with `iiif/` represent IIIF pyramids.