#!/usr/bin/env python

import pandas as pd
import os

# Run this script from inside a directory that also contains the file `barcode-ark-crosswalk.csv`

path = os.getcwd()
msg = "directory already exists"

if not os.path.exists(path+"/ark"):
    os.mkdir(msg)
else:
    print("directory already exists")

if not os.path.exists(path+"/barcode"):
    os.mkdir("barcode")
else:
    print(msg)

df = pd.read_csv(path+"/barcode-ark-crosswalk.csv")

for i in df["ark"].astype(str):
    if not os.path.exists(path+"/ark"+i):
        os.mkdir(os.path.join(path+"/ark", i))
    else:
        print(msg)

for i in df["barcode"].astype(str):
    if not os.path.exists(path+"/barcode"+i):
        os.mkdir(os.path.join(path+"/barcode", i))
    else:
        print(msg)