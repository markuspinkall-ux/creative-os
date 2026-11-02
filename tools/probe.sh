#!/bin/bash
# Schnelle Prüfungen in einem frischen Fedora (Werkzeug für die Entwicklung)
set +e
dnf install -y -q anaconda-gui greenboot greenboot-default-health-checks >/dev/null 2>&1
rpm -q anaconda-gui greenboot greenboot-default-health-checks
echo "=== greenboot Dateien"; rpm -ql greenboot greenboot-default-health-checks 2>/dev/null | grep -v "/doc/\|man" | head -60
echo "=== anaconda pixmaps"; ls -la /usr/share/anaconda/pixmaps/ 2>/dev/null
echo "=== anaconda css"; cat /usr/share/anaconda/anaconda-gtk.css
echo "=== product css im Code"; grep -rn "anaconda-gtk.css\|product.*\.css\|CssProvider" /usr/lib64/python3*/site-packages/pyanaconda/ui/gui/__init__.py | head
grep -n "css\|PRODUCT" -i /usr/lib64/python3*/site-packages/pyanaconda/ui/gui/__init__.py | head -40
echo "=== Pixmap-Pakete"; rpm -qf /usr/share/anaconda/pixmaps/* 2>/dev/null | sort -u
