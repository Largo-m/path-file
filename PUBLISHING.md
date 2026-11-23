# Publishing PathFile to PyPI

PathFile is **release-ready**. This document lists the exact steps to publish.

## Pre-flight (already verified in this repo)

| Gate | Command | Status |
| --- | --- | --- |
| Lint | `python -m ruff check src tests` | ✅ All checks passed |
| Format | `python -m ruff format --check src tests` | ✅ 51 files formatted |
| Types | `python -m mypy src` | ✅ strict, 24 files, 0 errors |
| Tests + coverage | `python -m pytest --cov=path_file --cov-fail-under=85` | ✅ 875 tests, 85.26% |
| Build | `python -m build` | ✅ wheel + sdist |
| Metadata | `python -m twine check dist/*` | ✅ PASSED |

Build output (created by `python -m build`):

- `dist/path_file-0.1.0.tar.gz` (sdist)
- `dist/path_file-0.1.0-py3-none-any.whl` (wheel)

## 1. TestPyPI dry run

```bash
python -m pip install --upgrade build twine
python -m twine upload --repository testpypi dist/*
```

Verify:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ path-file
python -c "import path_file; print(path_file.__version__)"
path-file --help
```

## 2. Trusted Publishing (no passwords — recommended)

This repo already contains [.github/workflows/publish.yml](.github/workflows/publish.yml),
which runs on GitHub **release publication** and uses
`pypa/gh-action-pypi-publish@release/v1` with `id-token: write`.

Register the publisher on <https://pypi.org/manage/account/publishing/>:

| Field | Value |
| --- | --- |
| PyPI Project Name | `path-file` |
| Owner | `Largo-m` |
| Repository name | `path-file` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Then publish with:

```bash
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 --title "PathFile 0.1.0" --notes-from CHANGELOG.md
```

The workflow builds, `twine check`s, and uploads the wheel + sdist itself.

## 3. Production PyPI (manual, alternative)

```bash
python -m twine upload dist/*
```

Authentication options:

- **API token** (recommended): create at <https://pypi.org/manage/account/token/>,
  then use username `__token__` and the token as password.
- Or set `TWINE_USERNAME` / `TWINE_PASSWORD` environment variables.

## 4. After publishing

1. Create a GitHub release at <https://github.com/Largo-m/path-file/releases/new>
   with tag `v0.1.0` and the [CHANGELOG.md](CHANGELOG.md) 0.1.0 section.
2. Confirm the README shields render on <https://pypi.org/project/path-file/>.
3. Optional: enable the Codecov badge by pushing coverage with the `CI` workflow
   (`.github/workflows/ci.yml`).

## 5. Next release checklist

```bash
python -m ruff check src tests && python -m ruff format --check src tests
python -m mypy src
python -m pytest --cov=path_file --cov-fail-under=85
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Update version in `pyproject.toml`, `src/path_file/_version.py`, `CHANGELOG.md`,
then commit and push to `main`.