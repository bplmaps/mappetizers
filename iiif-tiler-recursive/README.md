# iiif-tiler-recursive

Recursively tile high-resolution images with this bash script. IIIF tiler script from [Glen Robson](https://github.com/glenrobson/iiif-tiler).

## Behavior

This script's behavior is to:
1. `cd` into every directory at the current level
2. for each file (image) in that directory:
    1. make a new subdirectory named for this file, to a user-defined character limit
    2. `cd` into that new subdirectory
    3. run `iiif-tiler.jar` on this file
    4. once the image is tiled, `cd ..` into parent directory

It's completely dependent on a good directory structure and machine-sortable, metadata-driven file names. You might need to test it a few times to make sure the output tile pyramids are landing in a suitable order.

## Use

Prepare a directory structure for the script resembling:
1. Download `recursiveTiler.jar`
2. Download the latest release of [Glen Robson's IIIF tiler](https://github.com/glenrobson/iiif-tiler/releases)
3. Move both of them into the same directory
4. Move the images that you need to IIIF-ify into the same directory

To run the script simply `cd` into that directory and:

    bash recursiveTiler.sh

**Before running the script, ensure that your file nomenclature makes sense, and that lines 12-13 of the bash are parsing the file names to your desired length.**

## Sample directory structure

Let's say you are tiling a bunch of images for an LMEC digital exhibition. You might use the following directory structure:

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
