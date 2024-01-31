#!/bin/bash -e
: ${TARGET_DIR:="screenshots"}
# This script is used to run the application
envsubst < config.yaml | poetry run shot-scraper multi -