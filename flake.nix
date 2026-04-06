{
  description = "Strict Python + uv.lock + Nix (uv2nix)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        lib = pkgs.lib;
        python = pkgs.python312;

        workspace = uv2nix.lib.workspace.loadWorkspace {
          workspaceRoot = ./.;
        };

        projectOverlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        pyPkgs = (pkgs.callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            projectOverlay
            (final: prev: { })
          ]
        );

        runtimePython = python.withPackages (
          ps: with ps; [
            requests
            jsonschema
            pydantic
          ]
        );

        copaPkg = pkgs.symlinkJoin {
          name = "copa";
          paths = [ runtimePython ];
          nativeBuildInputs = [ pkgs.makeWrapper ];
          postBuild = ''
            if [ -e "$out/bin/copa" ]; then
              rm "$out/bin/copa"
            fi
            makeWrapper "${runtimePython}/bin/python" "$out/bin/copa" \
              --prefix PYTHONPATH : "${./src}" \
              --add-flags "-m" \
              --add-flags "copa.cli"
          '';
        };

        venv = pyPkgs.mkVirtualEnv "copa-venv" {
          copa = [ "dev" ];
        };

      in
      {
        packages.default = copaPkg;

        apps.default = {
          type = "app";
          program = "${copaPkg}/bin/copa";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            venv
            pkgs.pyright
            pkgs.ruff
            pkgs.uv
            pkgs.git
            pkgs.codex
          ];

          shellHook = ''
            export REPO_ROOT="$(pwd)"
            export PYTHONPATH="$REPO_ROOT/src"
            export VIRTUAL_ENV="${venv}"
            export PATH="${copaPkg}/bin:${venv}/bin:$PATH"

            # opcional: ajuda plugins que procuram uma pasta .venv no projeto
            if [ ! -e .venv ]; then
              ln -sfn "${venv}" .venv
            fi

            echo "COPA dev shell ready (from uv.lock)."
            echo "Python: $(which python)"
            python -m debugpy --version || true
          '';
        };
      }
    );
}
