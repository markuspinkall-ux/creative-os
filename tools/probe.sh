#!/bin/bash
# Gibt es QtWebEngine 6 mit H.264 (RPM Fusion „freeworld“)?
set +e
V=$(rpm -E %fedora)
dnf install -y -q "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$V.noarch.rpm" \
    "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$V.noarch.rpm" >/dev/null 2>&1
echo "== Fedora $V: Pakete mit qtwebengine =="
dnf list --available '*qtwebengine*' 2>/dev/null | grep -v debug
echo "== freeworld-Suche =="
dnf search freeworld 2>/dev/null | grep -i -E "webengine|qt6" || echo "kein qt6-webengine-freeworld"
echo "== Fedora-Paket: Codec-Hinweise =="
dnf info qt6-qtwebengine 2>/dev/null | grep -E "Version|Release|Repo"
exit 0
