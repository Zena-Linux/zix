import os
import json
import shutil
import message
import pathlib
import tempfile
import subprocess
from typing import List, Optional


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


def run_proc(cmd: List[str],
             cwd: Optional[pathlib.Path] = None,
             check: bool = True) -> int:
    try:
        message.info(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)
        return res.returncode
    except subprocess.CalledProcessError as e:
        message.error(f"Command failed with exit code {
                      e.returncode}: {' '.join(cmd)}")
        return e.returncode
    except FileNotFoundError:
        message.error(f"Command not found: {cmd[0]}")
        return 127


def read_json(path: pathlib.Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception as exc:
        message.error(f"Failed to read JSON file {path}: {exc}")
        return default if default is not None else {}


def write_json(path: pathlib.Path, data) -> None:
    atomic_write(path, json.dumps(data, indent=2) + "\n")
