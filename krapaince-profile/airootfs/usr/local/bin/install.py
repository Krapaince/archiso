#!/usr/bin/env python3

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any, Dict, List, Tuple

from utils import (
    CONFIG_FILEPATH,
    CONFIG_PATH,
    Colors,
    Config,
    Device,
    add_partition_number,
    eprint,
    execute_command,
    get_cpu_manufacturer,
    load_config,
    select_from_dict,
)

BOOT_MOUNTPOINT = Path("/mnt/boot")
ROOT_MOUNTPOINT = Path("/mnt")
HOME_MOUNTPOINT = Path("/mnt/home")

SCRIPT_PATH = Path("/usr/local/bin")
CONFIGURE_SCRIPT_NAME = "configure.py"
UTILS_SCRIPT_NAME = "utils.py"
CONFIGURE_SCRIPT_FILEPATH = SCRIPT_PATH.joinpath(CONFIGURE_SCRIPT_NAME)
UTILS_SCRIPT_FILEPATH = SCRIPT_PATH.joinpath(UTILS_SCRIPT_NAME)

CRYPT_PATH = Path("/dev/mapper")
CRYPTROOT_NAME = "cryptroot2"
CRYPTHOME_NAME = "crypthome2"
CRYPTROOT_PATH = CRYPT_PATH.joinpath(CRYPTROOT_NAME)
CRYPTHOME_PATH = CRYPT_PATH.joinpath(CRYPTHOME_NAME)


def join_absolute(p1: Path, p2: Path) -> Path:
    return Path(f"{p1.as_posix()}{p2.as_posix()}")


def checks_boot_mode():
    if not Path("/sys/firmware/efi/efivars").is_dir():
        eprint("System not booted in EFI mode.")
        exit(1)


def check_internet_connection():
    try:
        socket.create_connection(("archlinux.org", 443))
    except OSError:
        eprint("Not connected to internet.")
        exit(1)


def update_system_clock():
    execute_command(["timedatectl", "set-ntp", "true"])


def make_mountpoints_list(device: Device) -> List[str]:
    mountpoints: List[str] = []

    if "children" in device and isinstance(device["children"], List):
        for d in device["children"]:
            mountpoints.extend(make_mountpoints_list(d))

    for mountpoint in device["mountpoints"]:
        if mountpoint != None:
            mountpoints.append(mountpoint)
    return mountpoints


def umount_mountpoints(disk: Device):
    mountpoints = make_mountpoints_list(disk)

    while len(mountpoints) > 0:
        for i in range(len(mountpoints) - 1, -1, -1):
            mountpoint = mountpoints[i]
            if os.path.ismount(mountpoint):
                execute_command(["umount", "-R", mountpoint])
            del mountpoints[i]
    if CRYPTROOT_PATH.exists():
        execute_command(["cryptsetup", "close", CRYPTROOT_NAME])
    if CRYPTHOME_PATH.exists():
        execute_command(["cryptsetup", "close", CRYPTHOME_NAME])


def partition_and_format_disk() -> Tuple[Device, bool]:
    print(execute_command(["lsblk", "-o", "NAME,TYPE,FSAVAIL,SIZE,PATH,MOUNTPOINTS"]))
    disks: List[Device] = json.loads(
        execute_command(["lsblk", "-o", "NAME,PATH,TYPE,MOUNTPOINTS", "-J"])
    )["blockdevices"]

    options: Dict[str, Any] = dict()
    for disk in disks:
        if disk["type"] == "disk":
            options[disk["name"]] = disk

    disk: Device = select_from_dict(options, "disk")
    disk_path = Path(disk["path"])
    want_hone_partition = select_from_dict(
        prompt="Separated home partition from root one?"
    )
    crypt_root_partition = select_from_dict(
        prompt="Should the root partition be encrypted?"
    )
    crypt_home_partition = False
    if want_hone_partition:
        crypt_home_partition = select_from_dict(
            prompt="Should the home partition be encrypted?"
        )

    umount_mountpoints(disk)

    root_partition_size_prompt = "Size of the root partition (forward to fdisk)? "
    root_partition_size = input(root_partition_size_prompt)
    home_partition_size = None
    if want_hone_partition:
        while root_partition_size == "":
            print(
                "Root partition can't take the whole disk if you want a separated home partition"
            )
            root_partition_size = input(root_partition_size_prompt)

        home_partition_size = input("Size of the home partition (forward to fdisk)? ")

    fdisk_input = f"g n 1  +512M t 1 n 2  {root_partition_size} t 2 20 "
    if want_hone_partition:
        fdisk_input = fdisk_input + f"n 3  {home_partition_size} t 3 41 "

    fdisk_input = (fdisk_input + "w ").replace(" ", "\n").encode()
    p = subprocess.Popen(["fdisk", disk_path.as_posix()], stdin=subprocess.PIPE)
    p.communicate(input=fdisk_input)
    if p.returncode != 0:
        eprint("Fdisk returned an error")
        exit(1)

    boot_partition = add_partition_number(disk_path, 1)
    root_partition = add_partition_number(disk_path, 2)
    home_partition = add_partition_number(disk_path, 3)

    if crypt_root_partition:
        root_partition = encrypt_partition(root_partition.as_posix(), CRYPTROOT_NAME)
    create_ext4_filesystem(root_partition)
    mount_partition(root_partition, ROOT_MOUNTPOINT)
    prepare_boot_partition(boot_partition.as_posix())
    if want_hone_partition:
        if crypt_home_partition:
            home_partition = encrypt_partition(
                home_partition.as_posix(), CRYPTHOME_NAME
            )
        create_ext4_filesystem(home_partition)
        os.makedirs(HOME_MOUNTPOINT, exist_ok=True)
        mount_partition(home_partition, HOME_MOUNTPOINT)

    return (disk, crypt_root_partition or crypt_home_partition)


def encrypt_partition(partition: str, cryptname: str) -> Path:
    partition_mapping = CRYPT_PATH.joinpath(cryptname).as_posix()

    execute_command(["cryptsetup", "luksFormat", partition], False)
    execute_command(["cryptsetup", "open", partition, cryptname], False)

    return Path(partition_mapping)


def prepare_boot_partition(partition: str):
    execute_command(["mkfs.fat", "-F32", partition])
    os.makedirs(Path(BOOT_MOUNTPOINT), exist_ok=True)
    execute_command(["mount", partition, BOOT_MOUNTPOINT.as_posix()])


def create_ext4_filesystem(partition: Path):
    execute_command(["mkfs.ext4", partition.as_posix()])


def mount_partition(partition: Path, mountpoint: Path):
    execute_command(["mount", partition.as_posix(), mountpoint.as_posix()])


def generate_fstab():
    os.makedirs(join_absolute(ROOT_MOUNTPOINT, Path("/etc")), exist_ok=True)
    fstab_content: str = execute_command(["genfstab", "-U", ROOT_MOUNTPOINT.as_posix()])
    with open(join_absolute(ROOT_MOUNTPOINT, Path("/etc/fstab")), "w") as f:
        f.write(fstab_content)


def install_essential_package():
    cpu_manufacturer = get_cpu_manufacturer()

    # execute_command(["pacman-key", "--init"], capture_output=False)
    # execute_command(["pacman-key", "--populate", "archlinux"], capture_output=False)
    execute_command(
        [
            "pacstrap",
            ROOT_MOUNTPOINT.as_posix(),
            "archlinux-keyring",
            "base",
            "base-devel",
            "git",
            f"{cpu_manufacturer}-ucode",
            "linux",
            "linux-firmware",
            "man-db",
            "man-pages",
            "neovim",
            "networkmanager",
            "python3",
        ],
        capture_output=False,
    )


def chroot(device: Device, crypt_root_partition: bool):
    execute_command(["pacman", "-Sy"])
    execute_command(
        [
            "arch-chroot",
            ROOT_MOUNTPOINT.as_posix(),
            "python3",
            CONFIGURE_SCRIPT_FILEPATH.as_posix(),
            json.dumps(device),
            f"{crypt_root_partition}",
        ],
        capture_output=False,
    )


def execute_host_operation(operation):
    pacman_conf_filepath = Path("/etc/pacman.conf")

    filepaths: List[Tuple[Path, Tuple[Path, bool]]] = [
        (
            CONFIGURE_SCRIPT_FILEPATH,
            (join_absolute(ROOT_MOUNTPOINT, CONFIGURE_SCRIPT_FILEPATH), True),
        ),
        (
            UTILS_SCRIPT_FILEPATH,
            (join_absolute(ROOT_MOUNTPOINT, UTILS_SCRIPT_FILEPATH), True),
        ),
        (CONFIG_FILEPATH, (join_absolute(ROOT_MOUNTPOINT, CONFIG_FILEPATH), True)),
        (
            pacman_conf_filepath,
            (join_absolute(ROOT_MOUNTPOINT, pacman_conf_filepath), False),
        ),
    ]

    match operation:
        case "pre":
            join_absolute(ROOT_MOUNTPOINT, CONFIG_PATH).mkdir(
                parents=True, exist_ok=True
            )
        case "post":
            os.removedirs(join_absolute(ROOT_MOUNTPOINT, CONFIG_PATH))

    for (live_usb, (host, should_delete)) in filepaths:
        match operation:
            case "pre":
                shutil.copy(live_usb, host)
            case "post":
                if should_delete:
                    os.remove(host)


def main():
    config = load_config()

    checks_boot_mode()
    check_internet_connection()
    update_system_clock()
    (device, has_encrypted_partition) = partition_and_format_disk()
    generate_fstab()
    install_essential_package()
    execute_host_operation("pre")
    chroot(device, has_encrypted_partition)
    execute_host_operation("post")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Script interrupted by keyboard.{Colors.ENDC}")
