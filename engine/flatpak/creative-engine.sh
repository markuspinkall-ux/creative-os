#!/bin/sh
export PYTHONPATH=/app/lib/creative-engine${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m creative_engine "$@"
