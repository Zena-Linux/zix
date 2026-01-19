# zix: Declarative & Imperative Nix Profile Manager

`zix` is a command-line tool that simplifies the management of Nix user profiles. It offers a user-friendly interface to handle package installations across different, switchable profiles (e.g., 'work', 'personal'), blending both imperative commands with a declarative foundation.

## About The Project

Managing packages directly with `nix-env` can sometimes feel purely imperative and difficult to reproduce. `zix` solves this by maintaining a simple JSON manifest (`zix.json`) that declaratively defines your profiles and their packages. It then uses this manifest to generate and manage a `flake.nix`, bringing reproducibility and easy environment switching to your user profile.

## Features

- **Profile Management**: Create, remove, and switch between multiple, isolated user profiles.
- **Simple Package Management**: Add or remove packages from the current profile with simple commands.
- **Declarative Foundation**: All profiles and packages are stored in a `zix.json` manifest.
- **Synchronization Check**: `zix list` shows if your installed environment is out of sync with your manifest.
- **Nix Flake Integration**: Automatically generates and manages a `flake.nix` to build, apply, and rollback your environment.

## Getting Started

### Installation

Ensure the `zix` binary is available in your system's `PATH`.

### Initial Setup

To start using `zix`, run the initialization command. This will create the `~/.zix` directory, which contains the manifest and the Nix Flake.

```bash
zix init
```

## Usage

`zix` provides a set of commands to manage your profiles and packages.

### `zix init`
Initializes the `~/.zix` configuration directory.

```bash
zix init
```

### `zix profile`
Manage your profiles.

- **List available profiles:**
  ```bash
  zix profile list
  ```

- **Add a new profile:**
  ```bash
  zix profile add work
  ```

- **Switch to a different profile:**
  ```bash
  zix profile switch work
  ```

- **Remove a profile:**
  ```bash
  zix profile remove work
  ```

### `zix add`
Adds one or more packages to the current profile's manifest.

```bash
zix add git neovim
```

### `zix remove`
Removes one or more packages from the current profile's manifest.

```bash
zix remove neovim
```

### `zix list`
Lists all packages declared in the current profile's manifest and compares them against the packages currently installed in your Nix profile. This helps you see if your environment is in sync.

```bash
zix list
```

### `zix build`
Builds the current profile using the `flake.nix` but does not activate it. This is useful for validating your configuration.

```bash
zix build
```

### `zix apply`
Builds and applies the current profile, making the packages available in your environment. This is the main command to sync your environment with the manifest.

```bash
zix apply
```

### `zix rollback`
Rolls back your Nix profile to the previous generation.

```bash
zix rollback
```

## Example Workflow

1.  **Initialize zix:**
    ```bash
    zix init
    ```

2.  **Create a new profile for work:**
    ```bash
    zix profile add work
    ```

3.  **Switch to the new profile:**
    ```bash
    zix profile switch work
    ```

4.  **Add some development tools to the manifest:**
    ```bash
    zix add git go
    ```

5.  **Apply the changes to your system:**
    ```bash
    zix apply
    ```

6.  **Check the status:**
    ```bash
    zix list
    ```

## How It Works

- **`~/.zix/zix.json`**: The core manifest file. It's a simple JSON that stores a list of your profiles and the packages associated with each one.
- **`~/.zix/flake.nix`**: A Nix Flake template that is dynamically populated with data from `zix.json`. It reads the package list for the current profile and builds a Nix environment.
- **The `zix` binary**: This tool acts as an orchestrator. It modifies the `zix.json` manifest and runs the appropriate `nix` commands (e.g., `nix run .#profile.switch`) against the generated flake to manage your system state.
