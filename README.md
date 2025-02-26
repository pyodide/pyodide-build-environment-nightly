# pyodide-build-environment-nightly

Nightly cross build environments for building Pyodide packages

## Usage

This repository contains nightly cross build environments for building Pyodide packages.
The target user of this repository is package maintainers who want to build their packages against the unreleased version of Pyodide.

Each release in this repository contains a tip-of-tree build of Pyodide of the given date.
You can use the `pyodide xbuildenv install` command to install the build environment for a given date.

```bash
pip install pyodide-build

# Change the date to the date of the build you want to use
pyodide xbuildenv install "https://github.com/pyodide/pyodide-build-environment-nightly/releases/download/20250125/xbuildenv.tar.gz"

# Now you can use the build environment to build your package
pyodide build
```

## Maintainer Notes

The build environment is periodically built and released by GHA.

Otherwise, if you want to manually trigger a build, you can create a new tag.
Creating a tag will trigger a GHA workflow that builds the cross build environment and uploads it as a release asset.