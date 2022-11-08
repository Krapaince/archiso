#!/usr/bin/env python3

import json
import os
from pathlib import Path
import stat
import sys
from typing import List, TypedDict

from utils import (
    Colors,
    Config,
    Device,
    add_partition_number,
    execute_command,
    get_cpu_manufacturer,
    load_config,
)


class Disk(TypedDict):
    path: str
    uuid: str


def set_timezone(config: Config):
    os.symlink(f"/usr/share/zoneinfo/{config['timezone']}", "/etc/localtime")
    execute_command(["hwclock", "--systohc"])


def set_locale(config: Config):
    with open("/etc/locale.conf", "w+") as f:
        f.write(f"LANG={config['lang']}")
    with open("/etc/locale.gen", "w+") as f:
        f.write("\n".join(config["locale_gen"]))


def setup_network(config: Config):
    hostname = config["hostname"]

    with open("/etc/hostname", "w+") as f:
        f.write(hostname)

    with open("/etc/hosts", "w+") as f:
        hosts_content = f"""127.0.0.1   localhost
::1     localhost
127.0.1.1   {hostname}.localdomain {hostname}"""
        f.write(hosts_content)
    execute_command(
        ["systemctl", "enable", "NetworkManager.service"], capture_output=False
    )


def set_mkinitcpio_conf(has_encrypted_partition: bool):
    if has_encrypted_partition:
        hooks = "HOOKS=(base udev autodetect modconf block keyboard encrypt filesystems fsck)"
        execute_command(
            ["sed", "-i", "-e", f"s/^HOOKS=(.*/{hooks}/", "/etc/mkinitcpio.conf"]
        )


def generate_initramfs():
    execute_command(["mkinitcpio", "-P"], capture_output=False)


def setup_sudo():
    sudoers_filepath = Path("/etc/sudoers").as_posix()
    st = os.stat(sudoers_filepath).st_mode
    os.chmod(sudoers_filepath, st | stat.S_IWUSR)
    execute_command(
        [
            "sed",
            "-i",
            "-e",
            "s/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/",
            "/etc/sudoers",
        ]
    )
    os.chmod(sudoers_filepath, st)


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


def create_skeleton_structure(config):
    for dir in config["skel"]:
        os.makedirs(Path("/etc/skel").joinpath(dir), exist_ok=True)


def create_user(config: Config):
    execute_command(["useradd", "-mG", "wheel", config["username"]])
    execute_command(["passwd", config["username"]], capture_output=True)


def execute_cmds_as_user(username: str, cmds: List[str]):
    script_filepath = Path("/tmp/script.sh").as_posix()
    script = "#!/usr/bin/env bash\n" + "\n".join(cmds)
    with open(script_filepath, "w") as f:
        f.write(script)
    script_stat = os.stat(script_filepath).st_mode
    os.chmod(script_filepath, script_stat | stat.S_IXOTH)

    execute_command(
        ["su", username, "-P", "-c", script_filepath],
        capture_output=False,
    )


def install_paru(config: Config):
    clone_path = Path("/tmp/paru-bin").as_posix()
    cmds = [
        f"git clone --depth 1 https://aur.archlinux.org/paru-bin {clone_path}",
        f"cd {clone_path}",
        "makepkg -si",
    ]

    execute_cmds_as_user(config["username"], cmds)


def install_dotdrop(config: Config):
    cmds = ["paru --skipreview -Sy dotdrop"]

    execute_cmds_as_user(config["username"], cmds)


def install_krapaince_config(config: Config):
    dotfiles_dir = Path("~/Desktop/GIT/dotfiles_linux").as_posix()
    dotfiles_profile = config["krapaince_config"]["dotdrop_profile"]
    cmds = [
        f"mkdir -p {dotfiles_dir}",
        f"git clone https://github.com/krapaince/dotfiles_linux {dotfiles_dir}",
        f"cd {dotfiles_dir}/packages",
        f"python ./install.py {dotfiles_profile}",
        "cd ..",
        f"dotdrop install -c dotdrop/config.yaml -p {dotfiles_profile} -D",
    ]
    execute_cmds_as_user(config["username"], cmds)
    execute_command(["chsh", "-s", "/usr/bin/fish", config["username"]])


def main():
    if len(sys.argv) != 3:
        print(
            f"{Colors.RED}Script takes 2 arguments (device, has_encrypted_partition).{Colors.ENDC}"
        )
    device = json.loads(sys.argv[1])
    has_encrypted_partition = sys.argv[2] == "True"

    config = load_config()

    set_timezone(config)
    set_locale(config)
    setup_network(config)
    set_mkinitcpio_conf(has_encrypted_partition)
    generate_initramfs()
    setup_sudo()
    set_root_password()
    configure_boot_loader(device, has_encrypted_partition)

    if "username" in config:
        create_skeleton_structure(config)
        create_user(config)
        install_paru(config)

        if config["krapaince_config"]["install"]:
            install_dotdrop(config)
            install_krapaince_config(config)
            # Set browser
            # Install theme GTK/QT theme


if __name__ == "__main__":
    main()
