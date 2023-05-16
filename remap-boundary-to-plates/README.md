# Remapping `Boundary.geojson` to `plates.geojson` files for Atlascope v2 metadata schema

This repo contains two scripts used to re-map the Atlascope v1 metadata schema to the Atlascope v2 metadata schema. `plates.geojson` files were generated with the following workflow:

1. `createDirStructure.py`: creates a workspace with two top-level directories---`ark` and `barcode`---each of which contain 101 folders named, respectively, with an Atlascope layer's ARK ID (Atlascope v2 identifier) and its Barcode (Atlascope v1 identifier)
    - This script requires `barcode-ark-crosswalk.csv` in order to create the directory structure
2. Manually download all `Boundary.geojson` files from Wasabi and place them in their corresponding directory
3. `boundariesToPlates.py`: loops through each `Boundary.geojson` file, remaps its fields to conform to Atlascope v2 metadata schema, and saves the output as `plates.geojson` in the corresponding ARK ID folder
    - This script requires `barcode-ark-crosswalk.json` in order to connect a Barcode key with its companion ARK ID value (necessary for saving `plates.geojson` files to the right place)
