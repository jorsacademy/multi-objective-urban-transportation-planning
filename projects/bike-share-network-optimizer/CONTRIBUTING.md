# Contributing

Thanks for contributing to Bike Share Network Optimizer.

## Development setup

1. Fork or clone the repository.
2. Create and activate a virtual environment.
3. Install the package with development dependencies:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Development workflow

Create a focused branch from `main`:

```bash
git checkout main
git pull
git checkout -b feat/short-description
```

Recommended branch prefixes:

- `feat/` for new functionality
- `fix/` for bug fixes
- `docs/` for documentation
- `test/` for tests
- `refactor/` for internal restructuring
- `chore/` for maintenance

Keep changes narrowly scoped. Avoid mixing unrelated refactors with behavioral changes.

## Code quality

Before opening a pull request, run:

```bash
ruff check .
pytest --cov=bike_share_optimizer --cov-report=term-missing
python -m bike_share_optimizer
```

All checks should pass locally. GitHub Actions runs the same quality gates across supported Python versions.

## Tests

Add or update tests for behavior changes. Prefer deterministic fixtures and explicit assertions. New optimization logic should include tests for normal cases, validation errors, and important edge cases.

## Pull requests

Pull requests should:

- explain the problem being solved;
- summarize the implementation;
- include relevant tests;
- keep public API changes explicit;
- update documentation when usage changes;
- pass CI before merge.

Use the repository pull request template and link related issues when applicable.

## Commit messages

Use concise, imperative commit messages. Conventional Commit-style prefixes are encouraged, for example:

- `feat: add demand weighting`
- `fix: handle empty station data`
- `test: cover fleet mix validation`
- `docs: clarify installation`

## Reporting bugs and proposing features

Use the GitHub issue forms. For bugs, include a minimal reproducible example, environment details, expected behavior, and actual behavior.

## Releases

Releases are published from version tags that match `v*.*.*`. The package version in `pyproject.toml` must match the tag without the leading `v`.

Example:

```bash
# pyproject.toml version = "0.2.0"
git tag v0.2.0
git push origin v0.2.0
```

The release workflow builds the distributions, verifies them with `twine check`, creates a GitHub Release, and publishes to PyPI through Trusted Publishing.
