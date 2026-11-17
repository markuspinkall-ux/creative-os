#!/bin/sh
# Startet den Player direkt aus diesem Ordner (zum Testen).
cd "$(dirname "$0")" || exit 1
exec python3 -m creative_media "$@"
