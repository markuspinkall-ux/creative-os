#!/bin/bash
set +e
dnf install -y -q rsync python3 >/dev/null 2>&1
S=/tmp/bk; mkdir -p $S/home/Dokumente $S/home/.cache $S/home/.local/share/Steam $S/drive
echo hi > $S/home/Dokumente/a.txt; echo c > $S/home/.cache/x; echo g > $S/home/.local/share/Steam/game
run() { HOME=$S/home USER=test python3 - <<PY
import sys; sys.path.insert(0,'settings')
from creative_settings import backup as b
b.find_target=lambda cfg: "$S/drive"; b._is_fat=lambda m: False
print(b.run(lambda p,t: print("Fortschritt", p, t)))
PY
}
run; echo bye > $S/home/Dokumente/a.txt; rm -f $S/home/Dokumente/gone.txt; run
find $S/drive -type f | sort; cat "$S/drive/Creative-OS-Sicherung/"*/Dokumente/a.txt
find "$S/drive/Creative-OS-Sicherung/Ältere Versionen" -type f
exit 0
