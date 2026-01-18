import pathlib
import argparse
import textwrap

import message
from flake import Flake
from manifest import Manifest

HOME_DIR = pathlib.Path.home().resolve()
ZIX_DIR = HOME_DIR / ".zix"


def cmd_init() -> None:
    ZIX_DIR.mkdir(exist_ok=True)
    flake = Flake(ZIX_DIR, "default")
    flake.create()
    manifest = Manifest(ZIX_DIR / "zix.json")
    manifest.create()
    message.ok("zix initialized.")


def cmd_add(manifest: Manifest, pkg: str) -> None:
    manifest.pkg_add(pkg)


def cmd_remove(manifest: Manifest, pkg: str) -> None:
    manifest.pkg_remove(pkg)


def cmd_list(manifest: Manifest) -> None:
    profile = manifest.content["current_profile"]
    pkgs = manifest.content["profiles"][profile]["packages"]
    message.info(f"Packages in profile '{profile}':")
    for pkg in pkgs:
        print(f"  - {pkg}")


def cmd_profile(manifest: Manifest, args) -> None:
    if args.profile_cmd == "add":
        manifest.profile_add(args.profile_name)
    elif args.profile_cmd == "remove":
        manifest.cmd_profile_remove(args.profile_name)
    elif args.profile_cmd == "list":
        profiles = manifest.content["profiles"].keys()
        message.info("Profiles:")
        for p in profiles:
            if p == manifest.content["current_profile"]:
                print(f"  - {p} (current)")
            else:
                print(f"  - {p}")
    elif args.profile_cmd == "switch":
        manifest.profile_switch(args.profile_name)


def cmd_build(flake: Flake) -> None:
    flake.build()


def cmd_apply(flake: Flake) -> None:
    flake.apply()


def cmd_rollback(flake: Flake) -> None:
    flake.rollback()


def build_parser() -> argparse.ArgumentParser:
    description = "zix - declarative & imperative user profile manager for Nix"
    epilog = textwrap.dedent(
        "Examples:\n"
        "  zix init\n"
        "  zix profile add work\n"
        "  zix profile switch work\n"
        "  zix profile list\n"
        "  zix profile remove work\n"
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

    sub.add_parser("init", help="initializes zix")

    p_add = sub.add_parser("add", help="add package(s) to current profile")
    p_add.add_argument("pkgs", nargs="+", help="package name(s)")

    p_rm = sub.add_parser(
        "remove", help="remove package(s) from current profile")
    p_rm.add_argument("pkgs", nargs="+", help="package name(s)")

    sub.add_parser("list", help="list declared packages")

    profile = sub.add_parser("profile", help="manage profiles")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)

    p_profile_add = profile_sub.add_parser(
        "add", help="add package(s) to profile")
    p_profile_add.add_argument("profile_name")

    p_profile_remove = profile_sub.add_parser(
        "remove", help="remove a profile")
    p_profile_remove.add_argument("profile_name")

    profile_sub.add_parser("list", help="list profiles")

    p_profile_switch = profile_sub.add_parser("switch", help="switch profile")
    p_profile_switch.add_argument("profile_name")

    sub.add_parser("build", help="build the profile")
    sub.add_parser("apply", help="apply the profile")
    sub.add_parser("rollback", help="rollback profile")

    return parser


def dispatch(args, manifest: Manifest, flake: Flake) -> None:
    if args.cmd == "init":
        cmd_init()

    elif args.cmd == "add":
        for pkg in args.pkgs:
            cmd_add(manifest, pkg)

    elif args.cmd == "remove":
        for pkg in args.pkgs:
            cmd_remove(manifest, pkg)

    elif args.cmd == "list":
        cmd_list(manifest)

    elif args.cmd == "profile":
        cmd_profile(manifest, args)

    elif args.cmd == "build":
        cmd_build(flake)

    elif args.cmd == "apply":
        cmd_apply(flake)

    elif args.cmd == "rollback":
        cmd_rollback(flake)


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "init":
        dispatch(args, None, None)
        return

    manifest = Manifest(ZIX_DIR / "zix.json")
    profile = manifest.content["current_profile"]
    flake = Flake(ZIX_DIR, profile)
    dispatch(args, manifest, flake)


if __name__ == "__main__":
    main()
