#!/usr/bin/env python3

import json
import os
from pathlib import Path
import sys
from typing import List, TypedDict

from utils import (
    CONFIG_FILEPATH,
    Colors,
    Device,
    add_partition_number,
    execute_command,
    get_cpu_manufacturer,
)


class Config(TypedDict):
    timezone: str | None
    lang: str | None
    locale_gen: List[str]
    hostname: str
    username: str


class Disk(TypedDict):
    path: str
    uuid: str


def set_timezone(config: Config):
    timezone = "Europe/Paris"

    if isinstance(config["timezone"], str):
        timezone = config["timezone"]

    os.symlink(f"/usr/share/zoneinfo/{timezone}", "/etc/localtime")
    execute_command(["hwclock", "--systohc"])


def set_locale(config: Config):
    lang = "en_US.UTF-8"
    locale_gen = ["en_US.UTF-8 UTF-8", "en_US ISO-8859-1"]

    if isinstance(config["lang"], str):
        lang = config["lang"]

    if isinstance(config["locale_gen"], List):
        locale_gen = config["locale_gen"]

    with open("/etc/locale.conf", "w+") as f:
        f.write(f"LANG={lang}")
    with open("/etc/locale.gen", "w+") as f:
        f.write("\n".join(locale_gen))


def setup_network(config: Config):
    hostname = config["hostname"]

    with open("/etc/hostname", "w+") as f:
        f.write(hostname)

    with open("/etc/hosts", "w+") as f:
        hosts_content = f"""127.0.0.1   localhost
::1     localhost
127.0.1.1   {hostname}.localdomain {hostname}"""
        f.write(hosts_content)


def set_mkinitcpio_conf():
    hooks = (
        "HOOKS=(base udev autodetect modconf block keyboard encrypt filesystems fsck)"
    )
    execute_command(
        ["sed", "-i", "-e", f"s/^HOOKS=(.*/{hooks}/", "/etc/mkinitcpio.conf"]
    )


def generate_initramfs():
    execute_command(["mkinitcpio", "-P"], capture_output=False)


def set_root_password():
    execute_command(["passwd"], capture_output=False)


def configure_boot_loader(device: Device, crypt_root_partition: bool):
    cpu_manufacturer = get_cpu_manufacturer()

    execute_command(["bootctl", "install"], capture_output=False)

    root_partition = add_partition_number(Path(device["path"]), 2).as_posix()
    options = "options "
    if crypt_root_partition:
        uuid = execute_command(
            ["blkid", "-s", "UUID", "-o", "value", root_partition]
        ).replace("\n", "")
        options = (
            options + f"cryptdevice=UUID={uuid}:cryptroot root=/dev/mapper/cryptroot rw"
        )
    else:
        partuuid = execute_command(
            ["blkid", "-s", "PARTUUID", "-o", "value", root_partition]
        ).replace("\n", "")
        options = options + f"root=PARTUUID={partuuid} rw"

    with open("/boot/loader/entries/arch.conf", "w+") as f:
        content = f"""title Arch Linux
linux   /vmlinuz-linux
initrd  /{cpu_manufacturer}-ucode.img
initrd  /initramfs-linux.img
{options}"""
        f.write(content)

    with open("/boot/loader/loader.conf", "w+") as f:
        content = f"""default arch.conf
timeout 5
console-mode max
editor no"""
        f.write(content)


def main():
    if len(sys.argv) != 3:
        print(
            f"{Colors.RED}Script takes 2 arguments (device, crypt_root).{Colors.ENDC}"
        )
    with open(CONFIG_FILEPATH, "r") as f:
        config: Config = json.load(f)
        device = json.loads(sys.argv[1])
    crypt_root_partition = sys.argv[2] == "True"

    set_timezone(config)
    set_locale(config)
    setup_network(config)
    set_mkinitcpio_conf()
    generate_initramfs()
    set_root_password()
    configure_boot_loader(device, crypt_root_partition)


if __name__ == "__main__":
    main()
