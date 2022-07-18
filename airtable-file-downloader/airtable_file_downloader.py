#!/usr/bin/env python3

import re
from sys import stdin
import requests

inFile = stdin.read()
searchString = r"\((https://dl.airtable.com.*?)\)"

matcher = re.compile(searchString)
results = re.finditer(matcher, inFile)

def download_file(url):
    local_filename = url.split('/')[-1]
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                #if chunk: 
                f.write(chunk)
    return local_filename


for r in results:
    urlString = r.group(1)
    download_file(urlString)



