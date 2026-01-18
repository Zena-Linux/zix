#!/usr/bin/env python3

from __future__ import annotations
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional
import re
import textwrap

HOME = pathlib.Path.home().resolve()
CONFIG_DIR = HOME / ".config" / "zix"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST_FILE = CONFIG_DIR / "zix.json"
FLAKE_DIR = CONFIG_DIR / "flake"
FLAKE_DIR.mkdir(parents=True, exist_ok=True)

FLAKE_TEMPLATE = textwrap.dedent("""\
{
  description = "zix generated profile";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        manifest = builtins.fromJSON (builtins.readFile ./packages.json);
        currentProfile = if manifest.current_profile != "" then manifest.current_profile else "default";
        profilePackages = manifest.profiles.${currentProfile}.packages or [];
        env = pkgs.buildEnv {
          name = "zix-profile";
          paths = builtins.map (pkg: pkgs.${pkg}) profilePackages;
        };
        switchScript = pkgs.writeShellScriptBin "switch" ''
          nix-env --set ${env}
        '';
        rollbackScript = pkgs.writeShellScriptBin "rollback" ''
          nix-env --rollback
        '';
      in {
        defaultPackage = env;
        apps = {
          profile = {
            switch = {
              type = "app";
              program = "${switchScript}/bin/switch";
            };
            rollback = {
              type = "app";
              program = "${rollbackScript}/bin/rollback";
            };
          };
        };
      });
}
""")


def _print_stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def info(msg: str) -> None:
    print(f"\033[1;34m[info]\033[0m {msg}")


def ok(msg: str) -> None:
    print(f"\033[1;32m[ok]\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"\033[1;33m[warn]\033[0m {msg}")


def error(msg: str) -> None:
    _print_stderr(f"\033[1;31m[error]\033[0m {msg}")


def atomic_write(path: pathlib.Path, data: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.chmod(tmp, mode)
        shutil.move(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def read_json(path: pathlib.Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception as exc:
        error(f"Failed to read JSON from {path}: {exc}")
        return default if default is not None else {}


def write_json(path: pathlib.Path, data) -> None:
    atomic_write(path, json.dumps(data, indent=2) + "\n")


PKG_NAME_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")


def validate_pkg_name(name: str) -> None:
    if not PKG_NAME_RE.match(name):
        raise ValueError(
            "package name must match [A-Za-z0-9_.+-] (no spaces).")


def normalize_manifest(man: Dict) -> Dict:
    """Normalize manifest to ensure consistent structure."""
    # Ensure current_profile exists
    if "current_profile" not in man:
        man["current_profile"] = "default"

    # Ensure profiles exists
    if "profiles" not in man:
        man["profiles"] = {}

    # Ensure default profile exists
    if "default" not in man["profiles"]:
        man["profiles"]["default"] = {"packages": []}

    # Clean each profile's packages
    for profile_name, profile_data in man["profiles"].items():
        if not isinstance(profile_data, dict):
            man["profiles"][profile_name] = {"packages": []}
            continue

        pkgs = profile_data.get("packages", [])
        if not isinstance(pkgs, list):
            man["profiles"][profile_name]["packages"] = []
            continue

        cleaned: List[str] = []
        for p in pkgs:
            if not isinstance(p, str):
                continue
            s = p.strip()
            if s:
                cleaned.append(s)

        unique_sorted = sorted(set(cleaned))
        man["profiles"][profile_name]["packages"] = unique_sorted

    # Ensure current_profile exists in profiles
    if man["current_profile"] not in man["profiles"]:
        warn(f"Current profile '{man['current_profile']}' doesn't exist, switching to 'default'")
        man["current_profile"] = "default"
        if "default" not in man["profiles"]:
            man["profiles"]["default"] = {"packages": []}

    return man


def read_manifest() -> Dict:
    if not MANIFEST_FILE.exists():
        return {"current_profile": "default", "profiles": {"default": {"packages": []}}}

    raw = read_json(MANIFEST_FILE, {"current_profile": "default", "profiles": {"default": {"packages": []}}})
    try:
        return normalize_manifest(raw)
    except ValueError as exc:
        error(f"Manifest validation error: {exc}")
        sys.exit(1)


def write_manifest(man: Dict) -> None:
    norm = normalize_manifest(man)
    write_json(MANIFEST_FILE, norm)


def ensure_nix_available() -> bool:
    return shutil.which("nix") is not None


def run_proc(cmd: List[str],
             cwd: Optional[pathlib.Path] = None,
             check: bool = True) -> int:
    try:
        info(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)
        return res.returncode
    except subprocess.CalledProcessError as e:
        error(f"Command failed (exit {e.returncode}): {' '.join(cmd)}")
        return e.returncode
    except FileNotFoundError:
        error(f"Command not found: {cmd[0]}")
        return 127


def get_installed_packages() -> Optional[set[str]]:
    try:
        current_env = subprocess.check_output(
            ["readlink", "-f", os.path.expanduser("~/.nix-profile")],
            text=True
        ).strip()

        if not current_env:
            warn("No nix environment currently active")
            return None

        info(f"Current environment: {os.path.basename(current_env)}")

        if "zix-profile" not in current_env:
            warn("Not a zix environment")
            return None

        drv_path = subprocess.check_output(
            ["nix-store", "--query", "--deriver", current_env],
            text=True
        ).strip()

        drv_json = subprocess.check_output(
            ["nix", "derivation", "show", drv_path],
            text=True
        )

        pattern = r'/nix/store/[^/]+-([a-zA-Z0-9._+-]+?)-[\d.]+(?:-|$)'
        installed_packages = set(re.findall(pattern, drv_json))

        if not installed_packages:
            drv_data = json.loads(drv_json)
            pkgs_json = list(drv_data.values())[0]["env"]["pkgs"]
            pkgs_data = json.loads(pkgs_json)
            installed_packages = set()
            for item in pkgs_data:
                for path in item["paths"]:
                    basename = os.path.basename(path)
                    pkg_name = re.sub(r'^[^-]+-', '', basename)
                    pkg_name = re.sub(r'-[0-9][^-]*$', '', pkg_name)
                    installed_packages.add(pkg_name)

        return installed_packages

    except Exception as e:
        warn(f"Could not query installed packages: {e}")
        return None


def compare_manifest_with_installed(manifest_packages: set[str],
                                    installed_packages: set[str]) -> None:
    if manifest_packages == installed_packages:
        ok("Environment is in sync with manifest")
        return

    warn("Out of sync!")
    missing = manifest_packages - installed_packages
    extra = installed_packages - manifest_packages

    if missing:
        print(f"  Missing packages: {', '.join(sorted(missing))}")
    if extra:
        print(f"  Extra packages: {', '.join(sorted(extra))}")

    print()
    info("Sync using: zix apply")


def cmd_init() -> None:
    if MANIFEST_FILE.exists():
        warn("Manifest already exists; no changes made.")
        return
    write_manifest({"current_profile": "default", "profiles": {"default": {"packages": []}}})
    ok("Created zix.json with default profile.")


def cmd_add(pkg: str) -> None:
    try:
        validate_pkg_name(pkg)
    except ValueError as exc:
        error(str(exc))
        return

    man = read_manifest()
    current_profile = man["current_profile"]
    profile_data = man["profiles"].get(current_profile, {"packages": []})

    if pkg in profile_data.get("packages", []):
        warn(f"{pkg} already present in profile '{current_profile}'.")
        return

    profile_data["packages"].append(pkg)
    man["profiles"][current_profile] = profile_data
    write_manifest(man)
    ok(f"Added {pkg} to profile '{current_profile}'.")


def cmd_remove(pkg: str) -> None:
    man = read_manifest()
    current_profile = man["current_profile"]
    profile_data = man["profiles"].get(current_profile, {"packages": []})

    if pkg not in profile_data.get("packages", []):
        warn(f"{pkg} not in profile '{current_profile}'.")
        return

    profile_data["packages"].remove(pkg)
    man["profiles"][current_profile] = profile_data
    write_manifest(man)
    ok(f"Removed {pkg} from profile '{current_profile}'.")


def cmd_list() -> None:
    man = read_manifest()
    current_profile = man["current_profile"]

    info(f"Current profile: {current_profile}")
    print()

    info("Available profiles:")
    for profile_name in sorted(man["profiles"].keys()):
        prefix = " * " if profile_name == current_profile else "   "
        package_count = len(man["profiles"][profile_name].get("packages", []))
        print(f"{prefix}{profile_name} ({package_count} packages)")

    print()
    current_profile_data = man["profiles"].get(current_profile, {"packages": []})
    manifest_packages = set(current_profile_data.get("packages", []))

    info(f"Manifest packages for '{current_profile}':")
    if manifest_packages:
        for p in sorted(manifest_packages):
            print(f"  - {p}")
    else:
        print("  (none)")

    print()
    installed_packages = get_installed_packages()

    if installed_packages is None:
        info("Apply using: zix apply")
        return

    info(f"Installed packages ({len(installed_packages)}):")
    for pkg in sorted(installed_packages):
        print(f"  - {pkg}")

    print()
    compare_manifest_with_installed(manifest_packages, installed_packages)


def cmd_profile_list() -> None:
    """List all profiles with their packages."""
    man = read_manifest()
    current_profile = man["current_profile"]

    info(f"Current profile: {current_profile}")
    print()

    for profile_name in sorted(man["profiles"].keys()):
        prefix = " * " if profile_name == current_profile else "   "
        profile_data = man["profiles"][profile_name]
        packages = profile_data.get("packages", [])
        print(f"{prefix}{profile_name}:")
        for pkg in sorted(packages):
            print(f"      - {pkg}")
        if not packages:
            print("      (empty)")
        print()


def cmd_profile_create(profile_name: str) -> None:
    """Create a new profile."""
    if not profile_name:
        error("Profile name cannot be empty")
        return

    man = read_manifest()

    if profile_name in man["profiles"]:
        warn(f"Profile '{profile_name}' already exists.")
        return

    man["profiles"][profile_name] = {"packages": []}
    write_manifest(man)
    ok(f"Created profile '{profile_name}'.")


def cmd_profile_switch(profile_name: str) -> None:
    """Switch to a different profile."""
    man = read_manifest()

    if profile_name not in man["profiles"]:
        error(f"Profile '{profile_name}' does not exist.")
        info(f"Available profiles: {', '.join(sorted(man['profiles'].keys()))}")
        info(f"Create it with: zix profile create {profile_name}")
        return

    man["current_profile"] = profile_name
    write_manifest(man)
    ok(f"Switched to profile '{profile_name}'.")
    info(f"Run 'zix apply' to install packages for this profile.")


def cmd_profile_remove(profile_name: str) -> None:
    """Remove a profile."""
    if profile_name == "default":
        error("Cannot remove the default profile.")
        return

    man = read_manifest()

    if profile_name not in man["profiles"]:
        error(f"Profile '{profile_name}' does not exist.")
        return

    # If current profile is being removed, switch to default first
    if man["current_profile"] == profile_name:
        man["current_profile"] = "default"
        info(f"Switched to default profile before removing '{profile_name}'.")

    del man["profiles"][profile_name]
    write_manifest(man)
    ok(f"Removed profile '{profile_name}'.")


def cmd_build(force: bool = False, show: bool = False) -> None:
    flake_path = FLAKE_DIR / "flake.nix"
    packages_json = FLAKE_DIR / "packages.json"

    if not flake_path.exists() or force:
        atomic_write(flake_path, FLAKE_TEMPLATE)
        ok(f"Created/updated flake at {flake_path}")
    else:
        ok("Flake already exists")

    if packages_json.exists():
        if not packages_json.is_symlink():
            warn(f"{packages_json} exists but is not a symlink, removing")
            packages_json.unlink()
        elif packages_json.resolve() != MANIFEST_FILE:
            warn("packages.json symlink points elsewhere, updating")
            packages_json.unlink()

    if not packages_json.exists():
        os.symlink(MANIFEST_FILE, packages_json)
        ok(f"Created symlink: {packages_json} -> {MANIFEST_FILE}")

    if ensure_nix_available():
        run_proc(["nix", "flake", "lock"], cwd=FLAKE_DIR, check=False)
        ok("Updated flake.lock")
    else:
        warn("nix CLI not found; skipping lock")

    if show:
        print("----- flake.nix -----")
        print(FLAKE_TEMPLATE)
        print("---------------------")


def cmd_apply() -> None:
    flake_path = FLAKE_DIR / "flake.nix"
    if not flake_path.exists():
        error("Flake does not exist. Run `zix build` first.")
        return
    if not ensure_nix_available():
        error("nix CLI not found; cannot apply.")
        return

    man = read_manifest()
    current_profile = man["current_profile"]
    info(f"Applying profile '{current_profile}'...")

    run_proc(["nix", "run", "--impure", f"{FLAKE_DIR}#profile.switch"], cwd=FLAKE_DIR)


def cmd_rollback() -> None:
    flake_path = FLAKE_DIR / "flake.nix"
    if not flake_path.exists():
        error("Flake does not exist. Run `zix build` first.")
        return
    if not ensure_nix_available():
        error("nix CLI not found; cannot rollback.")
        return
    run_proc(["nix", "run", f"{FLAKE_DIR}#profile.rollback"], cwd=FLAKE_DIR)


def main(argv=None) -> None:
    description = "zix - declarative & imperative user profile manager for Nix"
    epilog = textwrap.dedent(
        "Examples:\n"
        "  zix init\n"
        "  zix profile create work\n"
        "  zix profile switch work\n"
        "  zix add git\n"
        "  zix build --show\n"
        "  zix apply\n"
        "  zix list\n"
    )

    parser = argparse.ArgumentParser(
        prog="zix",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create a new zix.json manifest")

    p_add = sub.add_parser(
        "add", help="add package(s) to current profile"
    )
    p_add.add_argument(
        "pkgs",
        nargs="+",
        help="package name(s) (nix attribute names, e.g., git)",
    )

    p_rm = sub.add_parser(
        "remove", help="remove package(s) from current profile"
    )
    p_rm.add_argument(
        "pkgs",
        nargs="+",
        help="package name(s) (nix attribute names)",
    )

    sub.add_parser(
        "list", help="list declared packages and installed packages for current profile")

    sub.add_parser(
        "profile-list", help="list all profiles with their packages"
    )

    p_profile_create = sub.add_parser(
        "profile-create", help="create a new profile"
    )
    p_profile_create.add_argument(
        "profile_name",
        help="name of the new profile"
    )

    p_profile_switch = sub.add_parser(
        "profile-switch", help="switch to a different profile"
    )
    p_profile_switch.add_argument(
        "profile_name",
        help="name of the profile to switch to"
    )

    p_profile_remove = sub.add_parser(
        "profile-remove", help="remove a profile"
    )
    p_profile_remove.add_argument(
        "profile_name",
        help="name of the profile to remove"
    )

    p_build = sub.add_parser(
        "build", help="generate flake.nix and symlink packages.json"
    )
    p_build.add_argument(
        "--force", "-f",
        action="store_true",
        help="force regeneration of flake.nix",
    )
    p_build.add_argument(
        "--show",
        action="store_true",
        help="print flake.nix to stdout",
    )

    sub.add_parser(
        "apply", help="apply the flake to your Nix profile")
    sub.add_parser(
        "rollback", help="rollback the profile via nix-env rollback")

    args = parser.parse_args(argv)

    if args.cmd == "init":
        cmd_init()
    elif args.cmd == "add":
        for pkg in args.pkgs:
            cmd_add(pkg)
    elif args.cmd == "remove":
        for pkg in args.pkgs:
            cmd_remove(pkg)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "profile-list":
        cmd_profile_list()
    elif args.cmd == "profile-create":
        cmd_profile_create(args.profile_name)
    elif args.cmd == "profile-switch":
        cmd_profile_switch(args.profile_name)
    elif args.cmd == "profile-remove":
        cmd_profile_remove(args.profile_name)
    elif args.cmd == "build":
        cmd_build(force=args.force, show=args.show)
    elif args.cmd == "apply":
        cmd_apply()
    elif args.cmd == "rollback":
        cmd_rollback()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
