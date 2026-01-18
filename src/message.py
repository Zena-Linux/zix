import sys


def info(msg: str) -> None:
    print(f"\033[1;34m[info]\033[0m {msg}")


def ok(msg: str) -> None:
    print(f"\033[1;32m[ok]\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"\033[1;33m[warn]\033[0m {msg}")


def error(msg: str) -> None:
    print(f"\033[1;31m[error]\033[0m {msg}", file=sys.stderr)
