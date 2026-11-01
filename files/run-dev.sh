#!/bin/sh
# Startet „Dateien“ direkt aus dem Quellordner (zum Ausprobieren).
cd "$(dirname "$0")"
exec python3 -m creative_files "$@"
