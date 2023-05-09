This repo is for creating and storing screenshots of a selected number of OWID pages. It uses the [shot-scraper](https://shot-scraper.datasette.io/en/stable/) tool to take screenshots of the urls listed in [config.yaml](./config.yaml). Shot-scraper uses a headless browser under the hood via the python package playwright. There is a bit of javascript that has to be done for each screenshot to scroll through the page and give graphers and lazy images time to load.

To add more screenshots, edit config.yaml and add the reference screenshot against to the screenshots directory.

TODO:
- the URLs are for now absolute URLs against prod. This should be replaced with a $BASE_URL variable that can be set from CI so we can easily run this against staging servers