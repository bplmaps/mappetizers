# Digital Collections Scraper

Very simple Python script to download bulk collections data from LMEC Digital Collections portal.

## Usage

1. Set `searchString` variable to the URL of a query from Digital Collections (e.g., go to Digital Collections on the web, make a search, and copy the URL of that search into `searchString`)
2. If you want raw JSON output of _everything_ returned by the search, set `scrapeRawJson` to `True`
3. If you want a TSV table of specific field names, set `scrapeRawJson` to `False` and set the `field` list to a list of field names (case sensitive) that you want to retain
4. Run `python3 ./scraper.py` and you'll get a time stamped output file to the same directory.
