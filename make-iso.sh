#!/usr/bin/env bash

cp -r /usr/share/archiso/configs/releng .
rsync -avhPc ./krapaince-profile/ ./releng/
patch ./patch/pacman.conf -i ./patch/pacman.conf.patch -o ./releng/pacman.conf
patch ./patch/profiledef.sh -i ./patch/profiledef.sh.patch -o ./releng/profiledef.sh

sudo mkarchiso -v -w ./archiso-tmp ./releng
