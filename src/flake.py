import message
import textwrap
from utils import atomic_write, run_proc

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
        manifest = builtins.fromJSON (builtins.readFile ./zix.json);
        currentProfile = if manifest.current_profile != ""
                         then manifest.current_profile
                         else "default";
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
        buildScript = pkgs.writeShellScriptBin "build" ''
          nix build . --no-link
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
            build = {
              type = "app";
              program = "${buildScript}/bin/build";
            };
          };
        };
      });
}
""")


class Flake:
    def __init__(self, directory, profile):
        self.directory = directory
        self.file = self.directory / "flake.nix"
        self.profile = profile

    def create(self):
        file = self.file
        if not file.exists():
            message.warn("Flake does not exist. Creating flake...")
            atomic_write(file, FLAKE_TEMPLATE)
            message.ok(f"Created flake at {file}")

    def build(self) -> int:
        directory = self.directory
        profile = self.profile
        message.info(f"Building profile '{profile}'...")
        return run_proc(
            ["nix", "run", "--impure", f"{directory}#profile.build"],
            cwd=directory
        )

    def apply(self):
        directory = self.directory
        profile = self.profile
        self.create()
        message.info(f"Applying profile '{profile}'...")
        return run_proc(
            ["nix", "run",
             "--impure", f"{directory}#profile.switch"],
            cwd=directory)

    def rollback(self):
        directory = self.directory
        self.create()
        message.info("Rolling back...")
        return run_proc(["nix", "run", f"{directory}#profile.rollback"],
                        cwd=directory)
