"""Startpunkt: `creative-assistant` (Hintergrund-Dienst)."""

import signal
import sys

from .core import Assistant


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        Assistant().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
