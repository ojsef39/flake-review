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

flake-review ships two pairs of reusable workflows.

### Fork-safe (recommended)

GitHub gives fork PRs a read-only `GITHUB_TOKEN`, so a single workflow can't both build and post a comment back to the PR. The fork-safe setup splits the work into two files: the build runs on `pull_request` (read-only is fine), uploads its report as an artifact, and a second workflow triggered via `workflow_run` runs in base-repo context with a writable token and posts the comment.

In the consuming repo:

```yaml
# .github/workflows/flake-review-build.yml
name: Flake Review Build
on:
  pull_request:
  workflow_dispatch:
    inputs:
      pr-url:
        description: "PR URL to review"
        type: string
        required: true

permissions:
  contents: read

jobs:
  build:
    uses: ojsef39/flake-review/.github/workflows/flake-review-build-reusable.yml@main
    with:
      pr-url: ${{ inputs.pr-url || github.event.pull_request.html_url }}
```

```yaml
# .github/workflows/flake-review-comment.yml
name: Flake Review Comment
on:
  workflow_run:
    workflows: ["Flake Review Build"]
    types: [completed]

permissions:
  contents: read
  pull-requests: write
  actions: read

jobs:
  comment:
    uses: ojsef39/flake-review/.github/workflows/flake-review-comment-reusable.yml@main
```

The `workflow_run` workflow always runs from the default branch's copy of the file, so PR authors can't modify it — fork PRs are safe.

The `workflow_dispatch` input lets maintainers re-run flake-review against an arbitrary PR URL from the Actions tab.

### Single-workflow (same-repo PRs only)

If you don't need fork support, the original single-workflow form still works:

```yaml
name: Review
on: [pull_request]
jobs:
  review:
    uses: ojsef39/flake-review/.github/workflows/flake-review-reusable.yml@main
```

This posts comments inline but fails on fork PRs (no write token).

See [flake-review-build-reusable.yml](.github/workflows/flake-review-build-reusable.yml), [flake-review-comment-reusable.yml](.github/workflows/flake-review-comment-reusable.yml), and [flake-review-reusable.yml](.github/workflows/flake-review-reusable.yml) for inputs.

## Requirements

- Python 3.13+
- Nix with flakes enabled
- Git
- [nix-diff](https://github.com/Gabriella439/nix-diff) (bundled with the Nix package)

## Credits

Inspired by [nixpkgs-review](https://github.com/Mic92/nixpkgs-review) by Mic92.
