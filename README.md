# Krapaince's archiso sources

My custom Arch ISO. The purpose of this custom ISO is to ease Arch install
process by applying my settings and config.

## Requirements

An arch machine with the `archiso` package.

## Build

Just run the `make-iso.sh` script at the repo root.

## How it works

The `archlive` folder is a copy of the `relang` config from the `archiso`
package. Plus, it contains my custom installer. The installer is a python script
(`airootfs/etc/usr/local/bin`) that does the following:

- Check that boot mode is EFI
- Check for an internet connection
- Update system clock
- Ask the user if they want a separate partition for home
- Ask the user if they want parition(s) to be encrypted
- Ask on which disk to install the system
- Ask for partition(s) size (can be left empty to take the whole disk)
- Create a GPT table, a boot, root (and a home) paritions on the selected disk
- Mount paritions
- Generate fstab
- Install via `pacstrap` the following packages: `archlinux-keyring`, `base`,
  `base-devel`, `git`, `{cpu_manufacturer}-ucode`, `linux`, `linux-firmware`,
  `man-db`, `man-pages`, `neovim`, `networkmanager`, `python3`

Once done the install script copies and runs the configuration script.

The configuration script is executed in `chroot` on the newly installed system.
It does the following:

- Set the timezone 
- Set the locale
- Set the hostname and `/etc/hosts`
- Generate initramfs
- Setup sudo (add wheel group to sudoers)
- Set root password
- Configure boot loader (bootctl)
- Create skeleton structure directory for user
- Create user which is a member of the group `wheel` and set its password

Steps run as the newly created user:
- Install `paru`
- Steps run if `krapaince_config.install` is `true`:
  - Install dotdrop
  - Install Krapaince's config

The configuration script comes with a config file
(`airootfs/etc/usr/local/share/installer/config.json`). The config file can be
edited prior to building the ISO or directly on the live OS. However the config
can't be saved on the live ISO across reboot.

### Config

The config is a json file which contains the following fields:
- **hostname** (`str`): hostname of the machine 
- **lang** (`str`): value used in `/etc/locale.conf` (Default: `en_US.UTF-8`)
- **locale_gen** (`Array of string`): each value is written to
  `/etc/locale.gen` (Default: `["en_US.UTF-8 UTF-8", "en_US ISO-8859-1"]`)
- **timezone** (`str`): timezone (Default: `Europe/Paris`)
- **username** (`str`): name of the user you which to create
- **skel** (`Array of string`): list of folders to create in `/etc/skel`
- **krapaince_config** (`Krapaince config object`):
  - **install** (`boolean`): whether or not to install my dotfiles
  - **dotdrop_profile** (`str`): which dotdrop profile to install (See
    available values
    [here](https://github.com/Krapaince/dotfiles_linux/blob/a1583124016c7c5eefeaf71e1419e4ed814906b5/packages/install.py#L8))

## Roadmap

- Improve `intaller.py` to install on a disk with an existing partition

## Known issues

- Sometimes package installation will fail due to keyring errors even if the
  `archlinux-keyring` package is install. To pass through this error, just
  reboot.
