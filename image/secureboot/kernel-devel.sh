#!/bin/bash
# kernel-devel passend zum Kernel des Abbilds installieren (vor akmods, damit dnf
# nicht den neuesten Kernel-Entwicklungsstand nachzieht). Ist die Version aus den
# Paketquellen schon verschwunden, direkt vom Fedora-Bausystem (Koji) laden.
set -u
KVER="$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core | tail -n1)"
V="$(rpm -q --qf '%{VERSION}\n' kernel-core | tail -n1)"
R="$(rpm -q --qf '%{RELEASE}\n' kernel-core | tail -n1)"
if ! rpm -q "kernel-devel-${KVER}" >/dev/null 2>&1; then
    if ! dnf install -y "kernel-devel-${KVER}" "kernel-devel-matched-${KVER}"; then
        echo "kernel-devel ${KVER} nicht mehr in den Paketquellen – lade aus Koji"
        base="https://kojipkgs.fedoraproject.org/packages/kernel/${V}/${R}/x86_64"
        dnf install -y "${base}/kernel-devel-${KVER}.rpm" "${base}/kernel-devel-matched-${KVER}.rpm" || exit 1
    fi
fi
dnf install -y akmods || exit 1
rpm -q "kernel-devel-${KVER}"
