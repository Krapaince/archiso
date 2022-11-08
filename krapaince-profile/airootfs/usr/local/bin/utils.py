from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, TypedDict


CONFIG_PATH = Path("/usr/local/share/installer")
CONFIG_FILEPATH = CONFIG_PATH.joinpath("config.json")


class Device:
    name: str
    type: str
    path: str
    mountpoints: List[str]
    children: List[Device]


class KrapainceConfig(TypedDict):
    install: bool
    dotdrop_profile: str


class Config(TypedDict):
    timezone: str
    lang: str
    locale_gen: List[str]
    hostname: str
    username: str
    skel: List[str]
    krapaince_config: KrapainceConfig


class Colors:
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[33m"
    WARNING = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def execute_command(
    command: List[str], capture_output: bool = True, **kwargs
) -> str | None:
    print(f"{Colors.YELLOW}Executing -> {Colors.CYAN}{' '.join(command)}{Colors.ENDC}")
    try:
        if capture_output:
            return subprocess.check_output(command, text=True, **kwargs)
        else:
            subprocess.run(command, check=True, **kwargs)
    except subprocess.CalledProcessError:
        print(f"\n{Colors.RED}Command failed.{Colors.ENDC}")
        exit(1)


def add_partition_number(disk: Path, nb: int):
    disk_path = disk.as_posix()
    if disk_path.startswith("/dev/nvme"):
        disk_path = f"{disk_path}p"
    disk_path = f"{disk_path}{nb}"
    return Path(disk_path)


def select_from_dict(
    options: Dict[str, Any] = {"No": False, "Yes": True},
    name: str = "",
    prompt: str | None = None,
):
    index = 0
    index_valid_list = []

    if prompt == None:
        prompt = f"Select a {name}:"
    print(f"{Colors.MAGENTA}{prompt}{Colors.ENDC}")

    for (key, value) in options.items():
        index = index + 1
        index_valid_list.extend([([key, value])])
        print(f"{Colors.YELLOW}{str(index)}) {Colors.CYAN}{key}{Colors.ENDC}")

    is_input_valid = False
    selected = None
    while not is_input_valid:
        raw_input = input(name + ": ")
        input_no = None
        try:
            input_no = int(raw_input) - 1
        except ValueError:
            pass

        if (
            isinstance(input_no, int)
            and input_no > -1
            and input_no < len(index_valid_list)
        ):
            selected = index_valid_list[input_no]
            print(f"Selected {name}: {Colors.CYAN}{selected[0]}{Colors.ENDC}\n")
            is_input_valid = True
        else:
            print("Please select a valid " + name + " number")

    return selected[1]


def get_cpu_manufacturer() -> str:
    model_name = execute_command(["grep", "-m", "1", "model name", "/proc/cpuinfo"])

    if "intel" in model_name.lower():
        return "intel"
    else:
        return "amd"


def load_config() -> Config:
    with open(CONFIG_FILEPATH, "r") as f:
        config: Config = json.load(f)

    if not isinstance(config["timezone"], str):
        config["timezone"] = "Europe/Paris"
    if not isinstance(config["lang"], str):
        config["lang"] = "en_US.UTF-8"
    if not isinstance(config["locale_gen"], List):
        config["locale_gen"] = ["en_US.UTF-8 UTF-8", "en_US ISO-8859-1"]
    return config
