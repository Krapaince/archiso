#!/usr/bin/env bash

ISO_DIR="out"
DISK=./archlinux-disk-a.img
ISO=$(/usr/bin/ls -1 -t $ISO_DIR | head -n 1)

[ ! -f ./$DISK ] && qemu-img create -f qcow2 $DISK 32G

qemu-system-x86_64 \
  -cpu host -m 4096 \
  -hda $DISK \
  -k en-us \
  -bios /usr/share/edk2-ovmf/x64/OVMF.fd \
  -cdrom "./$ISO_DIR/$ISO" \
  -vga virtio \
  -enable-kvm \
  -vga none -device qxl-vga,vgamem_mb=512 \
  -monitor stdio # Enable console mod

