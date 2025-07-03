# pyodide-build-environment-nightly

Nightly cross build environments for building Pyodide packages

## Usage

This repository contains nightly cross build environments for building Pyodide packages.
The target user of this repository is package maintainers who want to build their packages against the unreleased version of Pyodide.

Each release in this repository contains a tip-of-tree build of Pyodide of the given date.
You can use the `pyodide xbuildenv install` command to install the build environment for a given date.

### Cross build environments

#### Release builds

```bash
pip install pyodide-build

# Change the date to the date of the build you want to use
pyodide xbuildenv install --url "https://github.com/pyodide/pyodide-build-environment-nightly/releases/download/20250125/xbuildenv.tar.bz2"

# Now you can use the build environment to build your package
pyodide build
```

#### Debug builds

For debugging purposes, you can also use the debug version of the cross build environment:

```bash
pip install pyodide-build

# Change the date to the date of the build you want to use
pyodide xbuildenv install --url "https://github.com/pyodide/pyodide-build-environment-nightly/releases/download/20250125/xbuildenv-debug.tar.bz2"

# Now you can use the build environment to build your package
pyodide build
```

The debug cross build environment is built with `PYODIDE_DEBUG=1` and provides additional debugging information.

> [!NOTE]
> The debug build does not make a difference in the build process itself. It is useful if you use the Pyodide CLI runner (`pyodide venv`), as
> it will automatically use the installed debug cross build environment for the Pyodide runtime and provide additional debugging information. To
> remove the debug build environment, you may use the `pyodide xbuildenv uninstall` command.

## Maintainer Notes

The build environment is periodically built and released by GHA.

Otherwise, if you want to manually trigger a build, you can create a new tag.
Creating a tag will trigger a GHA workflow that builds the cross build environment and uploads it as a release asset.
