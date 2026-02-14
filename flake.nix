{
  description = "Review tool for Nix flake pull requests";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    devenv.url = "github:cachix/devenv";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    devenv,
  } @ inputs:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;
      in {
        packages = {
          default = self.packages.${system}.flake-review;

          flake-review = python.pkgs.buildPythonApplication {
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
        };

        devShells.default = devenv.lib.mkShell {
          inherit inputs pkgs;
          modules = [
            {
              # Use Python packages from nixpkgs (fast, no building)
              packages = with pkgs;
                [
                  python
                  nix-diff # For derivation diff in reports
                ]
                ++ (with python.pkgs; [
                  setuptools
                  wheel
                  attrs
                  pytest
                  pytest-cov
                  mypy
                  black
                  ruff
                ]);

              cachix = {
                enable = true;
                pull = [
                  "ojsef39"
                  "nix-community"
                ];
              };

              # Scripts - these create actual executables that work in any shell
              scripts.d-test.exec = "pytest \"$@\"";
              scripts.d-test-cov.exec = "pytest --cov=flake_review --cov-report=term-missing --cov-report=html \"$@\"";
              scripts.d-lint.exec = "ruff check . \"$@\"";
              scripts.d-format.exec = "black . \"$@\"";
              scripts.d-typecheck.exec = "mypy flake_review \"$@\"";

              enterShell = ''
                echo "🔧 flake-review development environment"
                echo "Python: $(python --version)"
                echo ""
                echo "Available commands:"
                echo "  d-test      - Run tests"
                echo "  d-test-cov  - Run tests with coverage report"
                echo "  d-lint      - Run linter"
                echo "  d-format    - Format code"
                echo "  d-typecheck - Run type checker"
              '';
            }
          ];
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.flake-review}/bin/flake-review";
        };
      }
    );
}
