{
  description = "Review tool for Nix flake pull requests";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;
        devPython = python.withPackages (
          ps:
            with ps; [
              setuptools
              wheel
              attrs
              pytest
              pytest-cov
              mypy
              black
              ruff
            ]
        );

        mkDevScript = name: exec:
          pkgs.writeShellApplication {
            inherit name;
            runtimeInputs = [devPython];
            text = exec;
          };

        dTest = mkDevScript "d-test" ''pytest "$@"'';
        dTestCov = mkDevScript "d-test-cov" ''pytest --cov=flake_review --cov-report=term-missing --cov-report=html "$@"'';
        dLint = mkDevScript "d-lint" ''ruff check . "$@"'';
        dFormat = mkDevScript "d-format" ''black . "$@"'';
        dTypecheck = mkDevScript "d-typecheck" ''mypy flake_review "$@"'';

        flakeReview = python.pkgs.buildPythonApplication {
          pname = "flake-review";
          version = "0.1.0";

          src = pkgs.lib.sources.sourceFilesBySuffices ./. [
            ".py"
            ".toml"
            ".txt"
            ".md"
          ];

          format = "pyproject";

          nativeBuildInputs = with python.pkgs; [
            setuptools
            wheel
          ];

          propagatedBuildInputs = with python.pkgs; [
            attrs
          ];

          preFixup = ''
            makeWrapperArgs+=(--prefix PATH : ${
              pkgs.lib.makeBinPath [
                pkgs.nix-diff
                pkgs.git
              ]
            })
          '';

          checkInputs = with python.pkgs; [
            pytest
            pytestCheckHook
          ];

          pythonImportsCheck = ["flake_review"];

          meta = with pkgs.lib; {
            description = "Review tool for Nix flake pull requests";
            homepage = "https://github.com/ojsef39/flake-review";
            license = licenses.mit;
            maintainers = [];
          };
        };
      in {
        packages = {
          default = flakeReview;
          flake-review = flakeReview;
          d-test = dTest;
          d-test-cov = dTestCov;
          d-lint = dLint;
          d-format = dFormat;
          d-typecheck = dTypecheck;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            devPython
            pkgs.nix-diff
            pkgs.git
            dTest
            dTestCov
            dLint
            dFormat
            dTypecheck
          ];

          shellHook = ''
            echo "flake-review development environment"
            echo " - $(python --version)"
          '';
        };

        apps = {
          default = {
            type = "app";
            program = "${flakeReview}/bin/flake-review";
          };
          d-test = {
            type = "app";
            program = "${dTest}/bin/d-test";
          };
          d-test-cov = {
            type = "app";
            program = "${dTestCov}/bin/d-test-cov";
          };
          d-lint = {
            type = "app";
            program = "${dLint}/bin/d-lint";
          };
          d-format = {
            type = "app";
            program = "${dFormat}/bin/d-format";
          };
          d-typecheck = {
            type = "app";
            program = "${dTypecheck}/bin/d-typecheck";
          };
        };
      }
    );
}
