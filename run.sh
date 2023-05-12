#!/bin/bash -e

# This script is used to run the application
envsubst < config.yaml | poetry run shot-scraper multi -