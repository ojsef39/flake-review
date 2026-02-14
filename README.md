# flake-review

A review tool for Nix flake pull requests, inspired by [nixpkgs-review](https://github.com/Mic92/nixpkgs-review) but designed for flake-based repositories.

## Features

- Detect changes in flake package outputs between branches
- Build changed packages across multiple systems in parallel
- Show derivation diffs via [nix-diff](https://github.com/Gabriella439/nix-diff) (if available)
- Post results as GitHub PR comments (with automatic upsert)
- Support for fork PRs

## Usage

### Review a GitHub PR

```bash
flake-review pr https://github.com/owner/repo/pull/123

# Only build specific packages
flake-review pr https://github.com/owner/repo/pull/123 -p default -p injection

# Build for multiple systems
flake-review pr https://github.com/owner/repo/pull/123 --systems x86_64-linux,aarch64-darwin

# Preview the markdown report without posting
flake-review pr https://github.com/owner/repo/pull/123 --show-result

# Post results as a PR comment (requires GITHUB_TOKEN)
flake-review pr https://github.com/owner/repo/pull/123 --post-result

# Compare without building
flake-review pr https://github.com/owner/repo/pull/123 --no-build
```

### Review local changes

```bash
# Compare against upstream tracking branch (e.g., origin/main)
flake-review local

# Compare against a specific ref
flake-review local main
flake-review local origin/main
```

### Compare two git refs

```bash
flake-review compare main feature-branch
```

### Common options

| Flag                   | Description                                             |
| ---------------------- | ------------------------------------------------------- |
| `-p, --package <name>` | Only review specific packages (can be repeated)         |
| `--systems <list>`     | Comma-separated systems to build for (default: current) |
| `--no-build`           | Only compare outputs, skip building                     |
| `--max-workers <n>`    | Max parallel build workers (default: 4)                 |
| `--post-result`        | Post results as GitHub PR comment                       |
| `--show-result`        | Print the markdown report to console                    |

## CI/CD Integration

For automated PR reviews in GitHub Actions, use the reusable workflow:

```yaml
name: Review
on: [pull_request]
jobs:
  review:
    uses: ojsef39/flake-review/.github/workflows/flake-review-reusable.yml@main
```

See [flake-review-reusable.yml](.github/workflows/flake-review-reusable.yml) for customization options.

## Requirements

- Python 3.13+
- Nix with flakes enabled
- Git
- [nix-diff](https://github.com/Gabriella439/nix-diff) (bundled with the Nix package)

## Credits

Inspired by [nixpkgs-review](https://github.com/Mic92/nixpkgs-review) by Mic92.
