#!/bin/bash
# kernel-devel passend zum Kernel des Abbilds installieren. Ist die Version aus den
# Paketquellen schon verschwunden (Fedora hat einen neueren Kernel), direkt vom
# Fedora-Bausystem (Koji) laden.
set -u
KVER="$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-core | tail -n1)"
V="$(rpm -q --qf '%{VERSION}\n' kernel-core | tail -n1)"
R="$(rpm -q --qf '%{RELEASE}\n' kernel-core | tail -n1)"
dnf install -y akmods >/dev/null || exit 1
if rpm -q "kernel-devel-${KVER}" >/dev/null 2>&1; then echo "kernel-devel ${KVER} vorhanden"; exit 0; fi
if dnf install -y "kernel-devel-${KVER}"; then exit 0; fi
echo "kernel-devel ${KVER} nicht mehr in den Paketquellen – lade aus Koji"
base="https://kojipkgs.fedoraproject.org/packages/kernel/${V}/${R}/x86_64"
dnf install -y "${base}/kernel-devel-${KVER}.rpm" || dnf install -y "${base}/kernel-devel-${KVER}.rpm" "${base}/kernel-devel-matched-${KVER}.rpm"
