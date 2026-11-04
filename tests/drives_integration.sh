#!/bin/bash
# Only a newly allocated loop image is passed to the destructive helper.
set -euo pipefail
work=$(mktemp -d)
dev=''
cleanup() {
    if [ -n "$dev" ]; then
        while read -r target; do [ -z "$target" ] || sudo umount -- "$target" || true; done < <(findmnt -rn -S "${dev}p1" -o TARGET || true)
        sudo umount "$work/old" 2>/dev/null || true
        sudo losetup -d "$dev" || true
    fi
    sudo rm -rf "$work"
}
trap cleanup EXIT
truncate -s 2G "$work/disk.img"
dev=$(sudo losetup -fP --show "$work/disk.img")
[[ "$dev" == /dev/loop* ]]
[ "$(sudo losetup -n -O BACK-FILE "$dev" | xargs)" = "$work/disk.img" ]
printf 'label: gpt\n,500M,L\n,,L\n' | sudo sfdisk -q "$dev"
sudo udevadm settle
sudo mkfs.ext4 -q "${dev}p1"
sudo mkfs.ext4 -q "${dev}p2"
mkdir "$work/old"
sudo mount "${dev}p1" "$work/old"
for fs in ext4 exfat ntfs; do
    echo "Testing actual setup and rename: $fs"
    sudo env CREATIVE_DRIVES_TEST=1 PKEXEC_UID="$(id -u)" python3 drives/creative-drives-helper setup "$dev" Testplatte "$fs"
    part="${dev}p1"
    [ "$(sudo blkid -s TYPE -o value "$part")" = "$fs" ]
    [ "$(sudo blkid -s LABEL -o value "$part")" = Testplatte ]
    target=$(findmnt -rn -S "$part" -o TARGET | head -1)
    [ -n "$target" ]
    sudo sh -c 'printf retained > "$1/rename-sentinel"' sh "$target"
    sudo env CREATIVE_DRIVES_TEST=1 python3 drives/creative-drives-helper rename "$part" NeuerName
    [ "$(sudo blkid -s LABEL -o value "$part")" = NeuerName ]
    target=$(findmnt -rn -S "$part" -o TARGET | head -1)
    [ -n "$target" ]
    [ "$(sudo cat "$target/rename-sentinel")" = retained ]
    sudo umount "$target"
    sudo mount "$part" "$target"
    [ "$(sudo cat "$target/rename-sentinel")" = retained ]
    echo "PASS $fs: formatted, renamed, remounted; data retained across rename"
done
