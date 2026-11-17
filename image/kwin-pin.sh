#!/bin/bash
# KWin 6.8.3 stürzt beim Start/Anmelden ab, sobald die Maus bewegt wird
# (KDE-Bugs 528824, 528890: InputRedirection::syncTabletWithMouse) – schwarzer Bildschirm,
# Anmelde-Schleife. Bis Fedora eine reparierte Version liefert, nehmen wir 6.8.2.
# Andere Versionen bleiben unverändert (das Skript tut dann nichts).
set -euo pipefail
BAD="6.8.3"
GOOD="6.8.2"
ver() { rpm -q --qf '%{VERSION}' kwin-common 2>/dev/null || rpm -q --qf '%{VERSION}' kwin; }
now="$(ver)"
echo "KWin im Abbild: $now"
[ "$now" = "$BAD" ] || { echo "KWin: nichts zu tun"; exit 0; }

pkgs="$(rpm -qa --qf '%{NAME}\n' | grep -E '^kwin(-|$)' | grep -v -- '-debug' | sort -u)"
echo "KWin-Pakete: $(echo $pkgs)"

# 1) aus dem Archiv-Repo von Fedora
if dnf downgrade -y --enablerepo='updates-archive' $(for p in $pkgs; do printf '%s-%s ' "$p" "$GOOD"; done); then
    :
else
    # 2) direkt vom Fedora-Buildsystem (Koji)
    fc="fc$(rpm -E %fedora)"
    base="https://kojipkgs.fedoraproject.org/packages/kwin/$GOOD"
    rel="$(curl -fsSL "$base/" | grep -oE "href=\"[0-9]+\.$fc/\"" | sed 's/href="//; s/\/"//' | sort -V | tail -n1)"
    [ -n "$rel" ] || { echo "KWin $GOOD für $fc nicht gefunden" >&2; exit 1; }
    echo "KWin $GOOD-$rel von Koji"
    tmp="$(mktemp -d)"
    for p in $pkgs; do
        for arch in x86_64 noarch; do
            curl -fsSL -o "$tmp/$p.rpm" "$base/$rel/$arch/$p-$GOOD-$rel.$arch.rpm" && break || rm -f "$tmp/$p.rpm"
        done
        [ -f "$tmp/$p.rpm" ] || { echo "Paket fehlt bei Koji: $p" >&2; exit 1; }
    done
    dnf downgrade -y "$tmp"/*.rpm
    rm -rf "$tmp"
fi
dnf clean all
after="$(ver)"
echo "KWin jetzt: $after"
[ "$after" = "$GOOD" ]
