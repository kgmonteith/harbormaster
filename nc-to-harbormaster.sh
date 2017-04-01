#!/usr/bin/env bash

rtl-ais/rtl_ais -n &
nc -lku 10110 | xargs -n 1 -I '{}' curl -X POST --data-binary '{}' http://jefita.com:8000/input/Rooftop
