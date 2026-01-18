import sys
import message
from typing import Dict, List
from utils import read_json, write_json


class Manifest:
    def __init__(self, file):
        self.file = file
        if not file.exists():
            self.content = {"current_profile": "default",
                            "profiles": {"default": {"packages": []}}}
        else:
            raw = read_json(self.file, {"current_profile": "default",
                                        "profiles": {
                                            "default": {
                                                "packages": []
                                            }
                                        }})
            self.normalize(raw)

    def create(self):
        write_json(self.file, self.content)

    def normalize(self, content=None) -> Dict:
        try:
            content = self.content if content is None else content
            if "current_profile" not in content:
                content["current_profile"] = "default"

            if "profiles" not in content:
                content["profiles"] = {}

            if "default" not in content["profiles"]:
                content["profiles"]["default"] = {"packages": []}

            for profile_name, profile_data in content["profiles"].items():
                if not isinstance(profile_data, dict):
                    content["profiles"][profile_name] = {"packages": []}
                    continue

                pkgs = profile_data.get("packages", [])
                if not isinstance(pkgs, list):
                    content["profiles"][profile_name]["packages"] = []
                    continue

                cleaned: List[str] = []
                for p in pkgs:
                    if not isinstance(p, str):
                        continue
                    s = p.strip()
                    if s:
                        cleaned.append(s)

                unique_sorted = sorted(set(cleaned))
                content["profiles"][profile_name]["packages"] = unique_sorted

            if content["current_profile"] not in content["profiles"]:
                message.warn(f"Current profile '{
                             content['current_profile']
                             }' doesn't exist, switching to 'default'")
                content["current_profile"] = "default"
                if "default" not in content["profiles"]:
                    content["profiles"]["default"] = {"packages": []}

            self.content = content
            return content

        except ValueError as exc:
            message.error(f"Manifest validation error: {exc}")
            sys.exit(1)

    def write(self, content: Dict) -> None:
        file = self.file
        self.normalize(content)
        write_json(file, self.content)

    def pkg_add(self, pkg):
        content = self.content
        profile = content["current_profile"]
        pkgs = content["profiles"].get(profile, {"packages": []})

        if pkg in pkgs.get("packages", []):
            message.warn(f"{pkg} already present in profile '{profile}'.")
            return

        pkgs["packages"].append(pkg)
        content["profiles"][profile] = pkgs
        self.write(content)
        message.ok(f"Added {pkg} to profile '{profile}'.")

    def pkg_remove(self, pkg):
        content = self.content
        profile = content["current_profile"]
        pkgs = content["profiles"].get(profile, {"packages": []})

        if pkg not in pkgs.get("packages", []):
            message.warn(f"{pkg} not in profile '{profile}'.")
            return

        pkgs["packages"].remove(pkg)
        content["profiles"][profile] = pkgs
        self.write(content)
        message.ok(f"Removed {pkg} to profile '{profile}'.")

    def profile_switch(self, profile):
        content = self.content

        if profile not in content["profiles"]:
            message.error(f"Profile '{profile}' does not exist.")
            message.info(f"Available profiles: {', '.join(
                sorted(content['profiles'].keys()))}")
            message.info(f"Create it with: zix profile create {profile}")
            return

        content["current_profile"] = profile
        self.write(content)
        message.ok(f"Switched to profile '{profile}'.")
        message.info("Run 'zix apply' to install packages for this profile.")

    def profile_add(self, profile: str):
        content = self.content

        if profile in content["profiles"]:
            message.warn(f"Profile '{profile}' already exists.")
            return
        content["profiles"][profile] = {"packages": []}
        self.write(content)
        message.ok(f"Created profile '{profile}'.")

    def cmd_profile_remove(self, profile: str) -> None:
        content = self.content

        if profile == "default":
            message.error("Cannot remove the default profile.")
            return

        if profile not in content["profiles"]:
            message.error(f"Profile '{profile}' does not exist.")
            return

        if content["current_profile"] == profile:
            content["current_profile"] = "default"
            message.info(
                f"Switched to default profile before removing '{profile}'.")

        del content["profiles"][profile]
        self.write_manifest(content)
        message.ok(f"Removed profile '{profile}'.")
