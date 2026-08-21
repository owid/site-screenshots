#!/bin/bash -e

# This script is used to run the application
# --fail: without it a page that returns an HTTP error is screenshotted anyway, and the
# error page gets committed as that branch's screenshot. A staging server that was down
# for a couple of minutes produced six nginx "502 Bad Gateway" images that read as a
# whole-page diff on every one of those pages; on a master run it would poison the
# reference screenshots the same way. Better to fail the step and say which URL did it.
envsubst < config.yaml | poetry run shot-scraper multi - --fail