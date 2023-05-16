#!/usr/bin/env python

import os
import json
import pandas as pd
import geopandas as gpd
import subprocess

# This script:
    # 1. scans through all subdirectories inside a directory named `barcode`
    # 2. reformats files named `Boundary.geojson` to conform with Atlascope v2 metadata schema
    # 3. saves the reformatted files as `plates.geojson` in the appropriate subdirectory inside a directory named `ark`

# Before running this script, you must run `createDirStructure.py` from
# within a folder that also contains the file `barcode-ark-crosswalk.csv`

# You must also have downloaded the requisite `Boundary.geojson` files

path = os.getcwd()
indir = path+'/barcode'
outdir = path+'/ark'
map = path+"/barcode-ark-crosswalk.json"

# loop through all of the named barcode folders inside `barcode`

for bar in os.scandir(indir):

    # skip files

    isFile = os.path.isfile(bar)
    if isFile == False:

        # in each barcode folder,
        # capture the folder name as a string
        # so we can map it to its companion file later

        for f in os.scandir(bar):

            # capture barcode as string variable

            code = os.path.dirname(f)
            bc = os.path.basename(code)

            # load barcode-ark-crosswalk file as json

            with open(map, 'r') as m:
                m = json.load(m)
                
            # loop through it until
            # the barcode variable finds a match.
            # when it does, capture its value as a string variable

            for n in m:
                if bc == str(n['barcode']):
                    ark = n['ark']
                    
                    # inside the barcode folder,
                    # open `Boundary.geojson` as json

                    infile = indir+"/"+bc+"/Boundary.geojson"
                    with open(infile, 'r') as f:
                        d=json.load(f)

                    # loop through its features and
                    # re-map keys/values to Atlascope v2 schema
                    # plus error handling for problematic `Boundary` fields
                        
                    for feat in d['features']:

                        try:
                            feat['properties']['digitalCollectionsPermalinkPlate'] = 'https://digitalcommonwealth.org/search/'+feat['properties']['commonweal']+'/manifest'
                        except:
                            print(f"The commonweal field on ARK ID {ark} / Barcode {bc} is screwed up. investigate")
                            feat['properties']['digitalCollectionsPermalinkPlate'] = 'https://digitalcommonwealth.org/search/...'
                        feat['properties']['name'] = feat['properties']['plate']
                        feat['properties']['allmapsMapID'] = ''
                        feat['properties']['imageUri'] = ''
                        try:
                            p = feat['properties']['plate'].strip('plate ')
                            feat['properties']['identifier'] = 'ark:/50959/'+ark+'/'+p
                        except:
                            print(f"The plate field on ARK ID {ark} / Barcode {bc} is screwed up. investigate")
                            feat['properties']['identifier'] = 'ark:/50959/'
                        del feat['properties']['commonweal']
                        del feat['properties']['plate']
                        del feat['properties']['title']
                        del feat['properties']['publisher']
                        del feat['properties']['year']
                    
                    # delete deprecated crs field

                    del d['crs']

                    # save re-mapped file as `plates.geojson` in outfile directory

                    outfile = outdir+"/"+ark+"/plates.geojson"
                    with open(outfile, 'w+') as f:
                        json.dump(d, f, indent=2)

                    # rewind GeoJSON to conform to right-hand rule

                    rewind = outdir+"/"+ark+"/plates-rewind.geojson"
                    with open(rewind, 'w+') as f:
                        cmd = [
                            'geojson-rewind', outfile
                        ]
                        subprocess.run(
                            cmd,
                            stdout=f
                            )
                    
                    # indent the new GeoJSON and save it as `plates.geojson`

                    with open(rewind, 'r') as f:
                        d=json.load(f)
                    with open(outfile, 'w+') as f:
                        json.dump(d, f, indent=2)

                    # delete rewind file

                    os.remove(rewind)