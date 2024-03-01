#!/bin/bash

# Ensure your directory structure resembles:
#
# - iiif-tiler.jar
# - recursiveTiler.sh
# - img-folder1
#   -- img1
#   -- img2
# - img-folder2
#   -- img3
#   -- img4


jarpath='path/to/iiif-tiler.jar' # change this to match your path

for d in */ ; do
    cd "$d"
    for f in * ; do
        mv "$f" "${f// /_}"
        if [ -f "$f" ]; then
            mkdir ${f:0:6}
            cd ${f:0:6}
            java -jar $jarpath ../$f # customize this line to specify version 2 or version 3
            cd ..
        fi
    done
    cd ..
done