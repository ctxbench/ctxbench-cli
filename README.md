# py-uv-nix-template (STRICT VERSION)

Python template using:

- uv (pyproject.toml + uv.lock)
- Nix Flakes
- uv2nix (Nix builds from uv.lock)
- Single source of truth for dependencies

In this template:

- `uv.lock` is the ONLY dependency lock.
- Nix consumes `uv.lock` via uv2nix.
- Non-Nix users also use `uv.lock`.

------------------------------------------------------------

## Requirements

### With Nix
- Nix with flakes enabled

### Without Nix
- Python >= 3.11
- uv installed

------------------------------------------------------------

## First Time Setup

Generate the lock file:

    uv lock

------------------------------------------------------------

## Development (With Nix)

    nix develop
    myproj
    pytest

This environment is built from `uv.lock` via uv2nix.

------------------------------------------------------------

## Development (Without Nix)

    uv sync --all-extras
    uv run myproj
    uv run pytest

------------------------------------------------------------

## Build (Hermetic via Nix)

    nix build

------------------------------------------------------------

## Update dependencies

    uv add <package>
    uv lock

Then commit `uv.lock`.
