#!/bin/sh
# Startet die Systemsteuerung direkt aus dem Quellordner.
cd "$(dirname "$0")"
exec python3 -m creative_settings "$@"
