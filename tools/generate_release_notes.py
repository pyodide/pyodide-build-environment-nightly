# /// script
# dependencies = []
# ///

"""
Generate release notes in Markdown for nightly xbuildenv release

The data sources inside the tarball at the time of writing this script include:
- xbuildenv/requirements.txt                    --> cross-build Python packages (pip freeze)
- xbuildenv/pyodide-root/Makefile.envs          --> Emscripten and Python versions
- xbuildenv/pyodide-root/dist/pyodide-lock.json --> Pyodide runtime packages
- xbuildenv/site-packages-extras/**/*.a         --> static libraries
"""

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path


def _parse_env_var(content: str, var_name: str) -> str:
    for line in content.splitlines():
        if line.startswith(f"export {var_name}"):
            return line.split("=")[1].strip()
    return ""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def _parse_requirements(content: str) -> list[dict[str, str]]:
    """Parse pip freeze output into [{name, version}]"""
    packages = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)==(.+)$", line)
        if m:
            packages.append({"name": m.group(1), "version": m.group(2)})
    return sorted(packages, key=lambda p: p["name"].lower())


def _scan_tarball(path: Path) -> dict:
    """Extract all metadata from the tarball"""
    result: dict = {
        "emscripten_version": "",
        "python_version": "",
        "xbuildenv_packages": [],  # from requirements.txt
        "runtime_packages": [],  # from pyodide-lock.json (package_type=package)
        "runtime_libraries": [],  # from pyodide-lock.json (package_type=shared_library)
        "static_libs": [],  # from .a files
    }

    with tarfile.open(path, "r:bz2") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = member.name

            if name.endswith("Makefile.envs"):
                file = tf.extractfile(member)
                if file:
                    content = file.read().decode("utf-8", errors="replace")
                    result["emscripten_version"] = _parse_env_var(
                        content, "PYODIDE_EMSCRIPTEN_VERSION"
                    )
                    result["python_version"] = _parse_env_var(content, "PYVERSION")

            elif (
                name.endswith("requirements.txt")
                and "xbuildenv/requirements.txt" in name
            ):
                file = tf.extractfile(member)
                if file:
                    content = file.read().decode("utf-8", errors="replace")
                    result["xbuildenv_packages"] = _parse_requirements(content)

            elif name.endswith("pyodide-lock.json"):
                file = tf.extractfile(member)
                if file:
                    data = json.loads(file.read().decode("utf-8"))
                    for pkg in sorted(
                        data.get("packages", {}).values(),
                        key=lambda p: p["name"].lower(),
                    ):
                        entry = {
                            "name": pkg["name"],
                            "version": pkg.get("version", ""),
                            "sha256": pkg.get("sha256", ""),
                            "file_name": pkg.get("file_name", ""),
                        }
                        if pkg.get("package_type") == "shared_library":
                            result["runtime_libraries"].append(entry)
                        else:
                            result["runtime_packages"].append(entry)

            elif name.endswith(".a"):
                lib_file = Path(name).name
                lib_name = re.sub(r"^lib", "", re.sub(r"\.a$", "", lib_file))
                if lib_name:
                    result["static_libs"].append(lib_name)

    result["static_libs"].sort(key=str.lower)
    return result


def generate_markdown(
    version: str,
    release_path: Path | None,
    debug_path: Path | None,
) -> str:
    lines: list[str] = [
        f"# Pyodide nightly cross-build environment {version}",
        "",
    ]

    primary_path = release_path or debug_path
    if primary_path is None:
        return "\n".join(lines)

    data = _scan_tarball(primary_path)

    # Environment
    lines += [
        "## Environment",
        "",
        "| Property | Value |",
        "| --- | --- |",
        f"| Python version | `{data['python_version']}` |",
        f"| Emscripten version | `{data['emscripten_version']}` |",
        "",
    ]

    # Artifacts
    lines += [
        "## Artifacts",
        "",
        "| File | Size | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for path in (release_path, debug_path):
        if path and path.exists():
            size = _human_size(path.stat().st_size)
            checksum = _sha256_file(path)
            lines.append(f"| `{path.name}` | {size} | `{checksum}` |")
    lines.append("")

    # Cross-build environment packages (requirements.txt)
    if data["xbuildenv_packages"]:
        lines += [
            "## Cross-build environment packages",
            "",
            "Packages available for linking during cross-compilation.",
            "",
            "| Package | Version |",
            "| --- | --- |",
        ]
        for pkg in data["xbuildenv_packages"]:
            lines.append(f"| {pkg['name']} | `{pkg['version']}` |")
        lines.append("")

    # Pyodide runtime: Python packages
    if data["runtime_packages"]:
        lines += [
            "## Pyodide runtime packages",
            "",
            "| Package | Version | SHA-256 |",
            "| --- | --- | --- |",
        ]
        for pkg in data["runtime_packages"]:
            lines.append(f"| {pkg['name']} | `{pkg['version']}` | `{pkg['sha256']}` |")
        lines.append("")

    # Pyodide runtime: shared libraries
    if data["runtime_libraries"]:
        lines += [
            "## Pyodide runtime shared libraries",
            "",
            "| Library | Version | SHA-256 |",
            "| --- | --- | --- |",
        ]
        for lib in data["runtime_libraries"]:
            lines.append(f"| {lib['name']} | `{lib['version']}` | `{lib['sha256']}` |")
        lines.append("")

    # Static libraries (from .a files in site-packages-extras)
    if data["static_libs"]:
        lines += [
            "## Static libraries",
            "",
            "| Library |",
            "| --- |",
        ]
        for lib in data["static_libs"]:
            lines.append(f"| {lib} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Markdown release notes for a nightly xbuildenv release"
    )
    parser.add_argument("version", help="Release version tag, i.e., 20260601)")
    parser.add_argument("release_tarball", nargs="?", help="Path to xbuildenv.tar.bz2")
    parser.add_argument(
        "debug_tarball", nargs="?", help="Path to xbuildenv-debug.tar.bz2"
    )
    args = parser.parse_args()

    release_path = Path(args.release_tarball) if args.release_tarball else None
    debug_path = Path(args.debug_tarball) if args.debug_tarball else None

    if release_path and not release_path.exists():
        sys.exit(f"Release tarball not found: {release_path}")
    if debug_path and not debug_path.exists():
        print(f"Warning: debug tarball not found: {debug_path}", file=sys.stderr)
        debug_path = None

    print(generate_markdown(args.version, release_path, debug_path))


if __name__ == "__main__":
    main()
