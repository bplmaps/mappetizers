import requests
import datetime
import csv
import json

searchString = "https://collections.leventhalmap.org/search?"
scrapeRawJson = False
fields = ["id","extent_tsi"] # if scrapeRawJson is True, this is ignored

complete = False
page = 1


if scrapeRawJson:
    suffix = "json"
    collector = []
else:
    suffix = "tsv"

with open("./scrape_results_{}.{}".format(datetime.datetime.now(), suffix), 'w+') as outFile:

    if not scrapeRawJson:
        outFile.write("id\t{}\n".format("\t".join(fields)))

    while not complete:

        r = requests.get("{}&format=json&per_page=100&page={}".format(searchString, page))

        thisPageResult = r.json()

        for record in thisPageResult['data']:
            doc = record['attributes']

            if scrapeRawJson:
                collector.append(doc)

            else:
                outFile.write(doc["id"])
                for f in fields:
                    if f not in doc:
                        p = ""
                    else:
                        if isinstance(doc[f], list):
                            p = " || ".join(doc[f])
                        else:
                            p = doc[f]
                    outFile.write("\t{}".format(p))
                outFile.write("\n")

        complete = True if thisPageResult['meta']['pages']['last_page?'] else False
        page = thisPageResult['meta']['pages']['next_page']

    if scrapeRawJson:
        json.dump(collector, outFile)
