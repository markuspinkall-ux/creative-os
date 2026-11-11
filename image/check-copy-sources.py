#!/usr/bin/python3
"""Prüft vor dem langen Build, ob jede COPY-Quelle im Containerfile existiert.

  python3 image/check-copy-sources.py [image/Containerfile …]
"""

import glob
import sys


def missing_sources(path):
    text = open(path, encoding="utf-8").read().replace("\\\n", " ")
    missing = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line.upper().startswith(("COPY ", "ADD ")) or "--from" in line:
            continue
        parts = [p for p in line.split()[1:] if not p.startswith("--")]
        for source in parts[:-1]:
            if "://" not in source and not glob.glob(source):
                missing.append(source)
    return missing


def main(paths):
    bad = 0
    for path in paths or ["image/Containerfile"]:
        for source in missing_sources(path):
            print(f"::error file={path}::COPY-Quelle fehlt: {source}")
            bad += 1
    if not bad:
        print("Alle COPY-Quellen vorhanden.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
