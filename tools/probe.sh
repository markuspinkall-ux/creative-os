#!/bin/bash
set +e
dnf install -y -q fedora-logos >/dev/null 2>&1
ls -la /usr/share/anaconda/pixmaps/rnotes/ /usr/share/anaconda/pixmaps/rnotes/en/
head -c 600 /usr/share/anaconda/pixmaps/rnotes/en/$(ls /usr/share/anaconda/pixmaps/rnotes/en/ | head -1); echo
rpm -ql fedora-logos | grep -v "/doc/\|licenses" | head -80
exit 0
